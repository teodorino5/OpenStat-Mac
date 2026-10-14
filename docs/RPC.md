# Engine RPC 1.1

The Swift app starts the Python engine as a child process. JSON-RPC 2.0 messages travel only over that process's stdin/stdout pipes; this is not a network listener. Each message uses `Content-Length: <UTF-8-byte-count>\r\n\r\n` followed by one JSON object. stdout carries protocol frames only. Diagnostics go to stderr. Batch arrays are unsupported; valid notifications receive no response.

The engine accepts payloads up to 8 MiB and headers up to 4,096 bytes. It rejects duplicate/malformed headers, invalid JSON, non-finite JSON constants, truncated frames, and non-object requests. A framing error sends one parse error when possible, then closes the connection. JSON output forbids NaN and Infinity. The parser preserves Foundation's floating negative-zero token `-0` as IEEE negative zero and parses other integer tokens without float conversion. The native client validates response IDs, serializes pipe access on a private queue, and terminates a hung process after 30 seconds.

## Handshake and data transfer

`engine.hello` accepts optional `protocol_major` (currently `1`) and returns `protocol_major: 1`, `protocol_minor: 1`, `engine_version`, registered method names, `analysis_methods: []`, `bulk: ["arrow_ipc_file"]`, `max_page_rows: 512`, `max_inline_rows: 100000`, `ui_transport: "arrow_ipc_file"`, the session artifact directory, and `max_arrow_bytes: 33554432`. A different major version returns `error.protocol_version`.

`dataset.page` returns projected typed values and stable row IDs as JSON or an Arrow IPC file artifact. Inline page requests are limited to 512 rows. Arrow artifacts use UUID handles, canonical files in the advertised `openstat-` session directory, SHA-256, and an explicit `artifact.release` call. Arrow payloads are limited to 32 MiB. The native reader verifies handle path, byte length, checksum, schema, and row IDs. It supports uncompressed little-endian V5 int64, float64, UTF-8, Boolean, and list-of-string arrays. Other Arrow encodings are rejected. Dataset creation accepts at most 100,000 inline rows; `dataset.extend` accepts at most 100,000 blank rows per call.

## Registered methods

The handshake method list is the runtime source of truth. Current methods include:

| Area | Methods |
| --- | --- |
| Engine | `engine.hello`, `engine.shutdown` |
| Dataset and project | `dataset.create`, `dataset.extend`, `dataset.page`, `dataset.edit`, `dataset.metadata`, `dataset.importCSV`, `project.save`, `project.open`, `artifact.release` |
| Office and statistical-file I/O | `dataset.import_xlsx`, `dataset.export_xlsx`, `dataset.import_sav`, `dataset.import_dta`, `dataset.import_sas7bdat`, `dataset.export_sav`, `dataset.export_dta` |
| Table transformations | `tables.stack`, `tables.join`, `tables.transpose`, `tables.pivot`, `tables.aggregate` |
| Case views | `dataset.select`, `dataset.filter`, `dataset.sort`, `dataset.weights` |
| Other Phase 0 data operations | `columns.outliers`, `dataset.delete_cases`, `dataset.drop_fields`, `classification.categories`, `classification.intervals`, `dataset.contingency`, `dataset.missing_audit`, `columns.recode`, `columns.compute`, `columns.rank`, `columns.lag`, `columns.standardize`, `columns.duplicates` |
| Interchange | `dataset.export_csv`, `dataset.import_parquet`, `dataset.export_parquet`, `dataset.import_json`, `dataset.export_json`, `dataset.import_sqlite`, `dataset.export_sqlite` |
| Jobs | `jobs.submit`, `jobs.status`, `jobs.cancel` |

The engine currently advertises no statistical analysis methods. Registered data transformations, classification, inspection, and interchange methods do not imply inferential statistics support. See the feature catalog and acceptance-test report for current Phase 0 status.

## Jobs

`jobs.submit` accepts `method` and a nested `parameters` object. It accepts only registered methods outside `engine.*`, `jobs.*`, and `artifact.release`; it JSON-validates and copies parameters before queueing. It returns a job ID. `jobs.status` returns state and, when reported, actual processed/total counts and progress fraction. `jobs.cancel` removes queued jobs or requests cooperative cancellation of running jobs. A running operation must reach `jobs.checkpoint` or return before cancellation takes effect. The manager allows at most eight queued jobs and retains up to 64 terminal records.

Method-specific operations can also be dispatched directly, but that call runs synchronously in the service loop. The native document model submits its long-running operations through jobs and polls status. Operations without checkpoints expose no progress and cannot stop promptly while inside a long computation. Job parameter and result limits, checkpoint semantics, and lifecycle details are in [JOBS.md](JOBS.md).

## Errors and process setup

Errors return a JSON-RPC code, a stable locale-independent message key, and `data.message_key`. Domain failures use documented `EngineError` keys; unexpected exceptions return `error.engine_internal`, file failures return `error.file_io`, and parameter binding errors return `error.rpc_params`. Error payloads do not include source rows, exception details, or tracebacks. The native app localizes message keys at its boundary. Never parse localized display text as protocol data.

The native app launches the configured contributor Python executable in isolated mode (`-I`) and inserts the engine source path through a fixed bootstrap argument. It drains stderr separately and never evaluates project code when opening a file. A typical local setup uses Python 3.12 and `uv sync --directory engine --python 3.12 --locked`; see `CONTRIBUTING.md` and the repository setup instructions. The app's development runtime points to this checkout's virtual environment. It is not a portable bundled runtime.
