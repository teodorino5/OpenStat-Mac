import copy
import json
import runpy
from pathlib import Path


def test_gate_rejects_unexecuted_claims_and_missing_reference(tmp_path: Path) -> None:
    module = runpy.run_path(str(Path(__file__).parents[2] / "scripts/feature_matrix.py"))
    feature = {
        "id": "DATA-001",
        "phase": 0,
        "status": "implemented",
        "tests": [],
        "fixtures": [],
        "reference": "original",
        "evidence": "brief",
        "library": "original",
    }
    catalog = {"features": [feature]}
    errors = module["validate"](catalog, tmp_path)
    assert any("no test" in error for error in errors)
    assert any("No successful test run" in error for error in errors)
    engine = tmp_path / "engine"
    engine.mkdir()
    node = "tests/test_example.py::test_contract"
    report = {"exitstatus": 0, "tests": {node: {"features": ["DATA-001"], "outcome": "skipped"}}}
    (engine / "feature-test-results.json").write_text(json.dumps(report))
    feature["tests"] = ["engine/" + node]
    assert any("skipped or failed" in e for e in module["validate"](catalog, tmp_path))
    report["tests"][node]["outcome"] = "passed"
    (engine / "feature-test-results.json").write_text(json.dumps(report))
    assert module["validate"](catalog, tmp_path) == []
    feature["status"] = "verified against reference values"
    assert any("no fixture" in e for e in module["validate"](catalog, tmp_path))
    feature["fixtures"] = ["missing.json"]
    assert any("Missing reference" in e for e in module["validate"](catalog, tmp_path))
    fixture = {
        "provenance": "original",
        "independent_method": "hand contract",
        "expected": 3,
        "tolerance": 0,
        "feature_ids": ["DATA-001"],
        "test_selector": "engine/" + node,
    }
    (tmp_path / "missing.json").write_text(json.dumps(fixture))
    assert any("not loaded" in e for e in module["validate"](catalog, tmp_path))
    report["tests"][node]["fixtures"] = ["missing.json"]
    (engine / "feature-test-results.json").write_text(json.dumps(report))
    assert module["validate"](catalog, tmp_path) == []
    duplicate = copy.deepcopy(feature)
    assert any(
        "Duplicate" in e for e in module["validate"]({"features": [feature, duplicate]}, tmp_path)
    )


def test_gate_rejects_early_phase_promotion(tmp_path: Path) -> None:
    module = runpy.run_path(str(Path(__file__).parents[2] / "scripts/feature_matrix.py"))
    base = {
        "id": "DATA-001",
        "phase": 0,
        "status": "not started",
        "tests": [],
        "fixtures": [],
        "reference": "original",
        "evidence": "brief",
        "library": "original",
    }
    later = base | {"id": "DESC-001", "phase": 1, "status": "implemented"}
    assert any(
        "Earlier phase" in e for e in module["validate"]({"features": [base, later]}, tmp_path)
    )
