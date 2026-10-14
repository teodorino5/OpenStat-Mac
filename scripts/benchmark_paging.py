"""Measure repeated engine pages from an original 5M by 100 Parquet dataset."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import shutil
import statistics
import struct
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pyarrow import ipc as arrow_ipc

from openstat_engine.model import Field
from openstat_engine.store import ROW_ID, Revision, Store

ROOT = Path(__file__).resolve().parents[1]
ROWS = 5_000_000
COLUMNS = 100
BATCH_ROWS = 8192
PAGE_SIZE = 128
TOKENS = (0.125, -1.2345678901234567, 2.125, 999.875, 0.5)


def peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def generate_parquet(path: Path) -> tuple[tuple[Field, ...], float]:
    fields = tuple(
        Field(f"field-{index:03d}", f"Measure_{index:03d}", "float64", "continuous")
        for index in range(COLUMNS)
    )
    schema = pa.schema([(ROW_ID, pa.int64()), *[(field.id, pa.float64()) for field in fields]])
    pattern = pa.array(TOKENS, type=pa.float64())
    started = time.perf_counter()
    with pq.ParquetWriter(path, schema) as writer:
        for start in range(0, ROWS, BATCH_ROWS):
            count = min(BATCH_ROWS, ROWS - start)
            stop = start + count
            row_ids = pa.array(range(start, stop), type=pa.int64())
            phase_columns: list[pa.Array] = []
            for phase in range(len(TOKENS)):
                indices = pa.array(
                    [(row + phase) % len(TOKENS) for row in range(start, stop)],
                    type=pa.int8(),
                )
                phase_columns.append(pc.take(pattern, indices))
            arrays = [row_ids, *[phase_columns[index % len(TOKENS)] for index in range(COLUMNS)]]
            writer.write_table(pa.Table.from_arrays(arrays, schema=schema), row_group_size=count)
    return fields, time.perf_counter() - started


def footer_bytes(path: Path) -> int:
    with path.open("rb") as stream:
        stream.seek(-8, os.SEEK_END)
        trailer = stream.read(8)
    if len(trailer) != 8 or trailer[4:] != b"PAR1":
        raise AssertionError("Generated Parquet footer trailer is invalid")
    return int.from_bytes(trailer[:4], "little") + 8


def page_hash(row_ids: list[int], rows: list[list[Any]]) -> str:
    digest = hashlib.sha256()
    for row_id, row in zip(row_ids, rows, strict=True):
        digest.update(struct.pack("<q", row_id))
        for value in row:
            digest.update(struct.pack("<d", value))
    return digest.hexdigest()


def verify_page(row_ids: list[int], rows: list[list[Any]], offset: int) -> str:
    if row_ids != list(range(offset, offset + PAGE_SIZE)):
        raise AssertionError(f"Unexpected row IDs at page offset {offset}")
    if len(rows) != PAGE_SIZE or any(len(row) != COLUMNS for row in rows):
        raise AssertionError("Page shape differs from 128 × 100 contract")
    for local_row, row in enumerate(rows):
        source_row = offset + local_row
        for column, actual in enumerate(row):
            expected = TOKENS[(source_row + column) % len(TOKENS)]
            if struct.pack("<d", actual) != struct.pack("<d", expected):
                raise AssertionError(
                    f"Value mismatch at row {source_row}, column {column}: "
                    f"{actual!r} != {expected!r}"
                )
    return page_hash(row_ids, rows)


def run_page(
    store: Store, revision: str, field_ids: list[str], offset: int, result_format: str
) -> tuple[float, str, dict[str, Any]]:
    started = time.perf_counter()
    result = store.page(revision, offset, PAGE_SIZE, format=result_format)
    elapsed = time.perf_counter() - started
    if result_format == "json":
        digest = verify_page(result["row_ids"], result["rows"], offset)
    else:
        artifact = result["artifact"]
        try:
            with pa.memory_map(artifact["path"], "r") as source:
                table = arrow_ipc.open_file(source).read_all()
            if table.schema.names != [ROW_ID, *field_ids]:
                raise AssertionError("Arrow page schema differs from requested field IDs")
            row_ids = table[ROW_ID].to_pylist()
            rows = [
                [table[field_id][index].as_py() for field_id in field_ids]
                for index in range(PAGE_SIZE)
            ]
            digest = verify_page(row_ids, rows, offset)
        finally:
            store.release(artifact["handle"])
    return elapsed, digest, result


def main() -> None:
    parent = Path(tempfile.gettempdir())
    free = shutil.disk_usage(parent).free
    if free < 4 * 1024**3:
        raise RuntimeError(f"Need at least 4 GiB free scratch space; have {free} bytes")

    with tempfile.TemporaryDirectory(prefix="openstat-paging-benchmark-", dir=parent) as temporary:
        directory = Path(temporary)
        parquet_path = directory / "original-cyclic-5m-100.parquet"
        fields, generation_seconds = generate_parquet(parquet_path)
        parquet_size = parquet_path.stat().st_size
        footer_size = footer_bytes(parquet_path)
        if len(fields) != COLUMNS:
            raise AssertionError("Generated Parquet column count differs from contract")

        store = Store(directory / "store")
        revision_id = str(uuid4())
        dataset_id = str(uuid4())
        descriptor = store._record(
            Revision(
                revision_id,
                dataset_id,
                "Original cyclic 5M by 100",
                parquet_path,
                fields,
                ROWS,
            )
        )
        field_ids = [field.id for field in fields]
        offsets = {"middle": (ROWS // 2) - PAGE_SIZE // 2, "end": ROWS - PAGE_SIZE}

        cold_pages: dict[str, dict[str, Any]] = {}
        repeated: dict[str, dict[str, Any]] = {}
        for location, offset in offsets.items():
            for result_format in ("json", "arrow"):
                store.clear_metadata_cache()
                elapsed, digest, result = run_page(
                    store, descriptor["revision"], field_ids, offset, result_format
                )
                if result["count"] != PAGE_SIZE:
                    raise AssertionError(f"Cold {location} {result_format} page is incomplete")
                cold_pages[f"{location}_{result_format}"] = {
                    "seconds": elapsed,
                    "logical_sha256": digest,
                    "cache_cleared_before_call": True,
                }

                timings: list[float] = []
                hashes: list[str] = []
                for _ in range(10):
                    elapsed, repeated_hash, _ = run_page(
                        store, descriptor["revision"], field_ids, offset, result_format
                    )
                    timings.append(elapsed)
                    hashes.append(repeated_hash)
                if len(set(hashes)) != 1 or hashes[0] != digest:
                    raise AssertionError(
                        f"Cold and repeated {location} {result_format} results differ"
                    )
                sorted_timings = sorted(timings)
                repeated[f"{location}_{result_format}"] = {
                    "calls": len(timings),
                    "minimum_seconds": sorted_timings[0],
                    "median_seconds": statistics.median(timings),
                    "p95_seconds": sorted_timings[min(len(timings) - 1, int(len(timings) * 0.95))],
                    "maximum_seconds": sorted_timings[-1],
                    "logical_sha256": hashes[0],
                    "all_hashes_match": True,
                }

        for location in offsets:
            if (
                cold_pages[f"{location}_json"]["logical_sha256"]
                != cold_pages[f"{location}_arrow"]["logical_sha256"]
            ):
                raise AssertionError(f"JSON and Arrow {location} page results differ")
        with store._metadata_lock:
            metadata_cache_entries = len(store._metadata_cache)
        metadata = pq.ParquetFile(parquet_path).metadata
        row_groups = metadata.num_row_groups
        if metadata.num_rows != ROWS:
            raise AssertionError("Generated Parquet row count differs from contract")
        report = {
            "recorded_at_utc": datetime.now(UTC).isoformat(),
            "dataset": {
                "rows": ROWS,
                "columns": COLUMNS,
                "storage": "float64",
                "field_ids_unique": len(set(field_ids)) == COLUMNS,
                "first_field_id": field_ids[0],
                "last_field_id": field_ids[-1],
                "row_groups": row_groups,
                "page_size": PAGE_SIZE,
                "offsets": offsets,
                "pattern": [repr(value) for value in TOKENS],
                "verification": (
                    "all cells in cold and repeated pages matched exact f64 bits "
                    "and case IDs"
                ),
            },
            "bytes": {
                "parquet_file": parquet_size,
                "parquet_footer_including_trailer": footer_size,
            },
            "seconds": {
                "parquet_generation": generation_seconds,
                "cold_pages": cold_pages,
                "repeated_pages": repeated,
            },
            "metadata_cache": {
                "entries_after_run": metadata_cache_entries,
                "max_entries": 2,
                "cold_calls_used_clear_metadata_cache": True,
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
            "cache_limits": {
                "process": (
                    "clear_metadata_cache before each cold call; ten later calls "
                    "reuse current Store cache"
                ),
                "os": "uncontrolled; generated Parquet may remain in operating-system file cache",
                "claims": (
                    "one process and one run; no cold-disk result or statistical "
                    "distribution"
                ),
            },
            "scope": {
                "measured": "direct-Parquet generation, Store.page JSON and Arrow extraction",
                "excluded": (
                    "CSV parsing, native UI, protocol transfer, frame timing, "
                    "Instruments, 60 fps acceptance"
                ),
            },
        }

    output = ROOT / "build/benchmark-paging.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
