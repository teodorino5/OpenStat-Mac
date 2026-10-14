"""Standalone command-line access to the typed OpenStat data engine."""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from . import __version__, classification, columns, interchange, readstat_io, views, xlsx
from .errors import EngineError
from .rpc import Service, serve
from .store import Store

PARAMETERS_LIMIT = 1024 * 1024
IMPORT_FORMATS = {"csv", "tsv", "json", "parquet", "sqlite", "xlsx", "sav", "dta", "sas7bdat"}
EXPORT_FORMATS = IMPORT_FORMATS - {"sas7bdat"}
TRANSFORM_KEYS: dict[str, set[str]] = {
    "columns.recode": {"field", "name", "mapping", "unmatched", "include_missing_codes", "storage"},
    "columns.compute": {"name", "expression", "include_missing_codes"},
    "columns.rank": {"field", "name", "ties", "ascending", "include_missing_codes"},
    "columns.lag": {"field", "name", "steps", "direction", "include_missing_codes"},
    "columns.standardize": {"field", "name", "ddof", "include_missing_codes"},
    "columns.duplicates": {"fields", "name", "keep"},
    "classification.categories": {"source", "output", "mapping", "unmatched"},
    "classification.intervals": {"source", "output", "classes", "unmatched"},
    "dataset.filter": {"condition"},
    "dataset.sort": {"keys", "nulls"},
}


