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


def _brent_minimize(
    f: Callable[[float], float],
    a: float = -3.0,
    b: float = 3.0,
    tol: float = 1e-7,
    max_iter: int = 500,
) -> float:
    c = (3.0 - math.sqrt(5.0)) / 2.0
    x = w = v = a + c * (b - a)
    d = e = 0.0
    fx = f(x)
    fw = fv = fx

    for _ in range(max_iter):
        mid = 0.5 * (a + b)
        tol1 = tol * abs(x) + 1e-10
        tol2 = 2.0 * tol1

        if abs(x - mid) <= (tol2 - 0.5 * (b - a)):
            break

        p = q = r = 0.0
        if abs(e) > tol1:
            r = (x - w) * (fx - fv)
            q = (x - v) * (fx - fw)
            p = (x - v) * q - (x - w) * r
            q = 2.0 * (q - r)
            if q > 0.0:
                p = -p
            q = abs(q)
            r = e
            e = d

        if abs(p) < abs(0.5 * q * r) and p > q * (a - x) and p < q * (b - x):
            d = p / q
            u = x + d
            if (u - a) < tol2 or (b - u) < tol2:
                d = tol1 if (mid - x) >= 0 else -tol1
        else:
            e = (b - x) if (x < mid) else (a - x)
            d = c * e

        u = x + (d if abs(d) >= tol1 else (tol1 if d > 0 else -tol1))
        fu = f(u)

        if fu <= fx:
            if u >= x:
                a = x
            else:
                b = x
            v, fv = w, fw
            w, fw = x, fx
            x, fx = u, fu
        else:
            if u < x:
                a = u
            else:
                b = u
            if fu <= fw or w == x:
                v, fv = w, fw
                w, fw = u, fu
            elif fu <= fv or v == x or v == w:
                v, fv = u, fu

    return x


def box_cox(
    store: Store,
    revision: str,
    field: str,
    name: str,
    lmbda: float | int | None = None,
    include_missing_codes: bool = False,
) -> dict[str, Any]:
    """Box-Cox power transformation with fixed or MLE-fitted parameter lambda for positive data."""
    _options(include_missing_codes)
    if lmbda is not None:
        if (
            not isinstance(lmbda, (int, float))
            or isinstance(lmbda, bool)
            or not math.isfinite(lmbda)
        ):
            raise EngineError("error.operation_options")
    item = store.get(revision)
    source = _source(item, field, numeric=True)
    values = _values(store, item, source, include_missing_codes)
    observed = [v for v in values if v is not None]
    if len(observed) < 2 or min(observed) == max(observed):
        raise EngineError("error.zero_variance")
    if any(v <= 0 for v in observed):
        raise EngineError("error.transform_domain")

    if lmbda is not None:
        optimal_lmbda = float(lmbda)
    else:
        n = len(observed)
        log_observed = [math.log(v) for v in observed]
        sum_log = math.fsum(log_observed)

        def _nllf(param: float) -> float:
            try:
                if abs(param) < 1e-10:
                    trans = [log_y * (1.0 + 0.5 * param * log_y) for log_y in log_observed]
                else:
                    trans = [(y**param - 1.0) / param for y in observed]
                mean = math.fsum(trans) / n
                var = math.fsum((t - mean) ** 2 for t in trans) / n
                if var <= 0:
                    return float("inf")
                return 0.5 * n * math.log(var) - (param - 1.0) * sum_log
            except (OverflowError, ValueError):
                return float("inf")

        optimal_lmbda = _brent_minimize(_nllf, -3.0, 3.0)

    try:
        if abs(optimal_lmbda) < 1e-10:
            output = [None if v is None else math.log(v) for v in values]
        else:
            output = [
                None if v is None else (v**optimal_lmbda - 1.0) / optimal_lmbda
                for v in values
            ]
    except (OverflowError, ValueError) as exc:
        raise EngineError("error.transform_domain") from exc

    target = Field(str(uuid4()), name, "float64", "continuous")
    derived = _derive(
        store, item, target, lambda batch, offset: output[offset : offset + len(batch[ROW_ID])]
    )
    return derived | {"lambda": optimal_lmbda}


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
