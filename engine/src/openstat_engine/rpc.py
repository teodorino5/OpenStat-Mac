"""JSON-RPC 2.0 on private framed pipes. Logging never uses stdout."""

import io
import json
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, BinaryIO, cast

from . import (
    __version__,
    classification,
    columns,
    interchange,
    outliers,
    readstat_io,
    structure,
    tables,
    views,
    xlsx,
)
from .errors import EngineError
from .jobs import Jobs
from .store import Store

MAX_FRAME = 8 * 1024 * 1024
MAX_HEADER = 4096


def read_frame(stream: BinaryIO) -> dict[str, Any] | None:
    first = stream.readline(MAX_HEADER + 1)
    if not first:
        return None
    header = first
    while not header.endswith(b"\r\n\r\n"):
        if len(header) > MAX_HEADER:
            raise EngineError("error.rpc_header", -32700)
        line = stream.readline(MAX_HEADER + 1)
        if not line:
            raise EngineError("error.rpc_truncated", -32700)
        header += line
    headers: dict[bytes, bytes] = {}
    for line in header[:-4].split(b"\r\n"):
        key, separator, value = line.partition(b":")
        key = key.strip().lower()
        if not separator or key in headers:
            raise EngineError("error.rpc_header", -32700)
        headers[key] = value.strip()
    try:
        length = int(headers[b"content-length"])
    except (ValueError, KeyError) as exc:
        raise EngineError("error.rpc_header", -32700) from exc
    if not 0 < length <= MAX_FRAME:
        raise EngineError("error.rpc_size", -32700)
    payload = bytearray()
    while len(payload) < length:
        block = stream.read(length - len(payload))
        if not block:
            raise EngineError("error.rpc_truncated", -32700)
        payload.extend(block)
    try:

        def reject_constant(_: str) -> None:
            raise ValueError("nonfinite JSON")

        # Foundation may emit a floating negative zero as the valid JSON token -0.
        # Keep that sign while parsing every other integer without a float conversion.
        value = json.loads(
            payload,
            parse_constant=reject_constant,
            parse_int=lambda token: -0.0 if token == "-0" else int(token),
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise EngineError("error.rpc_json", -32700) from exc
    if not isinstance(value, dict):
        raise EngineError("error.rpc_request", -32600)
    return cast(dict[str, Any], value)


def write_frame(stream: BinaryIO, value: dict[str, Any]) -> None:
    data = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    stream.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
    stream.write(data)
    stream.flush()


class Service:
    def __init__(self, directory: Path) -> None:
        self.store = Store(directory)
        self.shutdown = False
        registry = self.methods()
        self.jobs = Jobs(
            {
                name: operation
                for name, operation in registry.items()
                if not name.startswith(("engine.", "jobs.")) and name != "artifact.release"
            }
        )

    def hello(self, protocol_major: int = 1) -> dict[str, Any]:
        if protocol_major != 1:
            raise EngineError("error.protocol_version")
        return {
            "protocol_major": 1,
            "protocol_minor": 1,
            "engine_version": __version__,
            "methods": sorted(self.methods()),
            "analysis_methods": [],
            "bulk": ["arrow_ipc_file"],
            "max_page_rows": 512,
            "max_inline_rows": 100000,
            "ui_transport": "arrow_ipc_file",
            "artifact_directory": str(self.store.directory.resolve()),
            "max_arrow_bytes": 32 * 1024 * 1024,
        }

    def stop(self) -> dict[str, bool]:
        self.shutdown = True
        self.jobs.close()
        return {"shutdown": True}

    def methods(self) -> dict[str, Callable[..., Any]]:
        return {
            "engine.hello": self.hello,
            "engine.shutdown": self.stop,
            "dataset.create": self.store.create,
            "dataset.extend": self.store.extend,
            "dataset.page": self.store.page,
            "dataset.edit": self.store.edit,
            "dataset.metadata": self.store.metadata,
            "dataset.importCSV": self.store.import_csv,
            "project.save": self.store.save,
            "project.open": self.store.open,
            "artifact.release": self.store.release,
            **(
                {
                    "jobs.submit": self.jobs.submit,
                    "jobs.status": self.jobs.status,
                    "jobs.cancel": self.jobs.cancel,
                }
                if hasattr(self, "jobs")
                else {}
            ),
            "dataset.import_xlsx": partial(xlsx.import_xlsx, self.store),
            "dataset.export_xlsx": partial(xlsx.export_xlsx, self.store),
            "dataset.import_sav": partial(readstat_io.import_sav, self.store),
            "dataset.import_dta": partial(readstat_io.import_dta, self.store),
            "dataset.import_sas7bdat": partial(readstat_io.import_sas7bdat, self.store),
            "dataset.export_sav": partial(readstat_io.export_sav, self.store),
            "dataset.export_dta": partial(readstat_io.export_dta, self.store),
            **{
                f"tables.{name}": partial(getattr(tables, name), self.store)
                for name in ("stack", "join", "transpose", "pivot", "aggregate")
            },
            "dataset.select": partial(views.select, self.store),
            "dataset.filter": partial(views.filter_cases, self.store),
            "dataset.sort": partial(views.sort_cases, self.store),
            "dataset.weights": partial(views.weights, self.store),
            "columns.outliers": partial(outliers.flag, self.store),
            "dataset.delete_cases": partial(structure.delete_cases, self.store),
            "dataset.drop_fields": partial(structure.drop_fields, self.store),
            "classification.categories": partial(classification.categories, self.store),
            "classification.intervals": partial(classification.intervals, self.store),
            "dataset.contingency": partial(classification.contingency, self.store),
            "dataset.missing_audit": partial(classification.missing_audit, self.store),
            **{
                f"columns.{name}": partial(getattr(columns, name), self.store)
                for name in ("recode", "compute", "rank", "lag", "standardize", "duplicates")
            },
            **{
                f"dataset.{name}": partial(getattr(interchange, name), self.store)
                for name in (
                    "export_csv",
                    "import_parquet",
                    "export_parquet",
                    "import_json",
                    "export_json",
                    "import_sqlite",
                    "export_sqlite",
                )
            },
        }

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any] | None:
        identifier = request.get("id")
        if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            return self.error(None, -32600, "error.rpc_request")
        if isinstance(identifier, bool) or not isinstance(
            identifier, (str, int, float, type(None))
        ):
            return self.error(None, -32600, "error.rpc_request")
        params = request.get("params", {})
        methods = self.methods()
        try:
            if request["method"] not in methods:
                raise EngineError("error.rpc_method", -32601)
            if not isinstance(params, dict):
                raise EngineError("error.rpc_params", -32602)
            result = methods[request["method"]](**params)
            if (
                len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                > MAX_FRAME - 1024
            ):
                raise EngineError("error.rpc_size")
            response = {"jsonrpc": "2.0", "id": identifier, "result": result}
        except EngineError as exc:
            response = self.error(identifier, exc.code, exc.key)
        except (TypeError, ValueError, KeyError, OverflowError):
            response = self.error(identifier, -32602, "error.rpc_params")
        except OSError:
            response = self.error(identifier, -32002, "error.file_io")
        except Exception:
            response = self.error(identifier, -32603, "error.engine_internal")
        return response if "id" in request else None

    @staticmethod
    def error(identifier: Any, code: int, key: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": identifier,
            "error": {"code": code, "message": key, "data": {"message_key": key}},
        }


def serve(source: BinaryIO, destination: BinaryIO, directory: Path) -> None:
    service = Service(directory)
    try:
        while not service.shutdown:
            try:
                request = read_frame(source)
            except EngineError as exc:
                write_frame(destination, service.error(None, exc.code, exc.key))
                # Framing is no longer trustworthy; close instead of guessing a boundary.
                return
            if request is None:
                return
            response = service.dispatch(request)
            if response is not None:
                write_frame(destination, response)
    finally:
        service.jobs.close()


def frame_bytes(value: dict[str, Any]) -> bytes:
    stream = io.BytesIO()
    write_frame(stream, value)
    return stream.getvalue()
