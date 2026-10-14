"""Validate coverage claims against executed acceptance tests and tracked reference fixtures."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/feature_catalog.json"
STATUSES = {"not started", "in progress", "implemented", "verified against reference values"}


def source_digest(root: Path) -> str:
    checksum = hashlib.sha256()
    paths: list[Path] = []
    for relative in ("engine/src", "engine/tests", "engine/fixtures", "scripts"):
        paths.extend(
            p for p in (root / relative).rglob("*") if p.is_file() and p.suffix in {".py", ".json"}
        )
    paths.extend(root / p for p in ("engine/pyproject.toml", "engine/uv.lock"))
    for path in sorted(paths):
        checksum.update(str(path.relative_to(root)).encode())
        checksum.update(path.read_bytes())
    return checksum.hexdigest()


def counts(features: list[dict[str, Any]]) -> tuple[int, int, int]:
    verified = sum(f["status"] == "verified against reference values" for f in features)
    implemented = sum(f["status"] == "implemented" for f in features) + verified
    return len(features), implemented, verified


def validate(catalog: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    features = catalog["features"]
    identifiers: set[str] = set()
    execution_path = root / "engine/feature-test-results.json"
    execution = json.loads(execution_path.read_text()) if execution_path.exists() else None
    if (
        root == ROOT
        and execution is not None
        and execution.get("source_digest") != source_digest(root)
    ):
        errors.append("Acceptance results are stale; rerun the engine test suite")
    for feature in features:
        identifier, status = feature["id"], feature["status"]
        if identifier in identifiers:
            errors.append(f"Duplicate feature ID: {identifier}")
        identifiers.add(identifier)
        if status not in STATUSES or feature["phase"] not in range(6):
            errors.append(f"Invalid status or phase: {identifier}")
        if not feature["reference"] or not feature["evidence"] or not feature["library"]:
            errors.append(f"Missing provenance: {identifier}")
        if status not in {"implemented", "verified against reference values"}:
            continue
        if not feature["tests"]:
            errors.append(f"Implemented feature has no test: {identifier}")
        if execution is None or execution["exitstatus"] != 0:
            errors.append(f"No successful test run for claim: {identifier}")
            continue
        for selector in feature["tests"]:
            if not selector.startswith("engine/tests/") or ".." in selector:
                errors.append(f"Unsupported acceptance test selector: {identifier}")
                continue
            selector = selector.removeprefix("engine/")
            matched = [
                value
                for node, value in execution["tests"].items()
                if node == selector or node.startswith(selector + "[")
            ]
            if not matched or any(
                value["outcome"] != "passed" or identifier not in value["features"]
                for value in matched
            ):
                errors.append(
                    f"Acceptance test missing, skipped or failed: {identifier}: {selector}"
                )
        if status != "verified against reference values":
            continue
        if not feature["fixtures"]:
            errors.append(f"Verified feature has no fixture: {identifier}")
        for reference in feature["fixtures"]:
            path = (root / reference).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                errors.append(f"Missing reference fixture: {identifier}")
                continue
            if root == ROOT:
                tracked = subprocess.run(
                    ["git", "ls-files", "--error-unmatch", "--", reference],
                    cwd=root,
                    capture_output=True,
                    check=False,
                )
                if tracked.returncode != 0:
                    errors.append(f"Reference fixture is not tracked in Git: {identifier}")
            fixture = json.loads(path.read_text())
            required = {"provenance", "independent_method", "expected", "tolerance", "feature_ids"}
            if not required <= fixture.keys() or identifier not in fixture.get("feature_ids", []):
                errors.append(f"Incomplete independent fixture: {identifier}")
            fixture_test = fixture.get("test_selector")
            if fixture_test not in feature["tests"]:
                errors.append(
                    f"Fixture comparison is not an executed acceptance test: {identifier}"
                )
            else:
                selector = fixture_test.removeprefix("engine/")
                comparisons = [
                    value
                    for node, value in execution["tests"].items()
                    if node == selector or node.startswith(selector + "[")
                ]
                if not comparisons or any(
                    reference not in value.get("fixtures", []) for value in comparisons
                ):
                    errors.append(f"Fixture was not loaded by its comparison test: {identifier}")
    # Strict phase order applies to accepted functions, not merely anticipatory source types.
    complete = {
        p: all(
            f["status"] == "verified against reference values" for f in features if f["phase"] == p
        )
        for p in range(6)
    }
    for feature in features:
        if feature["status"] in {"implemented", "verified against reference values"}:
            if any(not complete[p] for p in range(feature["phase"])):
                errors.append(f"Earlier phase gate incomplete: {feature['id']}")
    return errors


def render_matrix(catalog: dict[str, Any], text: str) -> str:
    features = {f["id"]: f for f in catalog["features"]}
    total, implemented, verified = counts(catalog["features"])
    text = re.sub(
        r"\*\*Coverage:.*?\*\*",
        f"**Coverage: {implemented} of {total} planned functions "
        f"implemented, {verified} verified against reference values.**",
        text,
        count=1,
    )
    lines = text.splitlines()
    for i, line in enumerate(lines):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 12 and parts[1] in features:
            feature = features[parts[1]]
            parts[5] = feature["library"]
            parts[7] = feature["status"]
            parts[9] = ", ".join(f"`{v}`" for v in feature["tests"]) or "—"
            parts[10] = ", ".join(f"`{v}`" for v in feature["fixtures"]) or "—"
            lines[i] = "| " + " | ".join(parts[1:-1]) + " |"
        elif re.fullmatch(r"\| [0-5] \| \d+ \| \d+ \| \d+ \|", line):
            phase = int(parts[1])
            subset = [f for f in features.values() if f["phase"] == phase]
            n, done, checked = counts(subset)
            lines[i] = f"| {phase} | {n} | {done} | {checked} |"
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()
    catalog = json.loads(CATALOG.read_text())
    errors = validate(catalog)
    matrix = ROOT / "docs/FEATURE_MATRIX.md"
    rendered = render_matrix(catalog, matrix.read_text())
    total, implemented, verified = counts(catalog["features"])
    readme = ROOT / "README.md"
    original = readme.read_text()
    updated = re.sub(
        r"\*\*\d+ of \d+ planned functions implemented, \d+ verified\.\*\*",
        f"**{implemented} of {total} planned functions implemented, {verified} verified.**",
        original,
        count=1,
    )
    if arguments.write and not errors:
        matrix.write_text(rendered)
        readme.write_text(updated)
    elif rendered != matrix.read_text() or updated != original:
        errors.append("Generated matrix or README is stale; run scripts/feature_matrix.py --write")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    phases = Counter(f["phase"] for f in catalog["features"])
    print(
        f"Coverage gate passed: {implemented}/{total} implemented, "
        f"{verified} verified; {dict(phases)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
