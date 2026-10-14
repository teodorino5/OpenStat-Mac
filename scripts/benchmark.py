"""Record an original CSV benchmark; this is not the full performance acceptance gate."""

import json
import platform
import tempfile
import time
from pathlib import Path

from openstat_engine.store import Store

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="openstat-benchmark-") as temporary:
    directory = Path(temporary)
    source = directory / "Original.csv"
    with source.open("w") as stream:
        stream.write("Observation,Measurement,Group\n")
        for i in range(1_000_000):
            stream.write(f"{i},{i % 97 + 0.25},group-{i % 5}\n")
    store = Store(directory / "cache")
    start = time.perf_counter()
    result = store.import_csv(str(source))
    elapsed = time.perf_counter() - start
    assert result["row_count"] == 1_000_000
    page_start = time.perf_counter()
    page = store.page(result["revision"], 999_872, 128)
    page_elapsed = time.perf_counter() - page_start
    assert page["count"] == 128 and page["row_ids"][-1] == 999_999
    report = {
        "os": platform.platform(),
        "architecture": platform.machine(),
        "rows": 1_000_000,
        "columns": 3,
        "csv_bytes": source.stat().st_size,
        "import_seconds": elapsed,
        "last_page_seconds": page_elapsed,
        "includes": "CSV parsing, row IDs, typed Parquet staging; excludes UI and project copy",
        "limitation": (
            "One cache-warm generated input on this machine; "
            "not a cold-load or 100-column acceptance test"
        ),
    }
    output = root / "build/benchmark.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
