"""Explicit data classification and counts; no inferential statistical methods."""

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from .errors import EngineError
from .model import Field, validate_fields
from .store import ARROW_TYPES, ROW_ID, Revision, Store

BATCH_ROWS = 8192


def missing_kind(field: Field, value: Any) -> str:
    """Null and user-coded missing are distinct; response codes invalidate the case."""
    if value is None:
        return "null"
    candidates = value if isinstance(value, list) else [str(value)]
    return "coded_missing" if any(v in field.missing_codes for v in candidates) else "valid"


def _field(item: Revision, source: str) -> Field:
    result = next((field for field in item.fields if field.id == source), None)
    if result is None:
        raise EngineError("error.field_id")
    return result


def _batches(
    store: Store, item: Revision, columns: list[str] | None = None
) -> Iterator[dict[str, list[Any]]]:
    """Consume the store's bounded typed stream with current sparse edits applied."""
    for table in store.iter_tables(item.id, columns=columns, batch_size=BATCH_ROWS):
        yield table.to_pydict()


def _output(item: Revision, output: dict[str, Any], labels: list[str]) -> Field:
    result = Field.from_dict(output)
    validate_fields((*item.fields, result))
    if (
        result.storage != "string"
        or result.measurement not in {"nominal", "ordinal"}
        or result.role != "characteristic"
        or result.missing_codes
        or (result.levels and list(result.levels) != labels)
    ):
        raise EngineError("error.classification_output")
    return replace(result, levels=tuple(labels))


def _derive(
    store: Store,
    item: Revision,
    source: Field,
    output: Field,
    classify: Callable[[Any], str | None],
    unmatched: str,
) -> dict[str, Any]:
    if unmatched not in {"error", "missing"}:
        raise EngineError("error.classification_options")
    fields = (*item.fields, output)
    schema = pa.schema([(ROW_ID, pa.int64()), *[(f.id, ARROW_TYPES[f.storage]) for f in fields]])
    path = store.directory / f"{uuid4()}.parquet"
    try:
        with pq.ParquetWriter(path, schema) as writer:
            for values in _batches(store, item):
                classified: list[str | None] = []
                for value in values[source.id]:
                    label = None if missing_kind(source, value) != "valid" else classify(value)
                    if (
                        label is None
                        and missing_kind(source, value) == "valid"
                        and unmatched == "error"
                    ):
                        raise EngineError("error.classification_unmatched")
                    classified.append(label)
                values[output.id] = classified
                writer.write_table(pa.table(values, schema=schema))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return store._record(replace(item, id=str(uuid4()), base=path, fields=fields, edits=()))


def categories(
    store: Store,
    revision: str,
    source: str,
    output: dict[str, Any],
    mapping: list[dict[str, Any]],
    unmatched: str = "error",
) -> dict[str, Any]:
    """Map exact typed values to explicit labels; no string or numeric coercion."""
    item = store.get(revision)
    field = _field(item, source)
    if field.storage == "multiple_response" or not mapping:
        raise EngineError("error.classification_source")
    normalized: list[tuple[Any, str]] = []
    labels: list[str] = []
    for entry in mapping:
        if (
            set(entry) != {"value", "label"}
            or not isinstance(entry["label"], str)
            or not entry["label"]
        ):
            raise EngineError("error.classification_options")
        value = store._value(field, entry["value"])
        if missing_kind(field, value) != "valid" or any(value == old for old, _ in normalized):
            raise EngineError("error.classification_options")
        label = entry["label"]
        normalized.append((value, label))
        if label not in labels:
            labels.append(label)
    derived = _output(item, output, labels)

    def classify(value: Any) -> str | None:
        return next((label for candidate, label in normalized if candidate == value), None)

    return _derive(store, item, field, derived, classify, unmatched)


@dataclass(frozen=True)
class Interval:
    label: str
    lower: int | float | None
    upper: int | float | None
    include_lower: bool
    include_upper: bool

    def contains(self, value: int | float) -> bool:
        return (
            self.lower is None or value > self.lower or (self.include_lower and value == self.lower)
        ) and (
            self.upper is None or value < self.upper or (self.include_upper and value == self.upper)
        )


def _intervals(classes: list[dict[str, Any]]) -> list[Interval]:
    result: list[Interval] = []
    keys = {"label", "lower", "upper", "include_lower", "include_upper"}
    for entry in classes:
        if (
            set(entry) != keys
            or not isinstance(entry["label"], str)
            or not entry["label"]
            or type(entry["include_lower"]) is not bool
            or type(entry["include_upper"]) is not bool
        ):
            raise EngineError("error.classification_options")
        for key in ("lower", "upper"):
            value = entry[key]
            if value is not None and (
                type(value) not in {int, float}
                or (isinstance(value, float) and not math.isfinite(value))
            ):
                raise EngineError("error.classification_options")
        current = Interval(**entry)
        if (
            (current.lower is None and current.include_lower)
            or (current.upper is None and current.include_upper)
            or (
                current.lower is not None
                and current.upper is not None
                and current.lower >= current.upper
            )
            or any(old.label == current.label for old in result)
        ):
            raise EngineError("error.classification_options")
        if result:
            previous = result[-1]
            if (
                previous.upper is None
                or current.lower is None
                or previous.upper > current.lower
                or (
                    previous.upper == current.lower
                    and previous.include_upper
                    and current.include_lower
                )
            ):
                raise EngineError("error.classification_overlap")
        result.append(current)
    if not result:
        raise EngineError("error.classification_options")
    return result


