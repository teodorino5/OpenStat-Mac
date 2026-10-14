import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from openstat_engine.store import Store

EXECUTED: dict[str, str] = {}
REFERENCES: dict[str, list[str]] = {}


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when == "call" or report.failed or report.skipped:
        EXECUTED[report.nodeid] = report.outcome


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if session.config.option.collectonly:
        return
    collected: dict[str, Any] = {
        item.nodeid: {
            "features": [str(marker.args[0]) for marker in item.iter_markers("feature")],
            "outcome": EXECUTED.get(item.nodeid, "not run"),
            "fixtures": REFERENCES.get(item.nodeid, []),
        }
        for item in session.items
    }
    root = Path(__file__).parents[2]
    matrix = runpy.run_path(str(root / "scripts/feature_matrix.py"))
    report = {
        "exitstatus": exitstatus,
        "tests": collected,
        "source_digest": matrix["source_digest"](root),
    }
    (Path(__file__).parents[1] / "feature-test-results.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "cache")


@pytest.fixture
def reference_fixture(request: pytest.FixtureRequest) -> Callable[[str], dict[str, Any]]:
    def load(relative: str) -> dict[str, Any]:
        root = Path(__file__).parents[2]
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Unsafe fixture path")
        REFERENCES.setdefault(request.node.nodeid, []).append(relative)
        value: dict[str, Any] = json.loads(path.read_text())
        return value

    return load


@pytest.fixture
def numeric() -> list[dict[str, str]]:
    return [{"id": "amount", "name": "Amount", "storage": "float64", "measurement": "continuous"}]
