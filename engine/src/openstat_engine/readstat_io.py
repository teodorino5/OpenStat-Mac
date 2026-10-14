"""Bounded flat-file import and export through the audited PyReadStat package."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pandas as pd
import pyarrow as pa
import pyreadstat

from .errors import EngineError
from .interchange import (
    BATCH_ROWS,
    _decode,
    _destination,
    _encode,
    _import_batches,
    _metadata,
    _schema,
)
from .model import Field
from .store import ARROW_TYPES, Revision, Store

MAX_ROWS = 100_000
MAX_COLUMNS = 1024
MAX_CELLS = 2_000_000
MAX_METADATA_CHARS = 1_000_000
MAX_SOURCE_BYTES = 128 * 1024 * 1024
_READERS = {
    "sav": pyreadstat.read_sav,
    "dta": pyreadstat.read_dta,
    "sas7bdat": pyreadstat.read_sas7bdat,
}


def _source_metadata(meta: Any, file_format: str) -> dict[str, Any]:
    """Return bounded metadata as report-only data; Store has no source metadata slot."""
    names = list(meta.column_names or [])
    labels = dict(meta.column_names_to_labels or {})
    formats = dict(meta.original_variable_types or {})
    file_text = [meta.file_label or "", meta.file_encoding or ""]
    text_size = sum(
        len(str(value))
        for value in [*file_text, *names, *labels.keys(), *labels.values(), *formats.values()]
    )
    if len(names) > MAX_COLUMNS or text_size > MAX_METADATA_CHARS:
        raise EngineError("error.readstat_limit")
    return {
        "format": file_format,
        "file_label": meta.file_label,
        "file_encoding": meta.file_encoding,
        "column_labels": labels,
        "original_variable_types": formats,
    }


def _is_date_format(file_format: str, variable_format: str) -> bool:
    fmt = variable_format.upper().strip()
    if not fmt:
        return False
    if file_format == "dta":
        return fmt.startswith("%T")
    return any(token in fmt for token in ("DATE", "TIME", "WKDAY", "MONTH", "MOYR", "QYR", "EDATE"))


def _field_for(name: str, meta: Any, file_format: str) -> Field:
    variable_format = (meta.original_variable_types or {}).get(name, "")
    if _is_date_format(file_format, variable_format):
        raise EngineError("error.readstat_date_format")
    labels_by_variable = meta.variable_value_labels or {}
    value_labels = labels_by_variable.get(name, {})
    types = meta.readstat_variable_types or {}
    native_type = str(types.get(name, "")).lower()
    missing_codes: list[Any] = []
    if (meta.missing_user_values or {}).get(name):
        raise EngineError("error.readstat_tagged_missing")
    ranges = (meta.missing_ranges or {}).get(name, [])
    for missing in ranges:
        if hasattr(missing, "lo") and hasattr(missing, "hi"):
            if missing.lo != missing.hi:
                raise EngineError("error.readstat_missing_range")
            missing = missing.lo
        elif isinstance(missing, dict):
            if not {"lo", "hi"}.issubset(missing):
                raise EngineError("error.readstat_schema")
            if missing.get("lo") != missing.get("hi"):
                raise EngineError("error.readstat_missing_range")
            missing = missing.get("lo")
        if (
            missing is None
            or isinstance(missing, bool)
            or not isinstance(missing, (str, int, float))
        ):
            raise EngineError("error.readstat_schema")
        missing_codes.append(missing)
    if native_type == "string":
        storage, measurement = "string", "nominal"
    elif native_type in {"int8", "int16", "int32", "int64"}:
        storage, measurement = "int64", "discrete"
    elif native_type in {"float", "double"}:
        storage, measurement = "float64", "continuous"
    else:
        raise EngineError("error.readstat_type")
    source_measure = str((meta.variable_measure or {}).get(name, "")).lower()
    if source_measure == "ordinal":
        measurement = "ordinal"
    elif source_measure == "nominal" and storage in {"int64", "float64"}:
        measurement = "nominal"
    elif source_measure == "scale" and storage in {"int64", "float64"}:
        measurement = "continuous" if storage == "float64" else "discrete"

    def code_text(code: Any) -> str:
        if storage == "float64":
            if isinstance(code, bool) or not isinstance(code, (int, float)):
                raise EngineError("error.readstat_schema")
            converted = float(code)
            if not math.isfinite(converted):
                raise EngineError("error.readstat_schema")
            return str(converted)
        if storage == "int64":
            if isinstance(code, bool) or not isinstance(code, (int, float)):
                raise EngineError("error.readstat_schema")
            integer = int(code)
            if integer != code or not -(2**63) <= integer < 2**63:
                raise EngineError("error.readstat_schema")
            return str(integer)
        if not isinstance(code, str):
            raise EngineError("error.readstat_schema")
        return code

    missing_codes = [code_text(code) for code in missing_codes]
    normalized_labels: dict[str, str] = {}
    for key, label in value_labels.items():
        if not isinstance(label, str):
            raise EngineError("error.readstat_schema")
        normalized_labels[code_text(key)] = label
    value_labels = normalized_labels
    if (
        value_labels
        and storage in {"int64", "float64"}
        and measurement in {"continuous", "discrete"}
    ):
        measurement = "nominal"
    levels = tuple(dict.fromkeys([*value_labels.keys(), *missing_codes]))
    if measurement == "nominal" or measurement == "ordinal":
        return Field(
            str(uuid4()),
            name,
            storage,
            measurement,
            levels=levels,
            value_labels=value_labels,
            missing_codes=tuple(missing_codes),
        )
    return Field(
        str(uuid4()),
        name,
        storage,
        measurement,
        value_labels=value_labels,
        missing_codes=tuple(missing_codes),
    )


def _import(store: Store, path: str, file_format: str) -> dict[str, Any]:
    reader = cast(Callable[..., tuple[Any, Any]], _READERS[file_format])
    source = Path(path)
    try:
        if not source.is_file():
            raise EngineError("error.readstat_file")
        if source.stat().st_size > MAX_SOURCE_BYTES:
            raise EngineError("error.readstat_limit")
        _, meta = reader(
            source,
            metadataonly=True,
            user_missing=True,
            apply_value_formats=False,
            disable_datetime_conversion=True,
            output_format="dict",
        )
        source_metadata = _source_metadata(meta, file_format)
        if getattr(meta, "mr_sets", None):
            raise EngineError("error.readstat_multiple_response")
        names = list(meta.column_names or [])
        if not names or len(names) > MAX_COLUMNS or len(set(names)) != len(names):
            raise EngineError("error.readstat_schema")
        if meta.number_rows is not None and meta.number_rows > MAX_ROWS:
            raise EngineError("error.readstat_limit")
        if len(names) * min(meta.number_rows or 0, MAX_ROWS) > MAX_CELLS:
            raise EngineError("error.readstat_limit")
        fields = tuple(_field_for(name, meta, file_format) for name in names)
        codebook_size = sum(
            len(code) + len(label) for field in fields for code, label in field.value_labels.items()
        )
        if codebook_size > MAX_METADATA_CHARS:
            raise EngineError("error.readstat_limit")
        data, read_meta = reader(
            source,
            user_missing=True,
            apply_value_formats=False,
            disable_datetime_conversion=True,
            row_limit=MAX_ROWS + 1,
            output_format="dict",
        )
        if read_meta.number_rows is not None and read_meta.number_rows > MAX_ROWS:
            raise EngineError("error.readstat_limit")
        if getattr(read_meta, "mr_sets", None):
            raise EngineError("error.readstat_multiple_response")
        if any((read_meta.missing_user_values or {}).values()):
            raise EngineError("error.readstat_tagged_missing")
        fields = tuple(_field_for(name, read_meta, file_format) for name in names)
        codebook_size = sum(
            len(code) + len(label) for field in fields for code, label in field.value_labels.items()
        )
        if codebook_size > MAX_METADATA_CHARS:
            raise EngineError("error.readstat_limit")
        rows = len(next(iter(data.values()), []))
        if rows > MAX_ROWS or rows * len(fields) > MAX_CELLS:
            raise EngineError("error.readstat_limit")
        if list(data) != names:
            raise EngineError("error.readstat_schema")
        schema = _schema(fields)

        def batches() -> Iterator[pa.Table]:
            for start in range(0, rows, BATCH_ROWS):
                stop = min(rows, start + BATCH_ROWS)
                arrays = [pa.array(range(start, stop), type=pa.int64())]
                for field in fields:
                    values: list[Any] = []
                    for value in data[field.name][start:stop]:
                        if value is None:
                            values.append(None)
                        elif field.storage == "int64":
                            try:
                                integer = int(value)
                            except (TypeError, ValueError, OverflowError) as exc:
                                raise EngineError("error.readstat_type") from exc
                            if (
                                isinstance(value, bool)
                                or integer != value
                                or not -(2**63) <= integer < 2**63
                            ):
                                raise EngineError("error.readstat_type")
                            values.append(integer)
                        elif field.storage == "float64":
                            try:
                                converted = float(value)
                            except (TypeError, ValueError, OverflowError) as exc:
                                raise EngineError("error.readstat_type") from exc
                            if not math.isfinite(converted):
                                raise EngineError("error.nonfinite")
                            values.append(converted)
                        else:
                            if not isinstance(value, str):
                                raise EngineError("error.readstat_type")
                            values.append(value)
                    arrays.append(pa.array(values, type=ARROW_TYPES[field.storage]))
                yield pa.Table.from_arrays(arrays, schema=schema)

        descriptor = _import_batches(
            store,
            _decode(_encode(_metadata(Revision("", "", source.stem, source, fields, rows)))),
            batches(),
        )
        descriptor["source_metadata"] = source_metadata
        descriptor["losses"] = ["source_metadata_not_persisted", "source_row_ids_reset"]
        if any(field.storage == "string" for field in fields):
            descriptor["losses"].append("source_null_and_empty_string_may_be_indistinguishable")
        return descriptor
    except EngineError:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        OverflowError,
        pa.ArrowException,
        pyreadstat.PyreadstatError,
        pyreadstat.ReadstatError,
    ) as exc:
        raise EngineError("error.readstat_file") from exc


def import_sav(store: Store, path: str) -> dict[str, Any]:
    return _import(store, path, "sav")


def import_dta(store: Store, path: str) -> dict[str, Any]:
    return _import(store, path, "dta")


def import_sas7bdat(store: Store, path: str) -> dict[str, Any]:
    return _import(store, path, "sas7bdat")


def _export(
    store: Store, revision: str, path: str, overwrite: bool, file_format: str
) -> dict[str, Any]:
    item = store.get(revision)
    if (
        item.row_count > MAX_ROWS
        or len(item.fields) > MAX_COLUMNS
        or item.row_count * len(item.fields) > MAX_CELLS
    ):
        raise EngineError("error.readstat_limit")
    name_limit = 32 if file_format == "dta" else 64
    if any(not f.name or len(f.name) > name_limit for f in item.fields):
        raise EngineError("error.readstat_name")
    columns: dict[str, list[Any]] = {f.name: [] for f in item.fields}
    for batch in store.iter_tables(item.id, batch_size=BATCH_ROWS):
        values = batch.to_pydict()
        for field in item.fields:
            columns[field.name].extend(values[field.id])
    labels: dict[str, dict[Any, str]] = {}
    column_labels: dict[str, str | None] = {f.name: f.name for f in item.fields}
    losses = ["field_ids", "row_ids", "context", "observation_unit", "codebook_missing_codes"]
    for field in item.fields:
        vals = columns[field.name]
        if field.storage == "multiple_response":
            raise EngineError("error.readstat_multiple_response")
        if field.storage == "int64":
            if any(value is not None and abs(value) > 2**53 for value in vals):
                raise EngineError("error.readstat_precision")
            columns[field.name] = pd.array(vals, dtype="Int64")
        elif field.storage == "float64":
            if any(value is not None and not math.isfinite(value) for value in vals):
                raise EngineError("error.nonfinite")
            columns[field.name] = pd.array(vals, dtype="Float64")
        elif field.storage == "bool":
            columns[field.name] = pd.array(vals, dtype="boolean")
        else:
            columns[field.name] = pd.array(vals, dtype="string")
        if field.value_labels:
            try:
                labels[field.name] = {
                    (
                        int(code)
                        if field.storage == "int64"
                        else float(code)
                        if field.storage == "float64"
                        else code
                    ): label
                    for code, label in field.value_labels.items()
                }
            except ValueError as exc:
                raise EngineError("error.readstat_schema") from exc
    if any(field.storage == "string" for field in item.fields):
        losses.append("null_empty_string_distinction")
    frame = pd.DataFrame(columns)
    variable_measure = {
        f.name: (
            "scale"
            if f.measurement in {"continuous", "discrete"}
            else "ordinal"
            if f.measurement == "ordinal"
            else "nominal"
        )
        for f in item.fields
    }
    with _destination(store, path, overwrite) as staging:
        try:
            if file_format == "sav":
                pyreadstat.write_sav(
                    frame,
                    staging,
                    column_labels=column_labels,
                    variable_value_labels=labels,
                    variable_measure=variable_measure,
                )
            else:
                pyreadstat.write_dta(
                    frame,
                    staging,
                    version=15,
                    column_labels=column_labels,
                    variable_value_labels=labels,
                    variable_format=None,
                )
        except (
            TypeError,
            ValueError,
            pyreadstat.PyreadstatError,
            pyreadstat.ReadstatError,
        ) as exc:
            raise EngineError("error.readstat_export") from exc
    return {"path": str(Path(path).absolute()), "rows": item.row_count, "losses": losses}


def export_sav(store: Store, revision: str, path: str, overwrite: bool = False) -> dict[str, Any]:
    return _export(store, revision, path, overwrite, "sav")


def export_dta(store: Store, revision: str, path: str, overwrite: bool = False) -> dict[str, Any]:
    return _export(store, revision, path, overwrite, "dta")
