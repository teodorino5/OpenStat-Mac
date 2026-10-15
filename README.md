# OpenStat Mac

An original MIT-licensed native macOS data editor and the foundation of a statistics application. macOS 14+, Swift 5.9+, Python 3.12. Working name is provisional.

**25 of 353 planned functions implemented, 19 verified.** Verification covers original codebook, typed case operations, classifications, table operations, ranks, lag/lead, standardization, duplicates, and outlier reference fixtures. No statistical analysis procedure is implemented yet. Another 28 families remain unknown or explicitly excluded; the denominator is the scoped feature matrix, not a claim of exhaustive vendor parity.

## Run locally

Install Apple's Command Line Tools or full Xcode, and [uv](https://docs.astral.sh/uv/). Then run:

```sh
make setup
make run
```

`make run` builds and opens `build/OpenStat Mac.app`. This is a **local contributor app** using this checkout's `engine/.venv`. It is not portable, not Developer ID signed and not notarized. The bundled resource files and executable are ad-hoc signed. No unaudited Python runtime or numerical library is copied into the app. Do not distribute this app as a standalone release.

Full Xcode is required for `make test` (XCTest). Command Line Tools can run `make check`: Python tests, strict mypy, ruff, Swift formatting, source build, feature-status gate and Swift/Python integration smoke. An Xcode app project is included and its plist syntax is checked; its actual Xcode build remains unverified on the current CLT-only machine.

## Current behavior

- Native document windows and an NSTableView grid with editable typed cells.
- Identifier/characteristic roles; numeric, ordered and categorical measurement metadata. The engine also supports multiple-response sets and value/missing labels.
- Population/sample/unspecified scope and observation-unit metadata.
- Immutable Parquet data, sparse edit revisions and bounded viewport pages.
- Project save/open with checksums, relative-path checks and preserved typed values.
- Separate undo/redo groups for immutable edits, imports and transforms; native autosave/version integration remains pending.
- CSV/TSV import with delimiter/decimal options and explicit export loss reports.
- Rich Parquet interchange; bounded typed JSON, SQLite and XLSX envelopes; bounded SAV/DTA interchange and an unverified SAS reader. See format-specific docs for rejected types and metadata losses.
- Safe case predicates and filters, stable external sort, classification, contingency counts, missing-value inspection, recoding, numeric expressions, ranks, lag/lead, standardization, duplicates and exact Tukey outlier flags.
- Engine table joins, streaming stacks, matrix transpose, wide pivot and grouped aggregation. A native multi-dataset workflow and remaining reshape/provenance support are pending.
- Native codebook, case, classification, column, outlier and export panels. Managed background jobs expose progress and cooperative cancellation.
- Complete English/Czech strings for the current controls, messages and accessibility labels.
- Standalone Python library, CLI and private-pipe JSON-RPC service.

The native grid reads bounded Arrow IPC pages with checked schemas, row IDs, lengths and SHA-256 checksums. Its original Swift reader supports the engine’s uncompressed V5 int64, float64, UTF-8, Boolean and list-of-string subset; it is not a general Arrow importer. The full 5M × 100/60 fps gate remains pending. The app starts with 50 blank cases and three variables. Basic case/variable addition and CSV/TSV delimiter/decimal options are available. Selected-case deletion and variable removal preserve prior revisions. Phase 0 remains incomplete: persistent weight selection, formula autocomplete, full reshape and missing-pattern audits, grouped provenance, wider file-format support, Box-Cox, analysis specifications, result blocks, autosave and complete native workflow/accessibility checks remain pending.

Statistics, results reports, command palette, workflow editor and charts are not available yet. Their UI sections state their pending phase explicitly.

## Checks and evidence

```sh
make check
make test       # requires full Xcode; does not silently skip XCTest
make benchmark        # original 1M × 3 engine import
make benchmark-large  # original 5M × 100 CSV import; requires scratch disk space
make benchmark-paging # repeated bounded pages; does not measure native frame rate
```

The current Intel machine passed Python tests, strict type/lint checks, Swift/Python integration and native-window edit/undo/redo/save/reopen checks in English and Czech. See [session evidence](docs/VALIDATION.md) for exact results and limits. The first public CI run exposed a SQLite capability difference in runner Python builds; the fix and regression pass locally, and a fresh CI run is pending. macOS 14 execution, a full accessibility audit and portable release remain pending.

Screenshots are pending a visual review of the running original app. Do not use third-party artwork or screenshots as placeholders.

## Architecture and extension

- [Gemini collaboration handoff](docs/CO_WORK.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Implemented RPC protocol](docs/RPC.md)
- [Current native format](docs/PROJECT_FORMAT.md)
- [Add an analysis module](docs/ADD_ANALYSIS.md)
- [Numerical conventions](docs/NUMERICAL_CONVENTIONS.md)
- [Release state](docs/RELEASE.md)
- [Feature matrix](docs/FEATURE_MATRIX.md) and [stable catalog](docs/feature_catalog.json)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md) and [audit sources](docs/SOURCES.md)
- [Third-party ledger](THIRD_PARTY_LICENSES.md)

The first intended statistical release completes Phases 0–2. Development follows the phase gates; later statistical methods remain unavailable until the foundation phase is fully verified. All documentation, UI wording and sample/reference fixtures are original or independently sourced with provenance.
