"""Typed case predicates and stable external sorting without arbitrary expressions."""

import heapq
import math
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from .errors import EngineError
from .jobs import checkpoint
from .model import Field
from .store import Store

TriBool = bool | None


def missing(field: Field, value: Any) -> bool:
    if value is None:
        return True
    values = value if isinstance(value, list) else [str(value)]
    return any(value in field.missing_codes for value in values)


def predicate(
    fields: tuple[Field, ...], spec: dict[str, Any], depth: int = 0
) -> Callable[[dict[str, Any]], TriBool]:
    """Build a bounded typed predicate; unknown comparisons retain SQL-style missing logic."""
    if depth > 16 or not isinstance(spec, dict):
        raise EngineError("error.predicate")
    op = spec.get("op")
    if not isinstance(op, str):
        raise EngineError("error.predicate")
    if op in {"and", "or", "not"}:
        if set(spec) != {"op", "args"} or not isinstance(spec["args"], list):
            raise EngineError("error.predicate")
        if not 1 <= len(spec["args"]) <= 64 or (op == "not" and len(spec["args"]) != 1):
            raise EngineError("error.predicate")
        children = [predicate(fields, child, depth + 1) for child in spec["args"]]

        def combine(row: dict[str, Any]) -> TriBool:
            values = [child(row) for child in children]
            if op == "not":
                return None if values[0] is None else not values[0]
            if op == "and":
                return False if False in values else (None if None in values else True)
            return True if True in values else (None if None in values else False)

        return combine
    field = next((field for field in fields if field.id == spec.get("field")), None)
    if field is None:
        raise EngineError("error.field_id")
    if op in {"is_null", "is_coded_missing", "is_missing"}:
        if set(spec) != {"op", "field"}:
            raise EngineError("error.predicate")

        def test_missing(row: dict[str, Any]) -> bool:
            value = row[field.id]
            if op == "is_null":
                return value is None
            if op == "is_coded_missing":
                return value is not None and missing(field, value)
            return missing(field, value)

        return test_missing
    if op not in {"eq", "ne", "lt", "le", "gt", "ge", "in", "contains"} or set(spec) != {
        "op",
        "field",
        "value",
    }:
        raise EngineError("error.predicate")
    wanted = spec["value"]
    if op == "contains":
        if field.storage != "multiple_response" or not isinstance(wanted, str):
            raise EngineError("error.predicate_type")
    else:
        if field.storage == "multiple_response":
            raise EngineError("error.predicate_type")
        values = wanted if op == "in" else [wanted]
        if not isinstance(values, list) or not 1 <= len(values) <= 1024:
            raise EngineError("error.predicate")
        for value in values:
            if value is None:
                raise EngineError("error.predicate_type")
            # Codebook membership is irrelevant for a query threshold.
            Store._value(Field(field.id, field.name, field.storage, "nominal"), value)
        ordered = field.measurement == "ordinal" and bool(field.levels)
        if op in {"lt", "le", "gt", "ge"}:
            if ordered:
                if str(wanted) not in field.levels:
                    raise EngineError("error.unknown_level")
            elif field.storage not in {"int64", "float64"}:
                raise EngineError("error.predicate_type")

    def compare(row: dict[str, Any]) -> TriBool:
        value = row[field.id]
        if missing(field, value):
            return None
        if op == "eq":
            return bool(value == wanted)
        if op == "ne":
            return bool(value != wanted)
        threshold = wanted
        if op in {"lt", "le", "gt", "ge"} and field.measurement == "ordinal" and field.levels:
            if str(value) not in field.levels:
                raise EngineError("error.unknown_level")
            value = field.levels.index(str(value))
            threshold = field.levels.index(str(wanted))
        if op == "lt":
            return bool(value < threshold)
        if op == "le":
            return bool(value <= threshold)
        if op == "gt":
            return bool(value > threshold)
        if op == "ge":
            return bool(value >= threshold)
        if op == "in":
            return value in wanted
        return wanted in value

    return compare


