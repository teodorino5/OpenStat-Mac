"""Deterministic lifecycle tests for asynchronous engine jobs."""

import threading
import time

import pytest

from openstat_engine.errors import EngineError
from openstat_engine.jobs import Jobs, checkpoint


def wait_state(jobs: Jobs, identifier: str, state: str) -> dict[str, object]:
    event = threading.Event()
    deadline = time.monotonic() + 2
    while jobs.status(identifier)["state"] != state:
        assert time.monotonic() < deadline, f"job did not reach {state}"
        event.wait(0.001)
    return jobs.status(identifier)


def test_submit_copies_parameters_and_result_snapshot() -> None:
    started = threading.Event()
    release = threading.Event()
    source = {"items": [1]}

    def operation(items: list[int]) -> dict[str, list[int]]:
        started.set()
        release.wait(2)
        return {"items": items}

    jobs = Jobs({"work": operation})
    identifier = jobs.submit("work", source)["job"]
    assert started.wait(1)
    source["items"].append(2)
    release.set()
    state = wait_state(jobs, identifier, "succeeded")
    assert state["result"] == {"items": [1]}
    cast_result = jobs.status(identifier)
    cast_result["result"]["items"].append(9)  # type: ignore[index]
    assert jobs.status(identifier)["result"] == {"items": [1]}
    jobs.close()


def test_progress_cancel_and_completion_marker() -> None:
    started = threading.Event()
    resume = threading.Event()

    def operation() -> str:
        checkpoint(2, 8)
        started.set()
        resume.wait(2)
        checkpoint(3, 8)
        return "done"

    jobs = Jobs({"work": operation})
    identifier = jobs.submit("work", {})["job"]
    assert started.wait(1)
    assert jobs.status(identifier)["progress"] == {"processed": 2, "total": 8, "fraction": 0.25}
    assert jobs.cancel(identifier) == {
        "job": identifier,
        "cancel_requested": True,
        "state": "running",
    }
    resume.set()
    assert wait_state(jobs, identifier, "cancelled")["error"] == {"key": "error.job_cancelled"}
    jobs.close()

    completed = Jobs({"work": lambda: (checkpoint(4, 10), "ok")[1]})
    done = completed.submit("work", {})["job"]
    state = wait_state(completed, done, "succeeded")
    assert state["progress"] == {"processed": 4, "total": 10, "fraction": 1.0}
    completed.close()


def test_cancel_queued_and_queue_limit() -> None:
    started = threading.Event()
    release = threading.Event()

    def blocked() -> None:
        started.set()
        release.wait(2)

    jobs = Jobs({"work": blocked})
    first = jobs.submit("work", {})["job"]
    assert started.wait(1)
    queued = [jobs.submit("work", {})["job"] for _ in range(8)]
    with pytest.raises(EngineError, match="error.job_queue_full"):
        jobs.submit("work", {})
    assert jobs.cancel(queued[0])["state"] == "cancelled"
    assert jobs.status(queued[0])["state"] == "cancelled"
    release.set()
    wait_state(jobs, first, "succeeded")
    for identifier in queued[1:]:
        wait_state(jobs, identifier, "succeeded")
    jobs.close()


def test_errors_registry_boundary_and_closed_state() -> None:
    jobs = Jobs({"work": lambda: (_ for _ in ()).throw(EngineError("error.input"))})
    with pytest.raises(EngineError, match="error.job_method"):
        jobs.submit("jobs.status", {"job": "no"})
    with pytest.raises(EngineError, match="error.job_method"):
        jobs.submit("missing", {})
    identifier = jobs.submit("work", {})["job"]
    assert wait_state(jobs, identifier, "failed")["error"] == {"key": "error.input"}
    jobs.close()
    jobs.close()
    with pytest.raises(EngineError, match="error.job_closed"):
        jobs.submit("work", {})
    assert checkpoint(1, 1) is None


def test_registry_is_copied_and_requires_named_callables() -> None:
    registry = {"work": lambda: "ok"}
    jobs = Jobs(registry)
    registry.clear()
    registry["new"] = lambda: "new"
    identifier = jobs.submit("work", {})["job"]
    assert wait_state(jobs, identifier, "succeeded")["result"] == "ok"
    with pytest.raises(EngineError, match="error.job_method"):
        jobs.submit("new", {})
    jobs.close()
    for invalid in ({"jobs.status": lambda: None}, {"work": object()}, {"": lambda: None}):
        with pytest.raises(EngineError, match="error.job_registry"):
            Jobs(invalid)  # type: ignore[arg-type]


