import io
import json
from pathlib import Path
from typing import Any

import pytest

from openstat_engine.errors import EngineError
from openstat_engine.rpc import MAX_FRAME, Service, frame_bytes, read_frame, serve, write_frame


def request(method: str, params: Any = None) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": "original-17",
        "method": method,
        "params": params if params is not None else {},
    }


def test_frame_unicode_size_and_multiple_messages() -> None:
    first = request("engine.hello", {"text": "česky"})
    second = request("engine.shutdown")
    encoded = io.BytesIO(frame_bytes(first) + frame_bytes(second))
    assert read_frame(encoded) == first
    assert read_frame(encoded) == second
    assert read_frame(encoded) is None
    assert b"\\u010d" not in frame_bytes(first)


@pytest.mark.parametrize(
    "payload",
    [
        b"Not-A-Header\r\n\r\n{}",
        b"Content-Length: nope\r\n\r\n{}",
        b"Content-Length: 0\r\n\r\n",
        f"Content-Length: {MAX_FRAME + 1}\r\n\r\n".encode(),
        b"Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
        b"Content-Length: 2\r\n",
        b"Content-Length: 3\r\n\r\n{}",
        b"Content-Length: 1\r\n\r\n\xff",
        b"Content-Length: 1\r\n\r\n{",
        b"Content-Length: 2\r\n\r\n[]",
        b"Content-Length: 3\r\n\r\nNaN",
        b"x" * 4100 + b"\r\n\r\n",
    ],
)
def test_invalid_frames_are_rejected(payload: bytes) -> None:
    with pytest.raises(EngineError):
        read_frame(io.BytesIO(payload))


def test_hello_rejects_incompatible_major_and_does_not_claim_analyses(tmp_path: Path) -> None:
    service = Service(tmp_path)
    response = service.dispatch(request("engine.hello"))
    assert response is not None
    assert response["result"]["ui_transport"] == "arrow_ipc_file"
    assert response["result"]["max_arrow_bytes"] == 32 * 1024 * 1024
    assert response["result"]["artifact_directory"] == str(tmp_path.resolve())
    assert response is not None
    assert response["result"]["analysis_methods"] == []
    bad = service.dispatch(request("engine.hello", {"protocol_major": 5}))
    assert bad is not None and bad["error"]["message"] == "error.protocol_version"


def test_command_registry_rpc_reports_dispatchable_commands(tmp_path: Path) -> None:
    service = Service(tmp_path)

    listed = service.dispatch(request("commands.list"))
    assert listed is not None
    commands = listed["result"]
    methods = service.methods()
    assert all(command["method"] in methods for command in commands if command["enabled"])

    by_id = {command["id"]: command for command in commands}
    assert by_id["columns.compute"]["enabled"] is True
    assert by_id["columns.box_cox"]["enabled"] is False
    assert by_id["tables.melt"]["enabled"] is False
    assert all(not command["enabled"] for command in commands if command["phase"] == 1)

    categories = service.dispatch(request("commands.categories"))
    assert categories is not None
    assert categories["result"] == [
        "transform",
        "classification",
        "tables",
        "cases",
        "descriptive",
        "inference",
    ]

    filtered = service.dispatch(
        request("commands.search", {"query": "", "category": "transform", "max_phase": 0})
    )
    assert filtered is not None
    assert all(command["category"] == "transform" for command in filtered["result"])


@pytest.mark.parametrize(
    "value,code",
    [
        ({"method": "engine.hello"}, -32600),
        ({"jsonrpc": "2.0", "method": 3}, -32600),
        (request("engine.hello") | {"id": True}, -32600),
        (request("engine.hello") | {"id": []}, -32600),
        (request("absent"), -32601),
        (request("engine.hello", []), -32602),
        (request("engine.hello", {"unexpected": True}), -32602),
        (request("dataset.create", {"name": "T", "fields": [{}], "rows": []}), -32602),
    ],
)
def test_request_validation(tmp_path: Path, value: dict[str, Any], code: int) -> None:
    response = Service(tmp_path).dispatch(value)
    assert response is not None and response["error"]["code"] == code


def test_notifications_shutdown_and_eof(tmp_path: Path) -> None:
    input_stream = io.BytesIO(
        frame_bytes({"jsonrpc": "2.0", "method": "engine.hello"})
        + frame_bytes(request("engine.shutdown"))
    )
    output = io.BytesIO()
    serve(input_stream, output, tmp_path)
    output.seek(0)
    response = read_frame(output)
    assert response is not None and response["result"] == {"shutdown": True}
    assert read_frame(output) is None
    serve(io.BytesIO(), io.BytesIO(), tmp_path)
    failed = io.BytesIO()
    serve(io.BytesIO(b"bad\r\n\r\n"), failed, tmp_path)
    failed.seek(0)
    error = read_frame(failed)
    assert error is not None and error["error"]["code"] == -32700


def test_safe_file_and_internal_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = Service(tmp_path)
    missing = service.dispatch(request("project.open", {"path": str(tmp_path / "missing")}))
    assert missing is not None and missing["error"]["message"] == "error.file_io"

    def fail(**_: Any) -> None:
        raise RuntimeError("private details must not be returned")

    monkeypatch.setattr(service.store, "page", fail)
    result = service.dispatch(request("dataset.page"))
    assert result is not None and result["error"]["message"] == "error.engine_internal"
    assert "private details" not in json.dumps(result)


def test_frame_refuses_nonfinite_output() -> None:
    with pytest.raises(ValueError):
        write_frame(io.BytesIO(), {"result": float("nan")})


def test_frame_preserves_foundation_negative_zero_and_integer_precision() -> None:
    import struct

    payload = b'{"value":-0,"integer":9223372036854775807,"zero":0}'
    decoded = read_frame(io.BytesIO(f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload))
    assert decoded is not None
    assert struct.pack("<d", decoded["value"]) == b"\0\0\0\0\0\0\0\x80"
    assert type(decoded["integer"]) is int and decoded["integer"] == 2**63 - 1
    assert type(decoded["zero"]) is int and decoded["zero"] == 0