def select(store: Store, revision: str, condition: dict[str, Any]) -> dict[str, Any]:
    item = store.get(revision)
    evaluate = predicate(item.fields, condition)
    selected = unknown = total = 0
    for table in store.iter_tables(revision):
        values = table.to_pydict()
        for index in range(table.num_rows):
            value = evaluate({field.id: values[field.id][index] for field in item.fields})
            selected += value is True
            unknown += value is None
            total += 1
    return {
        "revision": revision,
        "condition": condition,
        "total": total,
        "selected": selected,
        "false": total - selected - unknown,
        "unknown": unknown,
        "rule": "Only true cases are selected; unknown cases remain distinct.",
    }


def filter_cases(store: Store, revision: str, condition: dict[str, Any]) -> dict[str, Any]:
    item = store.get(revision)
    evaluate = predicate(item.fields, condition)
    path = store.directory / f"{uuid4()}.parquet"
    schema = pq.ParquetFile(item.base).schema_arrow
    count = 0
    try:
        with pq.ParquetWriter(path, schema) as writer:
            for table in store.iter_tables(revision):
                values = table.to_pydict()
                mask = [
                    evaluate({field.id: values[field.id][index] for field in item.fields}) is True
                    for index in range(table.num_rows)
                ]
                kept = table.filter(pa.array(mask, type=pa.bool_()))
                writer.write_table(kept, row_group_size=1024)
                count += kept.num_rows
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return store._record(replace(item, id=str(uuid4()), base=path, row_count=count, edits=()))


@dataclass(frozen=True)
class Descending:
    value: Any

    def __lt__(self, other: "Descending") -> bool:
        return bool(self.value > other.value)


def _sort_options(
    fields: tuple[Field, ...], keys: list[dict[str, Any]], nulls: str
) -> list[tuple[Field, bool]]:
    if (
        nulls not in {"first", "last"}
        or not isinstance(keys, list)
        or not 1 <= len(keys) <= len(fields)
    ):
        raise EngineError("error.sort_options")
    options: list[tuple[Field, bool]] = []
    for key in keys:
        if (
            not isinstance(key, dict)
            or set(key) - {"field", "ascending"}
            or type(key.get("ascending", True)) is not bool
        ):
            raise EngineError("error.sort_options")
        field = next((field for field in fields if field.id == key.get("field")), None)
        if field is None or any(field.id == previous.id for previous, _ in options):
            raise EngineError("error.field_id")
        if field.storage == "multiple_response":
            raise EngineError("error.sort_options")
        options.append((field, key.get("ascending", True)))
    return options


def _key(row: dict[str, Any], options: list[tuple[Field, bool]], nulls: str) -> tuple[Any, ...]:
    result: list[Any] = []
    for field, ascending in options:
        value = row[field.id]
        absent = missing(field, value)
        marker = int(absent) if nulls == "last" else int(not absent)
        if absent:
            result.append((marker, 0))
            continue
        if field.measurement == "ordinal" and field.levels:
            if str(value) not in field.levels:
                raise EngineError("error.unknown_level")
            value = field.levels.index(str(value))
        if isinstance(value, float) and not math.isfinite(value):
            raise EngineError("error.nonfinite")
        result.append((marker, value if ascending else Descending(value)))
    return tuple(result)


def _rows(path: Path) -> Iterator[dict[str, Any]]:
    for batch in pq.ParquetFile(path).iter_batches(batch_size=64):
        values = batch.to_pydict()
        for index in range(batch.num_rows):
            yield {name: column[index] for name, column in values.items()}


def _merge(
    paths: list[Path],
    target: Path,
    schema: pa.Schema,
    options: list[tuple[Field, bool]],
    nulls: str,
) -> None:
    total = sum(pq.ParquetFile(path).metadata.num_rows for path in paths)
    processed = 0
    checkpoint(0, total)
    streams = [_rows(path) for path in paths]
    heap: list[tuple[Any, int, dict[str, Any]]] = []

    def push(index: int) -> None:
        row = next(streams[index], None)
        if row is not None:
            # The stable position is stored in every run; case IDs need not equal positions.
            heapq.heappush(
                heap, ((_key(row, options, nulls), row["_openstat_sort_position"]), index, row)
            )

    for index in range(len(streams)):
        push(index)
    pending: list[dict[str, Any]] = []
    with pq.ParquetWriter(target, schema) as writer:
        while heap:
            _, index, row = heapq.heappop(heap)
            pending.append(row)
            processed += 1
            if len(pending) >= 1024:
                checkpoint(processed, total)
                writer.write_table(pa.Table.from_pylist(pending, schema=schema))
                pending.clear()
            push(index)
        checkpoint(processed, total)
        if pending:
            writer.write_table(pa.Table.from_pylist(pending, schema=schema))


