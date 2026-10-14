"""Acceptance tests for RPC-managed asynchronous engine jobs."""

import io
import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

import openstat_engine.rpc as rpc
from openstat_engine.jobs import MAX_SNAPSHOT_BYTES, Jobs
from openstat_engine.rpc import MAX_FRAME, Service, serve


def request(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }


def call(service: Service, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = service.dispatch(request(method, params))
    assert response is not None
    return response


def submit(service: Service, method: str, parameters: dict[str, Any]) -> str:
    response = call(service, "jobs.submit", {"method": method, "parameters": parameters})
    assert "result" in response, response
    return response["result"]["job"]


def wait_for(service: Service, identifier: str, state: str) -> dict[str, Any]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = call(service, "jobs.status", {"job": identifier})
        assert "result" in response, response
        snapshot = response["result"]
        if snapshot["state"] == state:
            return snapshot
        if snapshot["state"] in {"succeeded", "failed", "cancelled"}:
            pytest.fail(f"job reached {snapshot['state']}: {snapshot}")
        time.sleep(0.001)
    pytest.fail(f"job did not reach {state}")


@pytest.fixture
def service(tmp_path: Path):
    instance = Service(tmp_path)
    try:
        yield instance
    finally:
        instance.jobs.close()


def test_rpc_jobs_import_filter_and_export_round_trip(service: Service, tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("score,label\n1,low\n2,high\n3,high\n", encoding="utf-8")
    imported = wait_for(
        service,
        submit(service, "dataset.importCSV", {"path": str(source)}),
        "succeeded",
    )["result"]
    score_id = next(field["id"] for field in imported["fields"] if field["name"] == "score")

    filtered = wait_for(
        service,
        submit(
            service,
            "dataset.filter",
            {
                "revision": imported["revision"],
                "condition": {"op": "ge", "field": score_id, "value": 2},
            },
        ),
        "succeeded",
    )["result"]
    assert filtered["row_count"] == 2

    destination = tmp_path.parent / f"{tmp_path.name}-filtered.csv"
    exported = wait_for(
        service,
        submit(
            service,
            "dataset.export_csv",
            {
                "revision": filtered["revision"],
                "path": str(destination),
                "overwrite": False,
            },
        ),
        "succeeded",
    )["result"]
    assert exported["rows"] == 2
    assert "field_ids" in exported["losses"]
    assert destination.read_text(encoding="utf-8") == "score,label\n2,high\n3,high\n"
    assert source.read_text(encoding="utf-8").startswith("score,label\n1,low")


@pytest.mark.parametrize(
    "method",
    ["jobs.status", "jobs.cancel", "engine.shutdown", "artifact.release", "absent"],
)
def test_rpc_job_submit_cannot_reach_unregistered_or_control_methods(
    service: Service, method: str
) -> None:
    result = call(service, "jobs.submit", {"method": method, "parameters": {}})
    assert result["error"]["message"] == "error.job_method"


def test_rpc_jobs_methods_are_advertised_and_status_is_safe(service: Service) -> None:
    hello = call(service, "engine.hello")["result"]
    assert {"jobs.submit", "jobs.status", "jobs.cancel"}.issubset(hello["methods"])
    # A missing required argument raises TypeError inside the worker. RPC exposes
    # only the stable generic key, never Python's exception text.
    identifier = submit(service, "dataset.page", {})
    state = wait_for(service, identifier, "failed")
    assert state["error"] == {"key": "error.engine_internal"}
    assert "Traceback" not in json.dumps(state)


def test_rpc_job_dataset_create_returns_json_safe_descriptor(service: Service) -> None:
    descriptor = wait_for(
        service,
        submit(
            service,
            "dataset.create",
            {
                "name": "created",
                "fields": [
                    {
                        "id": "group",
                        "name": "Group",
                        "storage": "string",
                        "measurement": "ordinal",
                        "levels": ["control", "treated"],
                    }
                ],
                "rows": [["control"], ["treated"]],
            },
        ),
        "succeeded",
    )["result"]
    assert descriptor["row_count"] == 2
    assert descriptor["fields"][0]["levels"] == ["control", "treated"]
    assert len(json.dumps(descriptor, allow_nan=False).encode("utf-8")) < MAX_FRAME


def test_rpc_job_rejects_nonfinite_and_oversized_parameters(service: Service) -> None:
    nonfinite = call(
        service,
        "jobs.submit",
        {
            "method": "dataset.create",
            "parameters": {"name": "bad", "fields": [], "rows": [[float("nan")]]},
        },
    )
    assert nonfinite["error"]["message"] == "error.job_parameters"

    oversized = call(
        service,
        "jobs.submit",
        {
            "method": "dataset.create",
            "parameters": {
                "name": "too big",
                "fields": [],
                "rows": [],
                "padding": "x" * MAX_SNAPSHOT_BYTES,
            },
        },
    )
    assert oversized["error"]["message"] == "error.job_parameters"
    assert len(json.dumps(oversized, allow_nan=False).encode("utf-8")) < MAX_FRAME


def test_rpc_job_failure_omits_source_path_and_exception_text(
    service: Service, tmp_path: Path
) -> None:
    secret = str(tmp_path / "private-source-value.csv")
    state = wait_for(
        service,
        submit(service, "dataset.importCSV", {"path": secret}),
        "failed",
    )
    assert state["error"] == {"key": "error.engine_internal"}
    assert secret not in json.dumps(state)
    assert "Traceback" not in json.dumps(state)


def test_rpc_shutdown_cancels_running_and_queued_jobs(service: Service) -> None:
    started = threading.Event()
    release = threading.Event()

    def blocked(**_: Any) -> str:
        started.set()
        release.wait(3)
        raise RuntimeError("private details")

    service.jobs._registry["dataset.page"] = blocked
    running = submit(service, "dataset.page", {})
    assert started.wait(1)
    queued = submit(service, "dataset.page", {})
    shutdown = call(service, "engine.shutdown")
    assert shutdown["result"] == {"shutdown": True}
    assert wait_for(service, queued, "cancelled")["error"] == {"key": "error.job_cancelled"}
    rejected = call(service, "jobs.submit", {"method": "dataset.page", "parameters": {}})
    assert rejected["error"]["message"] == "error.job_closed"
    release.set()
    assert wait_for(service, running, "cancelled")["error"] == {"key": "error.job_cancelled"}


@pytest.mark.parametrize("input_bytes", [b"", b"bad\r\n\r\n"])
def test_serve_eof_and_bad_frame_close_job_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, input_bytes: bytes
) -> None:
    created: list[Jobs] = []
    original = rpc.Jobs

    def capture(registry: dict[str, Any]) -> Jobs:
        manager = original(registry)
        created.append(manager)
        return manager

    monkeypatch.setattr(rpc, "Jobs", capture)
    serve(io.BytesIO(input_bytes), io.BytesIO(), tmp_path)
    assert len(created) == 1
    created[0]._worker.join(1)
    assert not created[0]._worker.is_alive()
