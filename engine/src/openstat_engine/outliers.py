"""Exact Tukey outlier classification with bounded global scans."""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any
from uuid import uuid4

from . import columns
from .errors import EngineError
from .model import Field
from .store import Store

GLOBAL_LIMIT = columns.GLOBAL_LIMIT


def _fraction(value: int | float) -> Fraction:
    return Fraction(value) if isinstance(value, int) else Fraction.from_float(value)


def _multiplier(value: Any) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EngineError("error.operation_options")
    if isinstance(value, float) and not math.isfinite(value):
        raise EngineError("error.operation_options")
    return _fraction(value)


def _type7(values: list[Fraction], probability: Fraction) -> Fraction:
    position = (len(values) - 1) * probability
    lower = position.numerator // position.denominator
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] + fraction * (values[upper] - values[lower])


def flag(
    store: Store,
    revision: str,
    field: str,
    name: str,
    inner: float = 1.5,
    outer: float = 3.0,
    include_missing_codes: bool = False,
) -> dict[str, Any]:
    """Append 0/1/2 Tukey outlier severity. Null source values stay null."""
    if type(include_missing_codes) is not bool or not isinstance(name, str) or not name.strip():
        raise EngineError("error.operation_options")
    inner_value, outer_value = _multiplier(inner), _multiplier(outer)
    if inner_value < 0 or outer_value < inner_value:
        raise EngineError("error.operation_options")
    item = store.get(revision)
    if item.row_count > GLOBAL_LIMIT:
        raise EngineError("error.global_limit")
    source = next((definition for definition in item.fields if definition.id == field), None)
    if source is None:
        raise EngineError("error.unknown_field")
    if source.storage not in {"int64", "float64"}:
        raise EngineError("error.value_type")

    eligible: list[Fraction] = []
    for table in store.iter_tables(revision, [field]):
        for value in table[field].to_pylist():
            if value is None or (
                not include_missing_codes and columns._coded_missing(source, value)
            ):
                continue
            if isinstance(value, float) and not math.isfinite(value):
                raise EngineError("error.nonfinite")
            eligible.append(_fraction(value))
    eligible.sort()
    if eligible:
        q1 = _type7(eligible, Fraction(1, 4))
        q3 = _type7(eligible, Fraction(3, 4))
        spread = q3 - q1
        inner_low, inner_high = q1 - inner_value * spread, q3 + inner_value * spread
        outer_low, outer_high = q1 - outer_value * spread, q3 + outer_value * spread
    else:
        inner_low = inner_high = outer_low = outer_high = Fraction(0)

    target = Field(
        str(uuid4()),
        name,
        "int64",
        "nominal",
        value_labels={"0": "Not an outlier", "1": "Mild outlier", "2": "Extreme outlier"},
    )

    def classify(batch: dict[str, list[Any]], offset: int) -> list[int | None]:
        result: list[int | None] = []
        for value in batch[field]:
            if value is None or (
                not include_missing_codes and columns._coded_missing(source, value)
            ):
                result.append(None)
                continue
            exact = _fraction(value)
            if exact < outer_low or exact > outer_high:
                result.append(2)
            elif exact < inner_low or exact > inner_high:
                result.append(1)
            else:
                result.append(0)
        return result

    return columns._derive(store, item, target, classify)
