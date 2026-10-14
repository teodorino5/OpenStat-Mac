"""Safe derived columns; global operations have explicit bounded memory contracts."""

import math
from collections.abc import Callable, Iterator
from dataclasses import replace
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from .errors import EngineError
from .jobs import checkpoint
from .model import Field, validate_fields
from .store import ARROW_TYPES, ROW_ID, Revision, Store

GLOBAL_LIMIT = 100_000
BATCH_SIZE = 8192
MAX_EXPRESSION_DEPTH = 16
MAX_EXPRESSION_NODES = 256
EXPRESSION_FUNCTIONS: tuple[dict[str, Any], ...] = (
    {"name": "negate", "arity": 1, "description": "Unary negation (-x)"},
    {"name": "abs", "arity": 1, "description": "Absolute value (|x|)"},
    {"name": "sqrt", "arity": 1, "description": "Square root (sqrt(x))"},
    {"name": "log", "arity": 1, "description": "Natural logarithm (ln(x))"},
    {"name": "exp", "arity": 1, "description": "Exponential function (e^x)"},
    {"name": "add", "arity": 2, "description": "Addition (x + y)"},
    {"name": "subtract", "arity": 2, "description": "Subtraction (x - y)"},
    {"name": "multiply", "arity": 2, "description": "Multiplication (x * y)"},
    {"name": "divide", "arity": 2, "description": "Division (x / y)"},
)


def _source(item: Revision, field: str, numeric: bool = False) -> Field:
    result = next((f for f in item.fields if f.id == field), None)
    if result is None:
        raise EngineError("error.unknown_field")
    if numeric and result.storage not in {"float64", "int64"}:
        raise EngineError("error.value_type")
    return result


def _batches(store: Store, item: Revision) -> Iterator[dict[str, list[Any]]]:
    for table in store.iter_tables(item.id, batch_size=BATCH_SIZE):
        yield table.to_pydict()


def _derive(
    store: Store,
    item: Revision,
    field: Field,
    operation: Callable[[dict[str, list[Any]], int], list[Any]],
) -> dict[str, Any]:
    definitions = (*item.fields, field)
    validate_fields(definitions)
    schema = pa.schema(
        [(ROW_ID, pa.int64()), *[(f.id, ARROW_TYPES[f.storage]) for f in definitions]]
    )
    path = store.directory / f"{uuid4()}.parquet"
    offset = 0
    try:
        with pq.ParquetWriter(path, schema) as writer:
            if item.row_count == 0:
                checkpoint(0, 0)
            for values in _batches(store, item):
                count = len(values[ROW_ID])
                checkpoint(offset, item.row_count)
                derived = operation(values, offset)
                if len(derived) != count:
                    raise EngineError("error.row_width")
                values[field.id] = [Store._value(field, value) for value in derived]
                writer.write_table(pa.Table.from_pydict(values, schema=schema))
                offset += count
                checkpoint(offset, item.row_count)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return store._record(replace(item, id=str(uuid4()), base=path, fields=definitions, edits=()))


def _coded_missing(field: Field, value: Any) -> bool:
    candidates = value if isinstance(value, list) else [str(value)]
    return any(candidate in field.missing_codes for candidate in candidates)


def _numeric(value: Any, field: Field, include_missing_codes: bool) -> Any:
    if value is None or (not include_missing_codes and _coded_missing(field, value)):
        return None
    return value


def _options(include_missing_codes: bool) -> None:
    if type(include_missing_codes) is not bool:
        raise EngineError("error.operation_options")


def _global(item: Revision) -> None:
    if item.row_count > GLOBAL_LIMIT:
        raise EngineError("error.global_limit")


def _values(store: Store, item: Revision, field: Field, include_missing_codes: bool) -> list[Any]:
    _global(item)
    return [
        _numeric(value, field, include_missing_codes)
        for batch in _batches(store, item)
        for value in batch[field.id]
    ]


