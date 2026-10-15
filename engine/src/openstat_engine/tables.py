"""Original, bounded table transformations for Phase 0."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Iterator
from fractions import Fraction
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from .classification import missing_kind
from .errors import EngineError
from .model import Field, validate_fields
from .store import ARROW_TYPES, ROW_ID, Revision, Store

GLOBAL_LIMIT = 100_000
COLUMN_LIMIT = 1_024


def _fail() -> None:
    raise EngineError("error.operation_options")


def _check_global(store: Store, revisions: list[str], columns: int = 0) -> None:
    if columns > COLUMN_LIMIT:
        raise EngineError("error.global_limit")
    if any(store.get(revision).row_count > GLOBAL_LIMIT for revision in revisions):
        raise EngineError("error.global_limit")


def _field(item: Revision, name: str) -> Field:
    found = next((field for field in item.fields if field.id == name), None)
    if found is None:
        raise EngineError("error.field_id")
    return found


def _source_tables(store: Store, revision: str, ids: list[str]) -> Iterator[pa.Table]:
    return store.iter_tables(revision, ids)


def _write(
    store: Store,
    name: str,
    fields: list[Field],
    rows: Iterable[list[Any]],
    context: str = "unspecified",
    observation_unit: str = "",
) -> dict[str, Any]:
    if not isinstance(name, str) or not name.strip():
        _fail()
    validate_fields(tuple(fields))
    dataset_id, revision_id = str(uuid4()), str(uuid4())
    path = store.directory / f"{dataset_id}.parquet"
    schema = pa.schema(
        [(ROW_ID, pa.int64()), *[(field.id, ARROW_TYPES[field.storage]) for field in fields]]
    )
    offset = 0
    try:
        with pq.ParquetWriter(path, schema) as writer:
            chunk: list[list[Any]] = []
            for row in rows:
                if len(row) != len(fields):
                    raise EngineError("error.row_width")
                chunk.append(
                    [store._value(field, value) for field, value in zip(fields, row, strict=True)]
                )
                if len(chunk) == 8192:
                    writer.write_table(_arrow_chunk(chunk, fields, offset, schema))
                    offset += len(chunk)
                    chunk = []
            if chunk:
                writer.write_table(_arrow_chunk(chunk, fields, offset, schema))
                offset += len(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return store._record(
        Revision(
            revision_id, dataset_id, name, path, tuple(fields), offset, context, observation_unit
        )
    )


def _arrow_chunk(
    rows: list[list[Any]], fields: list[Field], offset: int, schema: pa.Schema
) -> pa.Table:
    arrays = [pa.array(range(offset, offset + len(rows)), type=pa.int64())]
    arrays.extend(
        pa.array([row[index] for row in rows], type=ARROW_TYPES[field.storage])
        for index, field in enumerate(fields)
    )
    return pa.Table.from_arrays(arrays, schema=schema)


def _fresh(field: Field, *, name: str | None = None) -> Field:
    return Field(
        str(uuid4()),
        name or field.name,
        field.storage,
        field.measurement,
        field.role,
        field.levels,
        dict(field.value_labels),
        field.missing_codes,
    )


def _prov(name: str, storage: str, measure: str) -> Field:
    return Field(str(uuid4()), name, storage, measure, role="identifier")


def stack(store: Store, revisions: list[str], name: str, match: str = "name") -> dict[str, Any]:
    if (
        not isinstance(revisions, list)
        or not revisions
        or not all(isinstance(r, str) for r in revisions)
    ):
        _fail()
    if (
        not isinstance(match, str)
        or match not in {"name", "id"}
        or not isinstance(name, str)
        or not name.strip()
    ):
        _fail()
    items = [store.get(revision) for revision in revisions]

    def keys(field: Field) -> str:
        return field.name if match == "name" else field.id

    union: list[Field] = []
    by_key: dict[str, Field] = {}
    for item in items:
        for field in item.fields:
            key = keys(field)
            if key in by_key:
                old = by_key[key]
                if old.storage != field.storage or old.measurement != field.measurement:
                    raise EngineError("error.value_type")
            else:
                by_key[key] = field
                union.append(field)
    # Use fresh IDs; names remain source names and must be unique.
    out = [_fresh(f) for f in union]
    if len({f.name for f in out}) != len(out):
        raise EngineError("error.duplicate_fields")
    ds = _prov("Source dataset", "string", "nominal")
    sr = _prov("Source row ID", "int64", "discrete")
    out.extend([ds, sr])
    output_for = {
        keys(source): target for source, target in zip(union, out[: len(union)], strict=True)
    }

    def rows() -> Iterator[list[Any]]:
        for revision, item in zip(revisions, items, strict=True):
            source_ids = [f.id for f in item.fields]
            source_map = {keys(f): f.id for f in item.fields}
            for table in _source_tables(store, revision, source_ids):
                data = table.to_pydict()
                for i, row_id in enumerate(data[ROW_ID]):
                    row = [
                        data[source_map[key]][i] if key in source_map else None
                        for key in output_for
                    ]
                    yield [*row, item.dataset_id, row_id]

    return _write(store, name, out, rows())


def join(
    store: Store,
    left: str,
    right: str,
    keys: list[dict[str, str]],
    name: str,
    how: str = "inner",
    missing: str = "never",
    cardinality: str = "many_to_many",
    suffixes: list[str] | None = None,
) -> dict[str, Any]:
    if (
        not isinstance(keys, list)
        or not keys
        or any(
            not isinstance(k, dict)
            or set(k) != {"left", "right"}
            or not all(isinstance(v, str) for v in k.values())
            for k in keys
        )
        or not isinstance(how, str)
        or how not in {"inner", "left", "full"}
        or not isinstance(missing, str)
        or missing not in {"never", "equal"}
        or not isinstance(cardinality, str)
        or cardinality not in {"one_to_one", "many_to_one", "one_to_many", "many_to_many"}
        or not isinstance(name, str)
        or not name.strip()
    ):
        _fail()
    a, b = store.get(left), store.get(right)
    _check_global(store, [left, right], len(a.fields) + len(b.fields) + 4)
    pairs = [(_field(a, key["left"]), _field(b, key["right"])) for key in keys]
    if len({x.id for x, _ in pairs}) != len(pairs) or len({y.id for _, y in pairs}) != len(pairs):
        _fail()
    if any(x.storage != y.storage for x, y in pairs):
        raise EngineError("error.value_type")
    left_data = _materialize(store, left, [f.id for f in a.fields])
    right_data = _materialize(store, right, [f.id for f in b.fields])
    lkeys = [_key(row, pairs, 0, a.fields, missing) for _, row in left_data]
    rkeys = [_key(row, pairs, 1, b.fields, missing) for _, row in right_data]
    li: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    ri: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for i, key in enumerate(lkeys):
        if key is not None:
            li[key].append(i)
    for i, key in enumerate(rkeys):
        if key is not None:
            ri[key].append(i)
    for key in li.keys() | ri.keys():
        if cardinality in {"one_to_one", "one_to_many"} and len(li[key]) > 1:
            raise EngineError("error.cardinality")
        if cardinality in {"one_to_one", "many_to_one"} and len(ri[key]) > 1:
            raise EngineError("error.cardinality")
    suffixes = ["_left", "_right"] if suffixes is None else suffixes
    if (
        not isinstance(suffixes, list)
        or len(suffixes) != 2
        or not all(isinstance(x, str) and x for x in suffixes)
    ):
        _fail()
    out: list[Field] = []
    left_out: dict[str, Field] = {}
    right_out: dict[str, Field] = {}
    for field in a.fields:
        if field.id in {x.id for x, _ in pairs}:
            continue
        label = field.name + (
            suffixes[0] if any(field.name == other.name for other in b.fields) else ""
        )
        target = _fresh(field, name=label)
        out.append(target)
        left_out[field.id] = target
    for field in b.fields:
        if field.id in {y.id for _, y in pairs}:
            continue
        label = field.name + (
            suffixes[1] if any(field.name == other.name for other in a.fields) else ""
        )
        target = _fresh(field, name=label)
        out.append(target)
        right_out[field.id] = target
    key_targets: list[Field] = []
    for lf, _rf in pairs:
        target = _fresh(lf, name=lf.name)
        if target.name in {f.name for f in out}:
            raise EngineError("error.duplicate_fields")
        out.append(target)
        key_targets.append(target)
    if len({f.name for f in out}) != len(out):
        raise EngineError("error.duplicate_fields")
    provenance = [
        _prov("Left source dataset", "string", "nominal"),
        _prov("Left source row ID", "int64", "discrete"),
        _prov("Right source dataset", "string", "nominal"),
        _prov("Right source row ID", "int64", "discrete"),
    ]
    out.extend(provenance)
    matches: list[tuple[int | None, int | None]] = []
    for i, key in enumerate(lkeys):
        found = ri.get(key, []) if key is not None else []
        if found:
            if len(matches) + len(found) > GLOBAL_LIMIT:
                raise EngineError("error.global_limit")
            matches.extend((i, j) for j in found)
        elif how in {"left", "full"}:
            if len(matches) == GLOBAL_LIMIT:
                raise EngineError("error.global_limit")
            matches.append((i, None))
    if how == "full":
        for j, key in enumerate(rkeys):
            if key is None or key not in li:
                if len(matches) == GLOBAL_LIMIT:
                    raise EngineError("error.global_limit")
                matches.append((None, j))

    def outrows() -> Iterator[list[Any]]:
        for i, j in matches:
            left_row = left_data[i][1] if i is not None else {}
            right_row = right_data[j][1] if j is not None else {}
            row = [
                left_row.get(source)
                if i is not None
                else right_row.get(
                    next(
                        (
                            right_field.id
                            for left_field, right_field in pairs
                            if left_field.id == source
                        ),
                        "",
                    )
                )
                for source in left_out
            ]
            row.extend(right_row.get(source) for source in right_out)
            row.extend(
                [left_row.get(lf.id) if i is not None else right_row.get(rf.id) for lf, rf in pairs]
            )
            row.extend(
                [
                    a.dataset_id if i is not None else None,
                    left_data[i][0] if i is not None else None,
                    b.dataset_id if j is not None else None,
                    right_data[j][0] if j is not None else None,
                ]
            )
            yield row

    return _write(store, name, out, outrows())


def _materialize(store: Store, revision: str, ids: list[str]) -> list[tuple[int, dict[str, Any]]]:
    result: list[tuple[int, dict[str, Any]]] = []
    ids = list(dict.fromkeys(ids))
    for table in store.iter_tables(revision, ids):
        data = table.to_pydict()
        result.extend(
            (rid, {field: data[field][i] for field in ids}) for i, rid in enumerate(data[ROW_ID])
        )
    return result


def _key(
    row: dict[str, Any],
    pairs: list[tuple[Field, Field]],
    side: int,
    fields: tuple[Field, ...],
    missing: str,
) -> tuple[Any, ...] | None:
    result = []
    for left, right in pairs:
        field = left if side == 0 else right
        value = row[field.id]
        if value is None and missing == "never":
            return None
        result.append(tuple(value) if isinstance(value, list) else value)
    return tuple(result)


def _canonical(value: Any) -> Any:
    return tuple(value) if isinstance(value, list) else value


def transpose(
    store: Store, revision: str, name: str, fields: list[str] | None = None
) -> dict[str, Any]:
    item = store.get(revision)
    selected = fields if fields is not None else [f.id for f in item.fields]
    if (
        not isinstance(selected, list)
        or not selected
        or not all(isinstance(field, str) for field in selected)
        or len(set(selected)) != len(selected)
    ):
        _fail()
    _check_global(store, [revision], len(selected) + 2)
    definitions = [_field(item, field) for field in selected]
    storage = definitions[0].storage
    if storage not in {"float64", "int64", "string", "bool"} or any(
        field.storage != storage for field in definitions
    ):
        raise EngineError("error.value_type")
    if item.row_count + 2 > COLUMN_LIMIT:
        raise EngineError("error.global_limit")
    data = _materialize(store, revision, selected)
    measurement = {
        "float64": "continuous",
        "int64": "discrete",
        "string": "nominal",
        "bool": "binary",
    }[storage]
    case_fields = [
        _prov("Source field ID", "string", "nominal"),
        _prov("Source field name", "string", "nominal"),
        *[
            Field(str(uuid4()), f"Case {row_id}", storage, measurement, role="characteristic")
            for row_id, _ in data
        ],
    ]
    if len({field.name for field in case_fields}) != len(case_fields):
        raise EngineError("error.duplicate_fields")
    transposed_rows = (
        [definition.id, definition.name, *(row[definition.id] for _, row in data)]
        for definition in definitions
    )
    return _write(store, name, case_fields, transposed_rows)


def pivot(
    store: Store, revision: str, index: list[str], column: str, value: str, name: str
) -> dict[str, Any]:
    item = store.get(revision)
    _check_global(store, [revision], len(item.fields))
    if (
        not isinstance(index, list)
        or not index
        or not all(isinstance(field, str) for field in index)
        or len(set(index)) != len(index)
    ):
        _fail()
    index_fields = [_field(item, field) for field in index]
    _field(item, column)
    value_field = _field(item, value)
    _check_global(store, [revision], len(index_fields) + 1)
    groups: dict[tuple[Any, ...], tuple[list[Any], dict[Any, Any]]] = {}
    categories: list[Any] = []
    for _, row in _materialize(store, revision, [*index, column, value]):
        category = row[column]
        if category is None:
            continue
        if category not in categories:
            categories.append(category)
            if len(categories) + len(index_fields) > COLUMN_LIMIT:
                raise EngineError("error.global_limit")
        key = tuple(_canonical(row[field]) for field in index)
        raw_key = [row[field] for field in index]
        _, values = groups.setdefault(key, (raw_key, {}))
        if category in values:
            raise EngineError("error.duplicate_fields")
        values[category] = row[value]
    output = [_fresh(field) for field in index_fields]
    value_fields = [_fresh(value_field, name=str(category)) for category in categories]
    if len({f.name for f in [*output, *value_fields]}) != len(output) + len(value_fields):
        raise EngineError("error.duplicate_fields")
    rows = (
        [*raw_key, *(values.get(category) for category in categories)]
        for raw_key, values in groups.values()
    )
    return _write(store, name, [*output, *value_fields], rows)


def melt(
    store: Store,
    revision: str,
    id_vars: list[str],
    value_vars: list[str],
    name: str,
    var_name: str = "variable",
    value_name: str = "value",
) -> dict[str, Any]:
    item = store.get(revision)
    _check_global(store, [revision], len(item.fields))
    if (
        not isinstance(id_vars, list)
        or not all(isinstance(field, str) for field in id_vars)
        or len(set(id_vars)) != len(id_vars)
        or not isinstance(value_vars, list)
        or not value_vars
        or not all(isinstance(field, str) for field in value_vars)
        or len(set(value_vars)) != len(value_vars)
        or not isinstance(name, str)
        or not name.strip()
        or not isinstance(var_name, str)
        or not var_name.strip()
        or not isinstance(value_name, str)
        or not value_name.strip()
        or bool(set(id_vars) & set(value_vars))
    ):
        _fail()
    id_fields = [_field(item, field) for field in id_vars]
    value_fields = [_field(item, field) for field in value_vars]

    storages = {field.storage for field in value_fields}
    if "multiple_response" in storages:
        raise EngineError("error.value_type")
    first_value_field = value_fields[0]
    shared_metadata = (
        first_value_field.role,
        first_value_field.levels,
        first_value_field.value_labels,
        first_value_field.missing_codes,
    )
    if any(
        (
            field.role,
            field.levels,
            field.value_labels,
            field.missing_codes,
        )
        != shared_metadata
        for field in value_fields[1:]
    ):
        raise EngineError("error.incompatible_melt_fields")
    if len(storages) == 1:
        storage = first_value_field.storage
        measurement = first_value_field.measurement
        if any(field.measurement != measurement for field in value_fields[1:]):
            raise EngineError("error.incompatible_melt_fields")
    elif storages <= {"int64", "float64"}:
        if any(field.measurement not in {"discrete", "continuous"} for field in value_fields):
            raise EngineError("error.incompatible_melt_fields")
        storage = "float64"
        measurement = "continuous"
    else:
        raise EngineError("error.value_type")

    total_rows = item.row_count * len(value_vars)
    if total_rows > GLOBAL_LIMIT:
        raise EngineError("error.global_limit")

    output_id_fields = [_fresh(field) for field in id_fields]
    var_field = Field(str(uuid4()), var_name, "string", "nominal")
    val_field = Field(
        str(uuid4()),
        value_name,
        storage,
        measurement,
        first_value_field.role,
        first_value_field.levels,
        dict(first_value_field.value_labels),
        first_value_field.missing_codes,
    )
    out = [*output_id_fields, var_field, val_field]
    if len({f.name for f in out}) != len(out):
        raise EngineError("error.duplicate_fields")
    if len(out) > COLUMN_LIMIT:
        raise EngineError("error.global_limit")

    def rows() -> Iterator[list[Any]]:
        for _, row in _materialize(store, revision, [*id_vars, *value_vars]):
            id_vals = [row[field_id] for field_id in id_vars]
            for vf in value_fields:
                val = row[vf.id]
                if val is not None and storage == "float64" and vf.storage == "int64":
                    promoted = float(val)
                    if int(promoted) != val:
                        raise EngineError("error.melt_precision_loss")
                    val = promoted
                yield [*id_vals, vf.name, val]

    return _write(store, name, out, rows())


def aggregate(
    store: Store,
    revision: str,
    groups: list[str],
    aggregations: list[dict[str, str]],
    name: str,
    include_missing_codes: bool = False,
) -> dict[str, Any]:
    item = store.get(revision)
    _check_global(store, [revision], len(item.fields))
    if (
        not isinstance(groups, list)
        or not all(isinstance(field, str) for field in groups)
        or len(set(groups)) != len(groups)
        or not isinstance(aggregations, list)
        or not aggregations
        or type(include_missing_codes) is not bool
    ):
        _fail()
    group_fields = [_field(item, field) for field in groups]
    parsed = []
    for spec in aggregations:
        if not isinstance(spec, dict) or set(spec) != {"field", "op", "name"}:
            _fail()
        source = _field(item, spec["field"])
        if (
            not isinstance(spec["op"], str)
            or spec["op"] not in {"count", "sum", "mean", "min", "max"}
            or not isinstance(spec["name"], str)
            or not spec["name"]
        ):
            _fail()
        if spec["op"] != "count" and source.storage not in {"int64", "float64"}:
            raise EngineError("error.value_type")
        parsed.append((source, spec["op"], spec["name"]))
    data: dict[tuple[Any, ...], tuple[list[Any], list[list[Any]]]] = {}
    for _, row in _materialize(store, revision, [*groups, *[p[0].id for p in parsed]]):
        key = tuple(_canonical(row[field]) for field in groups)
        raw_key = [row[field] for field in groups]
        _, accum = data.setdefault(key, (raw_key, [[] for _ in parsed]))
        for target, (source, _, _) in zip(accum, parsed, strict=True):
            value = row[source.id]
            kind = missing_kind(source, value)
            if kind == "null" or (kind == "coded_missing" and not include_missing_codes):
                continue
            target.append(value)
    out = [_fresh(field) for field in group_fields]
    for source, op, label in parsed:
        storage = "float64" if op == "mean" or source.storage == "float64" else "int64"
        measurement = "continuous" if storage == "float64" else "discrete"
        if op == "count":
            storage, measurement = "int64", "discrete"
        out.append(Field(str(uuid4()), label, storage, measurement))

    def results() -> Iterator[list[Any]]:
        for raw_key, buckets in data.values():
            answers: list[Any] = []
            for (_, op, _), values in zip(parsed, buckets, strict=True):
                if op == "count":
                    answers.append(len(values))
                elif not values:
                    answers.append(None)
                elif op == "sum":
                    if source.storage == "int64":
                        total = sum(values)
                        if not -(2**63) <= total < 2**63:
                            raise EngineError("error.integer_range")
                        answers.append(total)
                    else:
                        answers.append(_finite_float_sum(values))
                elif op == "mean":
                    exact_values = [_exact_number(value) for value in values]
                    try:
                        mean = float(sum(exact_values, Fraction()) / len(values))
                    except (OverflowError, ValueError) as exc:
                        raise EngineError("error.transform_domain") from exc
                    if not math.isfinite(mean):
                        raise EngineError("error.transform_domain")
                    answers.append(mean)
                elif op == "min":
                    answers.append(min(values))
                else:
                    answers.append(max(values))
            yield [*raw_key, *answers]

    return _write(store, name, out, results())


def _exact_number(value: int | float) -> Fraction:
    return Fraction(value) if isinstance(value, int) else Fraction.from_float(value)


def _finite_float_sum(values: list[int | float]) -> float:
    try:
        total = float(sum((_exact_number(value) for value in values), Fraction()))
    except (OverflowError, ValueError) as exc:
        raise EngineError("error.transform_domain") from exc
    if not math.isfinite(total):
        raise EngineError("error.transform_domain")
    return total
