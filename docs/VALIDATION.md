# Validation — Phase 0 contributor slices

Date: 2026-10-14, Europe/Prague. These results describe an Intel contributor build, not a completed phase or a portable release.

## Passed locally

- `make check`: Swift build, Python suite, ruff, strict mypy, Swift formatter lint, Swift/Python integration, feature-status validator and localization catalog checks.
- Python: **473 tests passed**, with **94.29% branch-aware engine coverage**, exceeding the 90% threshold. This is code coverage, not statistical-method coverage. No statistical procedure exists yet.
- Arrow interoperability: six original PyArrow inputs cover exact signed int64 bounds, negative zero, smallest subnormal, full-precision doubles, UTF-8, Boolean bits, nulls, empty response sets, multiple record batches and empty pages. Compression, nonfinite values, invalid response elements and duplicates are rejected. All 2,082 truncations are rejected; 2,082 deterministic byte mutations execute without a memory trap. This is a bounded reader check, not general Arrow conformance or a security audit. Artifact release is verified after native client reads.
- Swift/Python integration: actual sidecar handshake, typed data creation, immutable edit, Czech decimal parsing, full-precision editable number round trip, Unicode framing, project save/reopen, domain errors and graceful shutdown.
- Native NSDocument smoke in English and Czech: native window and toolbar, engine startup, Arrow viewport decoding, typed edit, undo, redo, explicit save and a second document reopened with the original value. Labels were verified as “Measurement” and “Měření”. These are internal integration checks, not full XCTest UI or accessibility audits.
- Dataset controls: append cases and all five storage types, immutable bases, retained sparse edits, stable IDs, empty tables, row-group boundaries, save/reopen and rejection of invalid counts/duplicate or reserved fields. Native English/Czech integration checks append a case and integer variable, preserve Int64.max on save/reopen, preserve negative zero through editing/RPC/save/reopen, import a semicolon/comma-decimal CSV, then undo the import and restore a valid inspector selection. The options forms are compiled but have not received a full interaction/visual audit.
- Localization: 452 current catalog keys have English and Czech translations; declared engine error keys resolve.
- Xcode project/Info.plist syntax passes `plutil`; app signing passes ad-hoc `codesign --verify --strict`.
- Feature coverage gate: **24/353 implemented, including 19 verified rows**. Reference fixtures include original typed-data/codebook contracts and independent hand-calculated case, classification, column, table and outlier expectations. The gate checks executed markers, passing outcomes, source freshness and actual tracked fixture use.

Environment: x86_64, macOS 26.7, Swift 6.3.3, Python 3.12.14, pyarrow 25.0.1. Active developer directory is `/Library/Developer/CommandLineTools`.

## Added foundation checks

- Actual managed RPC jobs create, import, transform and export datasets. Tests exercise method allowlisting, bounded strict JSON snapshots, cancellation, failure redaction and worker cleanup. Field descriptors now return JSON arrays, including codebooks.
- Native English/Czech smoke runs 23 checks each, adding safe expressions, interval classification, missing audit, stable sort/filter, edits against noncontiguous case IDs and reopening filtered projects. Each immutable change has its own undo group. Panel compilation does not replace a full form-interaction audit.
- Python acceptance includes rich Parquet/JSON/SQLite/XLSX round trips, untrusted-file rejection, original SAV/DTA inputs, typed transforms, external sorting and immutable structure operations. See format docs for bounds and losses; the wider catalog rows remain in progress where requirements are missing.

## Limited performance measurement

A generated 1M-row × 3-column CSV, 20,785,820 bytes, imported to typed Parquet with stable row IDs in **0.8118 seconds**. Fetching the last 128 rows took **0.00347 seconds**. This is one cache-warm engine measurement. It excludes UI presentation and copying the saved project, and does not verify cold loading, 100 columns, 5M rows, common statistical analyses or 60 fps scrolling. See [raw report](evidence/benchmark-intel.json).

An additional original **5M × 100** CSV (4,400,001,200 bytes) imported in **126.393 seconds**, with **877,342,720-byte peak RSS**. Project reopening took 7.008 seconds. Before metadata-cache optimization, first JSON/last Arrow pages took 0.913/0.835 seconds. See [large report](evidence/benchmark-large-intel.json) and [scope](LARGE_BENCHMARK.md).

A separate direct-Parquet **5M × 100** paging run measured metadata-cache-cleared calls at 0.083–0.089 seconds and repeated median calls at 0.0044–0.0051 seconds, with 182,140,928-byte peak RSS. See [paging report](evidence/benchmark-paging-intel.json) and [scope](PAGING_BENCHMARK.md). These are engine measurements on one machine; they do not establish native 60 fps, cold-disk performance or CSV speed after the optimization.

## Unavailable or pending

`swift test` fails here with the exact diagnostic `no such module 'XCTest'`. Full Xcode is not installed under /Applications, and the selected Command Line Tools do not provide XCTest/Swift Testing. The checks above do not disguise that failure. The full Xcode application build, XCTest/UI suite and GitHub runner executions are pending.

Native arm64/macOS 14 execution, manual keyboard/VoiceOver/text-scaling audits, full visual review, shared-document coordination, autosave and large-grid acceptance remain pending. Internal view-cache render probes cannot capture every native sidebar/material layer and are not presented as finished screenshots.

Portable Python relocation, all transitive/native component licenses, hardened-runtime behavior, quarantined clean-system launch and DMG size are unverified. The user has no Developer ID; trusted signing/notarization is deferred. The app currently relies on this source checkout's virtual environment.

## Recorded native checks

- [English native report](evidence/native-en.json)
- [Czech native report](evidence/native-cs.json)

Source publication is authorized at https://github.com/teodorino5/OpenStat-Mac. No binary release or successful public CI result is claimed.
