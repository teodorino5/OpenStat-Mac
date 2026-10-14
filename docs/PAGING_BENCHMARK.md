# Large-table paging benchmark

Run from repository root with `engine/.venv/bin/python scripts/benchmark_paging.py`. Script writes an original 5,000,000-row × 100-column Parquet dataset directly in 8,192-row batches, then registers it with engine `Store` and measures actual `Store.page` calls. Five literal numeric values cycle by row and column. First and last case IDs and all 12,800 float64 values on each page are checked against the independent literal pattern, including exact f64 bits.

The script records file size, footer bytes, row-group count, generation time, one metadata-cache-cold JSON and Arrow page per middle and end offset, followed by ten repeated JSON and Arrow pages at each offset, per-call times, logical page hashes, machine/toolchain, and process peak RSS. It releases each Arrow artifact and deletes the private temporary dataset and store after completion. Scratch guard requires at least 4 GiB free.

Cold calls clear the Store metadata LRU before each request. They are cold only relative to that in-process cache. The operating-system cache is uncontrolled and may contain the generated Parquet file. Repeated requests are one run's observations, not a statistical distribution. This benchmark does not measure CSV parsing, RPC transfer, native UI rendering, scrolling, frame intervals, input latency, main-thread stalls, Instruments, or the 60 fps viewport gate.

## Recorded run

On 2026-10-14, macOS 26.7 x86_64, Python 3.12.14 and PyArrow 25.0.1, generation took 13.44 s. The file contained 5,000,000 rows, 100 float64 columns and 611 row groups. Parquet occupied 54,837,837 bytes; footer plus trailer occupied 7,306,535 bytes. Peak process RSS was 182,140,928 bytes.

Cache-cleared 128-row calls took 0.083–0.089 s. Ten repeated calls per offset and format had medians from 0.0044–0.0051 s and p95 from 0.0048–0.0060 s. JSON and Arrow logical hashes matched per offset across cold and repeated calls. See [raw JSON report](../build/benchmark-paging.json) for each timing and hash. This is engine page timing only; 60 fps remains unmeasured.