def sort_cases(
    store: Store, revision: str, keys: list[dict[str, Any]], nulls: str = "last"
) -> dict[str, Any]:
    item = store.get(revision)
    options = _sort_options(item.fields, keys, nulls)
    source_schema = pq.ParquetFile(item.base).schema_arrow
    schema = source_schema.append(pa.field("_openstat_sort_position", pa.int64()))
    output = store.directory / f"{uuid4()}.parquet"
    try:
        with tempfile.TemporaryDirectory(prefix="openstat-sort-", dir=store.directory) as temporary:
            directory = Path(temporary)
            runs: list[Path] = []
            position = 0
            for table in store.iter_tables(revision):
                values = table.to_pydict()
                indices = sorted(
                    range(table.num_rows),
                    key=lambda i: _key(
                        {name: column[i] for name, column in values.items()}, options, nulls
                    ),
                )
                run = directory / f"{uuid4()}.parquet"
                expanded = table.append_column(
                    "_openstat_sort_position",
                    pa.array(range(position, position + table.num_rows), type=pa.int64()),
                )
                pq.write_table(
                    expanded.take(pa.array(indices, type=pa.int64())), run, row_group_size=1024
                )
                runs.append(run)
                position += table.num_rows
            while len(runs) > 1:
                combined: list[Path] = []
                for start in range(0, len(runs), 16):
                    group = runs[start : start + 16]
                    merged = directory / f"{uuid4()}.parquet"
                    _merge(group, merged, schema, options, nulls)
                    combined.append(merged)
                    for run in group:
                        run.unlink()
                runs = combined
            with pq.ParquetWriter(output, source_schema) as writer:
                if runs:
                    for batch in pq.ParquetFile(runs[0]).iter_batches(batch_size=1024):
                        writer.write_table(
                            pa.Table.from_batches([batch]).drop(["_openstat_sort_position"])
                        )
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return store._record(replace(item, id=str(uuid4()), base=output, edits=()))


def weights(store: Store, revision: str, field: str, kind: str = "frequency") -> dict[str, Any]:
    item = store.get(revision)
    definition = next((f for f in item.fields if f.id == field), None)
    if kind not in {"frequency", "analytic"} or definition is None:
        raise EngineError("error.weight_options")
    if definition.storage not in {"int64", "float64"} or definition.role == "identifier":
        raise EngineError("error.weight_options")
    eligible = missing_count = zero = 0
    integer_total = 0
    totals: list[float] = []
    total = 0.0
    try:
        for table in store.iter_tables(revision, [field]):
            values: list[float] = []
            for value in table[field].to_pylist():
                if missing(definition, value):
                    missing_count += 1
                    continue
                if (
                    value < 0
                    or not math.isfinite(value)
                    or (kind == "frequency" and value != int(value))
                ):
                    raise EngineError("error.weight_value")
                eligible += 1
                zero += value == 0
                if kind == "frequency":
                    integer_total += int(value)
                else:
                    values.append(float(value))
            if kind == "analytic":
                totals.append(math.fsum(values))
                if len(totals) == 128:
                    total = math.fsum([total, *totals])
                    totals.clear()
        total = math.fsum([total, *totals])
    except OverflowError as exc:
        raise EngineError("error.weight_value") from exc
    if not math.isfinite(total):
        raise EngineError("error.weight_value")
    return {
        "revision": revision,
        "field": field,
        "kind": kind,
        "eligible": eligible,
        "missing": missing_count,
        "zero": zero,
        "total_weight": integer_total if kind == "frequency" else total,
        "total_weight_exact": str(integer_total) if kind == "frequency" else None,
        "convention": (
            "frequency: exact nonnegative integer counts; "
            "analytic: nonnegative finite values"
        ),
    }