def _format_from_path(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    aliases = {"tab": "tsv", "txt": "csv", "db": "sqlite", "db3": "sqlite"}
    return aliases.get(suffix, suffix)


def _import_dataset(
    store: Store,
    source: Path,
    format_name: str,
    delimiter: str | None,
    decimal_point: str,
    sheet: str | None,
) -> dict[str, Any]:
    if format_name == "auto":
        format_name = _format_from_path(source)
    if format_name not in IMPORT_FORMATS:
        raise EngineError("error.cli_format")
    if sheet is not None and format_name != "xlsx":
        raise EngineError("error.cli_format")
    if delimiter is not None and format_name not in {"csv", "tsv"}:
        raise EngineError("error.cli_format")
    if decimal_point != "." and format_name not in {"csv", "tsv"}:
        raise EngineError("error.cli_format")
    if format_name == "csv":
        return store.import_csv(str(source), delimiter or ",", decimal_point)
    if format_name == "tsv":
        return store.import_csv(str(source), delimiter or "\t", decimal_point)
    if format_name == "json":
        return interchange.import_json(store, str(source))
    if format_name == "parquet":
        return interchange.import_parquet(store, str(source))
    if format_name == "sqlite":
        return interchange.import_sqlite(store, str(source))
    if format_name == "xlsx":
        return xlsx.import_xlsx(store, str(source), sheet)
    if format_name == "sav":
        return readstat_io.import_sav(store, str(source))
    if format_name == "dta":
        return readstat_io.import_dta(store, str(source))
    return readstat_io.import_sas7bdat(store, str(source))


def _export_dataset(
    store: Store,
    revision: str,
    destination: Path,
    format_name: str,
    delimiter: str | None,
    decimal_point: str,
    overwrite: bool,
) -> dict[str, Any]:
    if format_name == "csv":
        return interchange.export_csv(
            store, revision, str(destination), delimiter or ",", decimal_point, overwrite
        )
    if format_name == "tsv":
        return interchange.export_csv(
            store, revision, str(destination), delimiter or "\t", decimal_point, overwrite
        )
    if format_name == "json":
        return interchange.export_json(store, revision, str(destination), overwrite)
    if format_name == "parquet":
        return interchange.export_parquet(store, revision, str(destination), overwrite)
    if format_name == "sqlite":
        return interchange.export_sqlite(store, revision, str(destination), overwrite)
    if format_name == "xlsx":
        return xlsx.export_xlsx(store, revision, str(destination), overwrite)
    if format_name == "sav":
        return readstat_io.export_sav(store, revision, str(destination), overwrite)
    if format_name == "dta":
        return readstat_io.export_dta(store, revision, str(destination), overwrite)
    raise EngineError("error.cli_format")


def _parameters(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            raw = stream.read(PARAMETERS_LIMIT + 1)
        if len(raw) > PARAMETERS_LIMIT:
            raise EngineError("error.cli_parameters")

        def reject_constant(_: str) -> None:
            raise EngineError("error.cli_parameters")

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise EngineError("error.cli_parameters")
                result[key] = value
            return result

        value = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)
    except EngineError:
        raise
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise EngineError("error.cli_parameters") from exc
    if not isinstance(value, dict) or "revision" in value:
        raise EngineError("error.cli_parameters")
    _validate_json(value)
    return value


def _validate_json(value: Any, depth: int = 0) -> None:
    if depth > 32:
        raise EngineError("error.cli_parameters")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EngineError("error.cli_parameters")
        return
    if isinstance(value, list):
        if len(value) > 100_000:
            raise EngineError("error.cli_parameters")
        for item in value:
            _validate_json(item, depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 10_000 or not all(isinstance(key, str) for key in value):
            raise EngineError("error.cli_parameters")
        for item in value.values():
            _validate_json(item, depth + 1)
        return
    raise EngineError("error.cli_parameters")


def _transform(
    store: Store, revision: str, method: str, parameters: dict[str, Any]
) -> dict[str, Any]:
    allowed = TRANSFORM_KEYS.get(method)
    if allowed is None:
        raise EngineError("error.cli_method")
    if set(parameters) - allowed:
        raise EngineError("error.cli_parameters")
    operations: dict[str, Callable[..., dict[str, Any]]] = {
        "columns.recode": partial(columns.recode, store, revision),
        "columns.compute": partial(columns.compute, store, revision),
        "columns.rank": partial(columns.rank, store, revision),
        "columns.lag": partial(columns.lag, store, revision),
        "columns.standardize": partial(columns.standardize, store, revision),
        "columns.duplicates": partial(columns.duplicates, store, revision),
        "classification.categories": partial(classification.categories, store, revision),
        "classification.intervals": partial(classification.intervals, store, revision),
        "dataset.filter": partial(views.filter_cases, store, revision),
        "dataset.sort": partial(views.sort_cases, store, revision),
    }
    try:
        return operations[method](**parameters)
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        raise EngineError("error.cli_parameters") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openstat")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve")
    commands.add_parser("methods", help="list registered Phase 0 RPC methods")

    imported = commands.add_parser("import", help="import a data file into an OpenStat project")
    imported.add_argument("source", type=Path)
    imported.add_argument("destination", type=Path)
    imported.add_argument("--format", choices=["auto", *sorted(IMPORT_FORMATS)], default="auto")
    imported.add_argument("--delimiter")
    imported.add_argument("--decimal-point", default=".")
    imported.add_argument("--sheet")

    inspected = commands.add_parser("inspect")
    inspected.add_argument("project", type=Path)
    inspected.add_argument("--offset", type=int, default=0)
    inspected.add_argument("--limit", type=int, default=10)

    exported = commands.add_parser("export", help="export a project dataset")
    exported.add_argument("project", type=Path)
    exported.add_argument("destination", type=Path)
    exported.add_argument("--format", choices=sorted(EXPORT_FORMATS), required=True)
    exported.add_argument("--overwrite", action="store_true")
    exported.add_argument("--delimiter")
    exported.add_argument("--decimal-point", default=".")

    transformed = commands.add_parser("transform", help="apply one safe registered operation")
    transformed.add_argument("project", type=Path)
    transformed.add_argument("destination", type=Path)
    transformed.add_argument("--method", required=True)
    transformed.add_argument("--parameters-file", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    with tempfile.TemporaryDirectory(prefix="openstat-") as cache:
        directory = Path(cache)
        if arguments.command == "serve":
            serve(sys.stdin.buffer, sys.stdout.buffer, directory)
            return 0
        store = Store(directory)
        try:
            if arguments.command == "methods":
                methods = sorted(Service(directory).methods())
                result: dict[str, Any] = {"methods": methods, "analysis_methods": []}
            elif arguments.command == "import":
                result = _import_dataset(
                    store,
                    arguments.source,
                    arguments.format,
                    arguments.delimiter,
                    arguments.decimal_point,
                    arguments.sheet,
                )
                store.save(result["revision"], str(arguments.destination))
            elif arguments.command == "inspect":
                result = store.open(str(arguments.project))
                result["preview"] = store.page(
                    result["revision"], arguments.offset, arguments.limit
                )
            elif arguments.command == "export":
                result = store.open(str(arguments.project))
                if arguments.destination.resolve().is_relative_to(arguments.project.resolve()):
                    raise EngineError("error.export_path")
                if arguments.delimiter is not None and arguments.format not in {"csv", "tsv"}:
                    raise EngineError("error.cli_format")
                if arguments.decimal_point != "." and arguments.format not in {"csv", "tsv"}:
                    raise EngineError("error.cli_format")
                result = _export_dataset(
                    store,
                    result["revision"],
                    arguments.destination,
                    arguments.format,
                    arguments.delimiter,
                    arguments.decimal_point,
                    arguments.overwrite,
                )
            else:
                destination = arguments.destination.resolve()
                project = arguments.project.resolve()
                if arguments.destination.exists() or arguments.destination.is_symlink():
                    raise EngineError("error.export_exists")
                if destination == project or destination.is_relative_to(project):
                    raise EngineError("error.project_path")
                source = store.open(str(arguments.project))
                parameters = _parameters(arguments.parameters_file)
                result = _transform(store, source["revision"], arguments.method, parameters)
                store.save(result["revision"], str(arguments.destination))
        except EngineError as exc:
            print(json.dumps({"error": exc.key}), file=sys.stderr)
            return 1
        except OSError:
            print(json.dumps({"error": "error.file_io"}), file=sys.stderr)
            return 1
        except Exception:
            print(json.dumps({"error": "error.engine_internal"}), file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