def recode(
    store: Store,
    revision: str,
    field: str,
    name: str,
    mapping: list[dict[str, Any]],
    unmatched: str = "keep",
    include_missing_codes: bool = False,
    storage: str | None = None,
) -> dict[str, Any]:
    """Derive a column using typed exact-match pairs; raw null is always preserved."""
    _options(include_missing_codes)
    item = store.get(revision)
    source = _source(item, field)
    destination_storage = source.storage if storage is None else storage
    measurement = (
        source.measurement
        if destination_storage == source.storage
        else {
            "float64": "continuous",
            "int64": "discrete",
            "string": "nominal",
            "bool": "binary",
            "multiple_response": "multiple_response",
        }.get(destination_storage, "nominal")
    )
    # A recode can create new levels, so the result does not inherit a closed codebook.
    if measurement in {"binary", "ordinal"} and destination_storage != "bool":
        measurement = "nominal"
    target = Field(str(uuid4()), name, destination_storage, measurement)
    if (
        not isinstance(unmatched, str)
        or unmatched not in {"keep", "null"}
        or not isinstance(mapping, list)
        or len(mapping) > 1000
    ):
        raise EngineError("error.operation_options")
    pairs: list[tuple[Any, Any]] = []
    for pair in mapping:
        if not isinstance(pair, dict) or set(pair) != {"from", "to"} or pair["from"] is None:
            raise EngineError("error.operation_options")
        before = Store._value(source, pair["from"])
        after = Store._value(target, pair["to"])
        if any(before == existing for existing, _ in pairs):
            raise EngineError("error.operation_options")
        pairs.append((before, after))

    def apply(batch: dict[str, list[Any]], offset: int) -> list[Any]:
        output: list[Any] = []
        for value in batch[field]:
            if value is None:
                output.append(None)
            elif not include_missing_codes and _coded_missing(source, value):
                # Exclusion is explicit and cannot silently turn a coded missing value into data.
                output.append(None)
            else:
                replacement = next(
                    (after for before, after in pairs if before == value),
                    value if unmatched == "keep" else None,
                )
                output.append(replacement)
        return output

    return _derive(store, item, target, apply)


def compute(
    store: Store,
    revision: str,
    name: str,
    expression: dict[str, Any],
    include_missing_codes: bool = False,
) -> dict[str, Any]:
    """Evaluate only a validated JSON numeric expression tree, with null propagation."""
    _options(include_missing_codes)
    item = store.get(revision)
    nodes = 0
    unary = {
        "negate": lambda x: -x,
        "abs": abs,
        "sqrt": math.sqrt,
        "log": math.log,
        "exp": math.exp,
    }
    binary = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y,
    }

    def validate_node(node: Any, depth: int = 0, active: set[int] | None = None) -> None:
        nonlocal nodes
        nodes += 1
        if (
            not isinstance(node, dict)
            or depth > MAX_EXPRESSION_DEPTH
            or nodes > MAX_EXPRESSION_NODES
            or not all(isinstance(key, str) for key in node)
        ):
            raise EngineError("error.expression")
        path = set() if active is None else active
        identity = id(node)
        if identity in path:
            raise EngineError("error.expression")
        path.add(identity)
        if set(node) == {"field"} and isinstance(node["field"], str):
            _source(item, node["field"], numeric=True)
        elif set(node) == {"constant"}:
            value = node["constant"]
            if type(value) not in {int, float}:
                raise EngineError("error.expression")
            try:
                number = float(value)
            except (OverflowError, ValueError) as exc:
                raise EngineError("error.expression") from exc
            if not math.isfinite(number):
                raise EngineError("error.expression")
        elif set(node) == {"op", "args"} and isinstance(node["op"], str):
            operation, arguments = node["op"], node["args"]
            arity = 1 if operation in unary else 2 if operation in binary else 0
            if not arity or not isinstance(arguments, list) or len(arguments) != arity:
                raise EngineError("error.expression")
            for child in arguments:
                validate_node(child, depth + 1, path)
        else:
            raise EngineError("error.expression")
        path.remove(identity)

    validate_node(expression)

    def compile_node(node: Any) -> Callable[[dict[str, Any]], Any]:
        if set(node) == {"field"}:
            source = _source(item, node["field"], numeric=True)
            return lambda row: _numeric(row[source.id], source, include_missing_codes)
        if set(node) == {"constant"}:
            number = float(node["constant"])
            return lambda row: number
        operation, arguments = node["op"], node["args"]
        arity = 1 if operation in unary else 2
        children = [compile_node(child) for child in arguments]

        def evaluate(row: dict[str, Any]) -> Any:
            values = [child(row) for child in children]
            if any(value is None for value in values):
                return None
            try:
                result = unary[operation](values[0]) if arity == 1 else binary[operation](*values)
                result = float(result)
                if not math.isfinite(result):
                    raise ValueError("Nonfinite result")
                return result
            except (ValueError, OverflowError, ZeroDivisionError) as exc:
                raise EngineError("error.transform_domain") from exc

        return evaluate

    evaluate = compile_node(expression)
    target = Field(str(uuid4()), name, "float64", "continuous")
    return _derive(
        store,
        item,
        target,
        lambda batch, offset: [
            evaluate({key: values[index] for key, values in batch.items()})
            for index in range(len(batch[ROW_ID]))
        ],
    )