def intervals(
    store: Store,
    revision: str,
    source: str,
    output: dict[str, Any],
    classes: list[dict[str, Any]],
    unmatched: str = "error",
) -> dict[str, Any]:
    """Apply ordered, non-overlapping classes with explicitly inclusive/exclusive endpoints."""
    item = store.get(revision)
    field = _field(item, source)
    if field.storage not in {"int64", "float64"}:
        raise EngineError("error.classification_source")
    definitions = _intervals(classes)
    derived = _output(item, output, [definition.label for definition in definitions])

    def classify(value: Any) -> str | None:
        return next((interval.label for interval in definitions if interval.contains(value)), None)

    return _derive(store, item, field, derived, classify, unmatched)


def _axis(field: Field, mode: str) -> list[str]:
    if field.measurement in {"continuous", "discrete"} or field.role == "identifier":
        raise EngineError("error.contingency_source")
    if field.storage == "multiple_response" and mode != "response_membership":
        raise EngineError("error.contingency_mode")
    return [value for value in field.levels if value not in field.missing_codes]


def contingency(
    store: Store,
    revision: str,
    row_field: str,
    column_field: str,
    mode: str = "exclusive",
) -> dict[str, Any]:
    """Complete-case categorical counts; response sets require an explicit membership mode."""
    if mode not in {"exclusive", "response_membership"}:
        raise EngineError("error.contingency_mode")
    item = store.get(revision)
    first, second = _field(item, row_field), _field(item, column_field)
    row_levels, column_levels = _axis(first, mode), _axis(second, mode)
    row_seen, column_seen = set(row_levels), set(column_levels)
    cells: dict[tuple[str, str], int] = {}
    eligible = null_cases = coded_cases = empty_cases = 0
    for values in _batches(store, item, list(dict.fromkeys([first.id, second.id]))):
        for left, right in zip(values[first.id], values[second.id], strict=True):
            kinds = [missing_kind(first, left), missing_kind(second, right)]
            # Null takes precedence for mutually exclusive exclusion counts.
            if "null" in kinds:
                null_cases += 1
                continue
            if "coded_missing" in kinds:
                coded_cases += 1
                continue
            eligible += 1
            row_values = left if isinstance(left, list) else [str(left)]
            column_values = right if isinstance(right, list) else [str(right)]
            if not row_values or not column_values:
                empty_cases += 1
            for value in row_values:
                if value not in row_seen:
                    row_seen.add(value)
                    row_levels.append(value)
            for value in column_values:
                if value not in column_seen:
                    column_seen.add(value)
                    column_levels.append(value)
            if len(row_levels) * len(column_levels) > 1_000_000:
                raise EngineError("error.classification_limit")
            for row in row_values:
                for column in column_values:
                    cells[row, column] = cells.get((row, column), 0) + 1
    if len(row_levels) * len(column_levels) > 1_000_000:
        raise EngineError("error.classification_limit")
    counts = [[cells.get((row, column), 0) for column in column_levels] for row in row_levels]
    row_totals = [sum(row) for row in counts]
    column_totals = [sum(row[index] for row in counts) for index in range(len(column_levels))]
    return {
        "revision": revision,
        "row_field": row_field,
        "column_field": column_field,
        "mode": mode,
        "row_levels": row_levels,
        "column_levels": column_levels,
        "counts": counts,
        "row_totals": row_totals,
        "column_totals": column_totals,
        "pair_count": sum(row_totals),
        "eligible_cases": eligible,
        "total_cases": item.row_count,
        "excluded_null_cases": null_cases,
        "excluded_coded_missing_cases": coded_cases,
        "empty_response_cases": empty_cases,
        "denominator": "eligible_cases" if mode == "exclusive" else "response_pairs",
    }


def missing_audit(store: Store, revision: str, fields: list[str] | None = None) -> dict[str, Any]:
    """Separate null, coded-missing and valid values; empty response sets are valid."""
    item = store.get(revision)
    selected = list(item.fields) if fields is None else [_field(item, source) for source in fields]
    if not selected or len({field.id for field in selected}) != len(selected):
        raise EngineError("error.field_id")
    counts = {
        field.id: {"null": 0, "coded_missing": 0, "valid": 0, "empty_response": 0}
        for field in selected
    }
    complete_cases = 0
    for values in _batches(store, item, [field.id for field in selected]):
        for index in range(len(values[ROW_ID])):
            complete = True
            for field in selected:
                value = values[field.id][index]
                kind = missing_kind(field, value)
                counts[field.id][kind] += 1
                if value == []:
                    counts[field.id]["empty_response"] += 1
                complete = complete and kind == "valid"
            complete_cases += complete
    return {
        "revision": revision,
        "total_cases": item.row_count,
        "fields": counts,
        "complete_cases": complete_cases,
        "denominator": "total_cases",
    }
