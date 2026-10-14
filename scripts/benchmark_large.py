"""Measure original 5M by 100 CSV import, project persistence, and Arrow paging."""

from __future__ import annotations

import json
import os
import platform
import resource
import shutil
import struct
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
from pyarrow import ipc

from openstat_engine.store import ROW_ID, Store

ROOT = Path(__file__).resolve().parents[1]
ROWS = 5_000_000
COLUMNS = 100
PAGE_SIZE = 128
MIB = 1024**2
GIB = 1024**3
# All values are exact binary fractions. One longer decimal checks f64 parsing.
TOKENS = ("0.125", "-1.2345678901234567", "2.125", "999.875", "0.5")
EXPECTED = tuple(float(value) for value in TOKENS)


def peak_rss_bytes() -> int:
    """Normalize getrusage units: bytes on macOS, KiB on Linux/BSD."""
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def generate_csv(path: Path) -> int:
    """Write five cyclic row templates in bounded repeated blocks."""
    header = (",".join(f"Measure_{column:03d}" for column in range(COLUMNS)) + "\n").encode()
    rows = tuple(
        (
            ",".join(TOKENS[(phase + column) % len(TOKENS)] for column in range(COLUMNS)) + "\n"
        ).encode()
        for phase in range(len(TOKENS))
    )
    cycle = b"".join(rows)
    if ROWS % len(rows):
        raise AssertionError("Benchmark row count must contain full cycles")
    cycles = ROWS // len(rows)
    estimated_size = len(header) + len(cycle) * cycles
    free = shutil.disk_usage(path.parent).free
    # Keep 8 GiB reserve beyond exact source size for Parquet/project copies and OS activity.
    required = max(4 * GIB, estimated_size + 8 * GIB)
    if free < required:
        raise RuntimeError(f"Insufficient scratch space: need {required} bytes; have {free} bytes")
    with path.open("wb", buffering=4 * MIB) as stream:
        stream.write(header)
        block_cycles = 2048
        full_block = cycle * block_cycles
        while cycles:
            count = min(cycles, block_cycles)
            stream.write(full_block if count == block_cycles else cycle * count)
            cycles -= count
    actual_size = path.stat().st_size
    if actual_size != estimated_size:
        raise AssertionError(f"CSV size mismatch: {actual_size} != {estimated_size}")
    return actual_size


def assert_values(rows: list[list[Any]], start: int) -> None:
    if len(rows) != PAGE_SIZE or any(len(row) != COLUMNS for row in rows):
        raise AssertionError("Page dimensions differ from benchmark contract")
    for offset, row in enumerate(rows):
        case = start + offset
        for column, actual in enumerate(row):
            expected = EXPECTED[(case + column) % len(EXPECTED)]
            if actual != expected or struct.pack("<d", actual) != struct.pack("<d", expected):
                raise AssertionError(
                    f"Value mismatch at case {case}, column {column}: {actual!r} != {expected!r}"
                )