def expression_catalog(store: Store, revision: str, prefix: str = "") -> dict[str, Any]:
    """Return function allowlist and eligible numeric fields for expression autocomplete."""
    if not isinstance(prefix, str):
        raise EngineError("error.operation_options")
    item = store.get(revision)
    eligible_fields = [
        {"id": f.id, "name": f.name, "storage": f.storage, "measurement": f.measurement}
        for f in item.fields
        if f.storage in {"int64", "float64"} and f.role != "identifier"
    ]
    query = prefix.lower().strip()
    matched_functions = [
        fn for fn in EXPRESSION_FUNCTIONS if not query or query in fn["name"].lower()
    ]
    matched_fields = [
        f
        for f in eligible_fields
        if not query or query in f["name"].lower() or query in f["id"].lower()
    ]
    return {
        "revision": revision,
        "functions": list(matched_functions),
        "fields": list(matched_fields),
        "max_depth": MAX_EXPRESSION_DEPTH,
        "max_nodes": MAX_EXPRESSION_NODES,
    }


def rank(
    store: Store,
    revision: str,
    field: str,
    name: str,
    ties: str = "average",
    ascending: bool = True,
    include_missing_codes: bool = False,
) -> dict[str, Any]:
    _options(include_missing_codes)
    if (
        not isinstance(ties, str)
        or ties not in {"average", "min", "max", "dense", "first"}
        or type(ascending) is not bool
    ):
        raise EngineError("error.operation_options")
    item = store.get(revision)
    source = _source(item, field, numeric=True)
    values = _values(store, item, source, include_missing_codes)
    ordered = sorted(
        (i for i, v in enumerate(values) if v is not None),
        key=lambda i: values[i],
        reverse=not ascending,
    )
    output: list[Any] = [None] * len(values)
    start, dense = 0, 0
    while start < len(ordered):
        stop = start + 1
        while stop < len(ordered) and values[ordered[stop]] == values[ordered[start]]:
            stop += 1
        dense += 1
        for position in range(start, stop):
            output[ordered[position]] = {
                "average": (start + 1 + stop) / 2,
                "min": start + 1,
                "max": stop,
                "dense": dense,
                "first": position + 1,
            }[ties]
        start = stop
    target = Field(str(uuid4()), name, "float64", "ordinal")
    return _derive(
        store, item, target, lambda batch, offset: output[offset : offset + len(batch[ROW_ID])]
    )


