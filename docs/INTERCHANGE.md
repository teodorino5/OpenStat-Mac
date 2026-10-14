# Phase 0 data interchange contracts

The interchange module exports the current immutable revision, including sparse cell edits. An export never mutates a revision or its base file. Imports create a new dataset identity and revision. Rich formats preserve field IDs, row IDs, displayed row order, storage types, measurement metadata, labels, ordered levels, missing codes, context and observation unit. Source files are read without modification. These are original acceptance fixtures, not independently sourced statistical reference fixtures.

## Format contracts

| Format | Implemented contract | Precision and limitations |
| --- | --- | --- |
| CSV/TSV | UTF-8 headers using variable names; comma, tab or semicolon delimiter; dot or comma decimal separator | Integers render as decimal integers; finite binary64 values use Python's shortest-roundtrip representation, including negative zero. Booleans use `true`/`false`; response sets use JSON array text. Nulls and empty strings both export as blank cells. Codebooks, field/row identity, context and multiple-response typing are lost. The export result explicitly lists losses. Existing CSV import infers types and does not reconstruct the rich codebook. |
| Parquet | Typed columns plus `openstat.interchange.v1` JSON schema metadata | Rich exports preserve int64, binary64, nulls, UTF-8, Boolean and list-of-string responses. Metadata-free input supports exactly these types and infers measurement scale; dates, unsigned integers and other schemas are rejected. A plain file receives new field IDs and sequential row IDs. |
| JSON | A UTF-8 `openstat-data`, version 1 snapshot with `dataset`, `row_ids`, and `rows` | Maximum encoded file size 32 MiB. Integers are JSON integers and the engine preserves all int64 values; consumers using JavaScript Number must handle integers beyond 2^53 explicitly. Null, empty string and empty response list remain distinct. Exports stream arrays; imports parse only after the size bound is checked. Arbitrary JSON shapes and duplicate object keys are rejected. |
| SQLite | Original OpenStat v1 envelope with `_openstat_metadata` and `_openstat_data` tables | The data table carries a private display-order column and stable row IDs. Signed int64 uses INTEGER; finite float64 uses little-endian 8-byte BLOB to retain exact bit patterns, including negative zero. Response lists are JSON TEXT; Boolean values are INTEGER 0/1. This is not a general-purpose arbitrary-table SQL importer. |

Rich metadata is limited to 1 MiB and 1,024 fields. Parquet and SQLite import/export operate in batches of at most 8,192 rows. Batch row counts bound table materialization; individual very large string cells can still consume substantial memory. Unique row IDs are validated using a temporary on-disk SQLite index rather than an unbounded in-memory set. Row IDs must be distinct nonnegative int64 values; they need not be contiguous or ordered. Imports validate every value against the declared codebook and reject nonfinite numbers and duplicate responses.

## File integrity

Export destinations must have an existing parent directory. Existing files require `overwrite=true`. Symlinks, directories and private engine cache/base paths are rejected. Writes use a temporary file in the destination directory, close and synchronize it, then atomically publish it. Without overwrite, a hard link prevents a racing writer from being silently overwritten. Failed writes remove the temporary file and preserve existing content.

SQLite input uses `mode=ro`, `query_only=ON` and `trusted_schema=OFF`, and extension loading is disabled. Queries are fixed; values use bound parameters and field IDs are quoted as identifiers. The importer accepts only the declared envelope tables and column layout. No caller-provided SQL, formulas, hooks or project code execute during import.

## Callable signatures

All functions take the engine `Store` as their first argument. The parent service supplies it; it is not an RPC parameter.

- `export_csv(store, revision, path, delimiter=",", decimal_point=".", overwrite=False)`
- `export_parquet(store, revision, path, overwrite=False)`
- `import_parquet(store, path)`
- `export_json(store, revision, path, overwrite=False)`
- `import_json(store, path)`
- `export_sqlite(store, revision, path, overwrite=False)`
- `import_sqlite(store, path)`

Exports return `path`, `rows`, and `losses`. Imports return the ordinary dataset descriptor. Filesystem and Arrow I/O failures remain ordinary operational errors for the service to translate; schema/domain errors use locale-independent engine error keys.

## Executed acceptance evidence

`engine/tests/test_interchange.py` covers literal boundary int64 values, a binary64 precision fixture, negative-zero bytes, Unicode, null versus empty string/list, ordered levels, labels, missing codes, population/unit metadata, sparse edits, empty datasets, bounded multi-batch operation, noncontiguous row identities and display order, quoted SQL identifiers, explicit overwrite, symlink/private-path rejection, malformed/incompatible schemas, duplicate JSON keys, nonfinite inputs, unsupported Arrow types, corrupt SQLite values, metadata bounds, source-file preservation and failed-import cleanup.

Feature markers identify DATA-028 CSV, DATA-029 TSV, DATA-031 JSON, DATA-032 Parquet and DATA-036 SQLite acceptance cases. GUI picker integration and broader workflow acceptance are separate checks. This module does not claim statistical-method validation, portable release readiness or execution on arm64.