def main() -> None:
    scratch_parent = Path(tempfile.gettempdir())
    free_before = shutil.disk_usage(scratch_parent).free
    if free_before < 4 * GIB:
        raise RuntimeError(f"Need at least 4 GiB free scratch space; have {free_before} bytes")

    with tempfile.TemporaryDirectory(
        prefix="openstat-large-benchmark-", dir=scratch_parent
    ) as temporary:
        work = Path(temporary)
        source = work / "cyclic-numeric-5m-100.csv"
        generation_start = time.perf_counter()
        source_bytes = generate_csv(source)
        generation_seconds = time.perf_counter() - generation_start

        store = Store(work / "engine-cache")
        start = time.perf_counter()
        imported = store.import_csv(str(source))
        import_seconds = time.perf_counter() - start
        if imported["row_count"] != ROWS or len(imported["fields"]) != COLUMNS:
            raise AssertionError("Engine import returned unexpected dataset dimensions")
        field_ids = [field["id"] for field in imported["fields"]]
        if len(set(field_ids)) != COLUMNS:
            raise AssertionError("Imported field IDs are not unique")
        if any(field["storage"] != "float64" for field in imported["fields"]):
            raise AssertionError("Generated numeric columns did not import as float64")
        base_bytes = store.get(imported["revision"]).base.stat().st_size

        project = work / "benchmark.openstat"
        start = time.perf_counter()
        store.save(imported["revision"], str(project))
        save_seconds = time.perf_counter() - start
        # Manifest records content-addressed Parquet path; read it without relying on filenames.
        manifest = json.loads((project / "manifest.json").read_text())
        project_parquet_bytes = (project / manifest["data"]).stat().st_size

        reopened_store = Store(work / "reopened-cache")
        start = time.perf_counter()
        reopened = reopened_store.open(str(project))
        reopen_seconds = time.perf_counter() - start
        if reopened["fields"] != imported["fields"] or reopened["row_count"] != ROWS:
            raise AssertionError("Reopened project changed field IDs or row count")

        start = time.perf_counter()
        first_page = reopened_store.page(reopened["revision"], 0, PAGE_SIZE)
        first_page_seconds = time.perf_counter() - start
        if first_page["row_ids"] != list(range(PAGE_SIZE)):
            raise AssertionError("First page row IDs differ from source order")
        assert_values(first_page["rows"], 0)

        offset = ROWS - PAGE_SIZE
        start = time.perf_counter()
        last_page = reopened_store.page(reopened["revision"], offset, PAGE_SIZE, format="arrow")
        last_page_seconds = time.perf_counter() - start
        artifact = last_page["artifact"]
        try:
            with pa.memory_map(artifact["path"], "r") as source_file:
                arrow_page = ipc.open_file(source_file).read_all()
            expected_ids = list(range(offset, ROWS))
            if arrow_page.schema.names != [ROW_ID, *field_ids]:
                raise AssertionError("Arrow page field IDs or column order changed")
            if arrow_page[ROW_ID].to_pylist() != expected_ids:
                raise AssertionError("Last page row IDs differ from source order")
            assert_values(
                [
                    [arrow_page[field_id][row].as_py() for field_id in field_ids]
                    for row in range(PAGE_SIZE)
                ],
                offset,
            )
        finally:
            reopened_store.release(artifact["handle"])

        report: dict[str, Any] = {
            "recorded_at_utc": datetime.now(UTC).isoformat(),
            "dataset": {
                "rows": ROWS,
                "columns": COLUMNS,
                "storage": "float64",
                "field_ids_unique": True,
                "first_field_id": field_ids[0],
                "last_field_id": field_ids[-1],
                "first_page_row_ids": [first_page["row_ids"][0], first_page["row_ids"][-1]],
                "last_page_row_ids": [expected_ids[0], expected_ids[-1]],
                "precision_check": "all 25,600 first/last-page values matched exact f64 bits",
                "value_pattern": list(TOKENS),
            },
            "bytes": {
                "source_csv": source_bytes,
                "imported_parquet": base_bytes,
                "saved_project_parquet": project_parquet_bytes,
            },
            "seconds": {
                "generation": generation_seconds,
                "engine_import": import_seconds,
                "project_save": save_seconds,
                "project_open": reopen_seconds,
                "first_page_json": first_page_seconds,
                "last_page_arrow": last_page_seconds,
            },
            "peak_rss_bytes": peak_rss_bytes(),
            "machine": {
                "os": platform.platform(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "logical_cpus": os.cpu_count(),
                "python": sys.version.split()[0],
                "pyarrow": pa.__version__,
            },
            "cache_state": {
                "process_cache": "new Store for reopen; same process for all measured stages",
                "os_cache": "uncontrolled; CSV was just generated and project was just saved",
                "claim": "single run; no cold-cache or warm-cache distribution measured",
            },
            "scope": {
                "measured": (
                    "engine CSV import, project save/open, JSON first page, "
                    "Arrow last page"
                ),
                "excluded": (
                    "native UI rendering, viewport scrolling, Instruments frame "
                    "timing, protocol latency"
                ),
                "60_fps_gate": "not measured",
            },
        }

    output = ROOT / "build/benchmark-large.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