def lag(
    store: Store,
    revision: str,
    field: str,
    name: str,
    steps: int = 1,
    direction: str = "lag",
    include_missing_codes: bool = False,
) -> dict[str, Any]:
    """Shift in current row order, with null padding and an explicit bounded look-up."""
    _options(include_missing_codes)
    if (
        type(steps) is not int
        or not 1 <= steps <= GLOBAL_LIMIT
        or not isinstance(direction, str)
        or direction not in {"lag", "lead"}
    ):
        raise EngineError("error.operation_options")
    item = store.get(revision)
    source = _source(item, field)
    values = _values(store, item, source, include_missing_codes)
    target = replace(source, id=str(uuid4()), name=name, role="characteristic")
    shift = -steps if direction == "lag" else steps
    output = [
        values[i + shift] if 0 <= i + shift < len(values) else None for i in range(len(values))
    ]
    return _derive(
        store, item, target, lambda batch, offset: output[offset : offset + len(batch[ROW_ID])]
    )


def standardize(
    store: Store,
    revision: str,
    field: str,
    name: str,
    ddof: int = 1,
    include_missing_codes: bool = False,
) -> dict[str, Any]:
    _options(include_missing_codes)
    if type(ddof) is not int or ddof not in {0, 1}:
        raise EngineError("error.operation_options")
    item = store.get(revision)
    source = _source(item, field, numeric=True)
    values = _values(store, item, source, include_missing_codes)
    observed = [value for value in values if value is not None]
    if len(observed) <= ddof:
        raise EngineError("error.zero_variance")
    try:
        # Center before scaling to retain small differences between large integers or floats.
        # Integer subtraction stays exact. The float midpoint avoids overflow for opposite signs.
        origin = observed[0] if source.storage == "int64" else min(observed) / 2 + max(observed) / 2
        shifted = [value - origin for value in observed]
        scale = max(abs(value) for value in shifted)
        if scale == 0:
            raise EngineError("error.zero_variance")
        scaled = [value / scale for value in shifted]
        center = math.fsum(scaled) / len(scaled)
        spread = math.sqrt(
            math.fsum((value - center) ** 2 for value in scaled) / (len(scaled) - ddof)
        )
        if spread == 0:
            raise EngineError("error.zero_variance")
        output = [
            None if value is None else ((value - origin) / scale - center) / spread
            for value in values
        ]
    except (OverflowError, ValueError) as exc:
        raise EngineError("error.transform_domain") from exc
    target = Field(str(uuid4()), name, "float64", "continuous")
    return _derive(
        store, item, target, lambda batch, offset: output[offset : offset + len(batch[ROW_ID])]
    )


def duplicates(
    store: Store,
    revision: str,
    fields: list[str],
    name: str,
    keep: str = "first",
) -> dict[str, Any]:
    """Flag exact duplicates; raw nulls compare equal and coded missing values stay literal."""
    item = store.get(revision)
    _global(item)
    if (
        not isinstance(fields, list)
        or not fields
        or not all(isinstance(f, str) for f in fields)
        or len(set(fields)) != len(fields)
    ):
        raise EngineError("error.operation_options")
    for field in fields:
        _source(item, field)
    if not isinstance(keep, str) or keep not in {"first", "last", "none"}:
        raise EngineError("error.operation_options")
    keys = [
        tuple(tuple(value) if isinstance(value, list) else value for value in row)
        for batch in _batches(store, item)
        for row in zip(*(batch[field] for field in fields), strict=True)
    ]
    output = [False] * len(keys)
    seen: set[tuple[Any, ...]] = set()
    indices = range(len(keys) - 1, -1, -1) if keep == "last" else range(len(keys))
    for i in indices:
        output[i] = keys[i] in seen
        seen.add(keys[i])
    if keep == "none":
        repeated = {key for i, key in enumerate(keys) if output[i]}
        output = [key in repeated for key in keys]
    target = Field(str(uuid4()), name, "bool", "binary")
    return _derive(
        store, item, target, lambda batch, offset: output[offset : offset + len(batch[ROW_ID])]
    )
