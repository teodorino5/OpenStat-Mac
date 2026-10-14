# Command-line interface

The `openstat` command imports, inspects, exports and transforms typed datasets without opening the macOS application. Run `openstat --help` for command syntax and `openstat --version` for the installed engine version.

## Import

```text
openstat import SOURCE DESTINATION.openstat [--format auto|csv|tsv|json|parquet|sqlite|xlsx]
  [--delimiter CHARACTER] [--decimal-point .|,] [--sheet NAME]
```

The default `auto` format uses the source extension. It recognizes `.csv`, `.tsv` or `.tab`, `.json`, `.parquet`, `.sqlite`, `.db` or `.db3`, and `.xlsx`. Use `--format` when the extension is missing or incorrect. CSV defaults to comma delimiter; TSV defaults to tab. The existing `--delimiter` and `--decimal-point` options remain available for CSV and TSV imports. `--sheet` selects an XLSX worksheet.

Import reports the imported dataset descriptor as JSON on stdout. Errors report a locale-independent key as JSON on stderr and return a nonzero status.

## Inspect

```text
openstat inspect PROJECT.openstat [--offset ROW] [--limit ROWS]
```

Inspect prints dataset metadata and a bounded page preview as JSON. It does not modify the project.

## Export

```text
openstat export PROJECT.openstat DESTINATION --format csv|tsv|json|parquet|sqlite|xlsx
  [--overwrite] [--delimiter CHARACTER] [--decimal-point .|,]
```

Export prints row count, destination path and format loss information as JSON. CSV and TSV report loss of codebooks, field IDs, context, the distinction between null and empty text, and the multiple-response storage type. JSON, Parquet and SQLite preserve the supported typed metadata. XLSX reports its typed-roundtrip notes. Existing output files are refused unless `--overwrite` is explicit. Export destinations cannot be placed inside the source project.

## Transform

```text
openstat transform PROJECT.openstat DESTINATION.openstat \
  --method METHOD --parameters-file PARAMETERS.json
```

The source project is opened read-only. The command applies one registered operation to a private copy and saves the result to a new project. The destination must not already exist. The parameter file must be a JSON object no larger than 1 MiB. Duplicate keys, non-finite values, nesting deeper than 32 levels, a supplied `revision` key, and unknown parameter keys are rejected. The command injects the source revision itself.

Methods are explicit and use typed, declarative arguments. Supported methods are `columns.recode`, `columns.compute`, `columns.rank`, `columns.lag`, `columns.standardize`, `columns.duplicates`, `classification.categories`, `classification.intervals`, `dataset.filter`, and `dataset.sort`. `columns.compute` accepts the engine's bounded JSON expression tree; the CLI does not evaluate source code or load project code. Each method uses the parameter names documented by its engine operation.

## Methods

```text
openstat methods
```

This command lists the current JSON-RPC method registry and returns an empty `analysis_methods` array. It does not advertise unimplemented statistical analyses.

## RPC service

```text
openstat serve
```

`serve` reads and writes Content-Length-framed JSON-RPC on stdin and stdout. Keep stdout reserved for protocol frames. The command-line import, inspect, export, transform and methods commands write machine-readable JSON results to stdout and stable error keys to stderr. Neither output includes source values in error details or traceback text.
