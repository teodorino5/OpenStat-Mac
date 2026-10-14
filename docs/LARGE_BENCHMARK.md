# Large-data engine benchmark

Run from the repository root with `engine/.venv/bin/python scripts/benchmark_large.py`. Script creates original 5,000,000-row × 100-column CSV in a private system temporary directory. It uses five cyclic literal numeric rows and repeats them in bounded blocks. Every value parses as `float64`; pattern includes `-1.2345678901234567` and binary-exact fractions. Script verifies all 100 columns, unique field IDs, first and last row IDs, and exact float bits across every cell in first and last 128-row pages.

Measured stages: CSV generation, engine import to typed Parquet, project save, project reopen into a separate Store, first JSON page, and last Arrow page. Report includes source and Parquet byte counts, hardware/runtime details, and process peak RSS normalized to bytes. Temporary raw data and project files are deleted when run ends. Disk guard requires at least 4 GiB free and an additional 8 GiB beyond estimated CSV size.

Script writes one run to `build/benchmark-large.json`. Results do not include UI or protocol latency. A new Store handles project reopen, but all stages use one process. The operating-system file cache is uncontrolled; CSV is written immediately before import and project data is written immediately before reopen. Timings are therefore neither verified cold-cache measurements nor a warm-cache distribution. Peak RSS is cumulative process high-water mark, not a per-stage memory profile.

This measures engine file I/O and page extraction. It does not measure native table rendering, scrolling, frame intervals, input latency, main-thread stalls, or Instruments signposts. A successful 5M × 100 engine run does not verify the separate 60 fps native viewport gate.
