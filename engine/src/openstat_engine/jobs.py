"""Bounded asynchronous jobs for explicitly registered engine operations."""

from __future__ import annotations

import json
import math
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .errors import EngineError

_context = threading.local()
MAX_SNAPSHOT_BYTES = 7 * 1024 * 1024
MAX_SNAPSHOT_DEPTH = 64


def _snapshot(value: Any, error_key: str) -> Any:
    """Validate bounded JSON data and return detached JSON-compatible values."""
    active: set[int] = set()

    def validate(item: Any, depth: int) -> None:
        if depth > MAX_SNAPSHOT_DEPTH:
            raise EngineError(error_key)
        if item is None or type(item) in {str, bool, int}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise EngineError(error_key)
            return
        if type(item) not in {dict, list}:
            raise EngineError(error_key)
        identity = id(item)
        if identity in active:
            raise EngineError(error_key)
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise EngineError(error_key)
                    validate(child, depth + 1)
            else:
                for child in item:
                    validate(child, depth + 1)
        finally:
            active.remove(identity)

    try:
        validate(value, 0)
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        data = encoded.encode("utf-8")
        if len(data) > MAX_SNAPSHOT_BYTES:
            raise EngineError(error_key)
        return json.loads(data)
    except EngineError:
        raise
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise EngineError(error_key) from exc


def checkpoint(processed: int, total: int) -> None:
    """Report real work progress and raise when active job was cancelled."""
    job = getattr(_context, "job", None)
    if job is None:
        return
    if (
        type(processed) is not int
        or type(total) is not int
        or total < 0
        or not 0 <= processed <= total
    ):
        raise EngineError("error.job_progress")
    with job.lock:
        if job.cancel_requested:
            raise EngineError("error.job_cancelled")
        job.progress = {"processed": processed, "total": total}


@dataclass
class _Job:
    identifier: str
    method: str
    operation: Callable[..., Any]
    parameters: dict[str, Any]
    state: str = "queued"
    progress: dict[str, int] | None = None
    result: Any = None
    error: str | None = None
    cancel_requested: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock)


class Jobs:
    """Run only copied registry callables, with one daemon worker and bounded state."""

    def __init__(self, registry: dict[str, Callable[..., Any]]) -> None:
        if type(registry) is not dict:
            raise EngineError("error.job_registry")
        self._registry = registry.copy()
        if any(
            not isinstance(name, str)
            or not name
            or name.startswith("jobs.")
            or not callable(operation)
            for name, operation in self._registry.items()
        ):
            raise EngineError("error.job_registry")
        self._condition = threading.Condition(threading.RLock())
        self._jobs: dict[str, _Job] = {}
        self._order: deque[str] = deque()
        self._queue: deque[str] = deque()
        self._closed = False
        self._worker = threading.Thread(target=self._run, name="openstat-jobs", daemon=True)
        self._worker.start()

    def submit(self, method: str, parameters: dict[str, Any]) -> dict[str, str]:
        if type(method) is not str or method.startswith("jobs."):
            raise EngineError("error.job_method")
        operation = self._registry.get(method)
        if operation is None:
            raise EngineError("error.job_method")
        if type(parameters) is not dict:
            raise EngineError("error.job_parameters")
        copied = _snapshot(parameters, "error.job_parameters")
        with self._condition:
            if self._closed:
                raise EngineError("error.job_closed")
            if len(self._queue) >= 8:
                raise EngineError("error.job_queue_full")
            identifier = str(uuid4())
            job = _Job(identifier, method, operation, copied)
            self._jobs[identifier] = job
            self._order.append(identifier)
            self._queue.append(identifier)
            self._condition.notify()
            return {"job": identifier}

    def status(self, job: str) -> dict[str, Any]:
        if type(job) is not str:
            raise EngineError("error.job_not_found")
        with self._condition:
            item = self._jobs.get(job)
            if item is None:
                raise EngineError("error.job_not_found")
            with item.lock:
                result: dict[str, Any] = {"job": job, "state": item.state}
                if item.progress is not None:
                    progress: dict[str, int | float] = dict(item.progress)
                    total = int(progress["total"])
                    fraction = int(progress["processed"]) / total if total else 0.0
                    progress["fraction"] = 1.0 if item.state == "succeeded" else fraction
                    result["progress"] = progress
                if item.state == "succeeded":
                    result["result"] = _snapshot(item.result, "error.engine_internal")
                if item.error is not None:
                    result["error"] = {"key": item.error}
                return result

    def cancel(self, job: str) -> dict[str, Any]:
        if type(job) is not str:
            raise EngineError("error.job_not_found")
        with self._condition:
            item = self._jobs.get(job)
            if item is None:
                raise EngineError("error.job_not_found")
            with item.lock:
                if item.state == "queued":
                    item.cancel_requested = True
                    item.state = "cancelled"
                    item.error = "error.job_cancelled"
                    self._queue.remove(job)
                    self._trim_terminal()
                elif item.state == "running":
                    item.cancel_requested = True
                requested = item.cancel_requested
                state = item.state
            return {"job": job, "cancel_requested": requested, "state": state}

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            for identifier in tuple(self._queue):
                item = self._jobs[identifier]
                with item.lock:
                    item.cancel_requested = True
                    item.state = "cancelled"
                    item.error = "error.job_cancelled"
            self._queue.clear()
            for item in self._jobs.values():
                with item.lock:
                    if item.state == "running":
                        item.cancel_requested = True
            self._condition.notify_all()
            self._trim_terminal()

    def _trim_terminal(self) -> None:
        terminal = {"succeeded", "failed", "cancelled"}
        while sum(self._jobs[key].state in terminal for key in self._order) > 64:
            for identifier in tuple(self._order):
                if self._jobs[identifier].state in terminal:
                    self._order.remove(identifier)
                    del self._jobs[identifier]
                    break

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._queue and not self._closed:
                    self._condition.wait()
                if self._closed and not self._queue:
                    return
                identifier = self._queue.popleft()
                item = self._jobs[identifier]
                with item.lock:
                    if item.state != "queued":
                        continue
                    item.state = "running"
            _context.job = item
            try:
                result = item.operation(**item.parameters)
                with item.lock:
                    if item.cancel_requested:
                        item.state = "cancelled"
                        item.error = "error.job_cancelled"
                    else:
                        item.result = _snapshot(result, "error.job_result")
                        item.state = "succeeded"

            except EngineError as exc:
                with item.lock:
                    item.error = "error.job_cancelled" if item.cancel_requested else exc.key
                    item.state = "cancelled" if item.cancel_requested else "failed"
            except Exception:
                with item.lock:
                    item.error = (
                        "error.job_cancelled" if item.cancel_requested else "error.engine_internal"
                    )
                    item.state = "cancelled" if item.cancel_requested else "failed"
            finally:
                _context.job = None
                with self._condition:
                    self._trim_terminal()