def test_parameters_require_bounded_json_safe_values() -> None:
    called = threading.Event()
    jobs = Jobs({"work": lambda value: called.set()})
    cyclic: list[object] = []
    cyclic.append(cyclic)
    deep: object = "value"
    for _ in range(66):
        deep = [deep]
    invalid = [cyclic, float("nan"), object(), {1: "non-string key"}, deep]
    for value in invalid:
        with pytest.raises(EngineError, match="error.job_parameters"):
            jobs.submit("work", {"value": value})
    with pytest.raises(EngineError, match="error.job_parameters"):
        jobs.submit("work", {"value": "x" * (7 * 1024 * 1024)})
    assert not called.is_set()
    with pytest.raises(EngineError, match="error.job_not_found"):
        jobs.status([])  # type: ignore[arg-type]
    with pytest.raises(EngineError, match="error.job_not_found"):
        jobs.cancel({})  # type: ignore[arg-type]
    jobs.close()


def test_generic_exception_is_sanitized_and_cancel_wins() -> None:
    started = threading.Event()
    release = threading.Event()

    def raises_secret() -> None:
        started.set()
        release.wait(2)
        raise RuntimeError("private row content")

    jobs = Jobs({"work": raises_secret})
    identifier = jobs.submit("work", {})["job"]
    assert started.wait(1)
    assert jobs.cancel(identifier)["state"] == "running"
    release.set()
    state = wait_state(jobs, identifier, "cancelled")
    assert state["error"] == {"key": "error.job_cancelled"}
    assert "private row content" not in repr(state)
    jobs.close()

    failed = Jobs({"work": lambda: (_ for _ in ()).throw(RuntimeError("secret"))})
    failed_id = failed.submit("work", {})["job"]
    error = wait_state(failed, failed_id, "failed")["error"]
    assert error == {"key": "error.engine_internal"}
    assert "secret" not in repr(failed.status(failed_id))
    failed.close()


def test_late_cancel_does_not_change_succeeded_job() -> None:
    jobs = Jobs({"work": lambda: "done"})
    identifier = jobs.submit("work", {})["job"]
    wait_state(jobs, identifier, "succeeded")
    assert jobs.cancel(identifier) == {
        "job": identifier,
        "cancel_requested": False,
        "state": "succeeded",
    }
    assert jobs.status(identifier)["result"] == "done"
    jobs.close()


@pytest.mark.parametrize("processed,total", [(True, 1), (1, False), (-1, 1), (2, 1), (0, -1)])
def test_invalid_checkpoint_counts_fail_with_key(processed: int, total: int) -> None:
    def operation() -> None:
        checkpoint(processed, total)

    jobs = Jobs({"work": operation})
    identifier = jobs.submit("work", {})["job"]
    state = wait_state(jobs, identifier, "failed")
    assert state["error"] == {"key": "error.job_progress"}
    jobs.close()


def test_unsupported_or_oversized_result_fails_without_exposure() -> None:
    jobs = Jobs({"work": lambda: {"value": "x" * (7 * 1024 * 1024)}})
    identifier = jobs.submit("work", {})["job"]
    state = wait_state(jobs, identifier, "failed")
    assert state["error"] == {"key": "error.job_result"}
    assert "value" not in state
    jobs.close()

    cyclic: list[object] = []
    cyclic.append(cyclic)
    invalid = Jobs({"work": lambda: cyclic})
    invalid_id = invalid.submit("work", {})["job"]
    assert wait_state(invalid, invalid_id, "failed")["error"] == {"key": "error.job_result"}
    invalid.close()


def test_close_cancels_queue_without_waiting_for_running_job() -> None:
    started = threading.Event()
    release = threading.Event()

    def cooperative() -> None:
        started.set()
        release.wait(2)
        checkpoint(1, 1)

    jobs = Jobs({"work": cooperative})
    running = jobs.submit("work", {})["job"]
    assert started.wait(1)
    queued = jobs.submit("work", {})["job"]
    jobs.close()
    assert jobs.status(queued)["state"] == "cancelled"
    release.set()
    assert wait_state(jobs, running, "cancelled")["state"] == "cancelled"


def test_close_wakes_and_stops_idle_worker() -> None:
    jobs = Jobs({"work": lambda: None})
    worker = jobs._worker
    jobs.close()
    worker.join(1)
    assert not worker.is_alive()


def test_terminal_retention_is_bounded() -> None:
    jobs = Jobs(
        {
            "success": lambda value: value,
            "failure": lambda: (_ for _ in ()).throw(EngineError("error.input")),
        }
    )
    identifiers = []
    for value in range(70):
        method = "success" if value % 2 == 0 else "failure"
        identifier = jobs.submit(method, {"value": value} if method == "success" else {})["job"]
        identifiers.append(identifier)
        wait_state(jobs, identifier, "succeeded" if method == "success" else "failed")
    assert jobs.status(identifiers[-1])["error"] == {"key": "error.input"}
    assert jobs.status(identifiers[-2])["result"] == 68
    with pytest.raises(EngineError, match="error.job_not_found"):
        jobs.status(identifiers[0])
    assert len(jobs._jobs) == 64
    jobs.close()
