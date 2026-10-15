# XLSX interchange

OpenStat reads and writes a bounded subset of SpreadsheetML OOXML workbooks. The implementation uses Python's standard `zipfile` and `xml.etree.ElementTree` modules. It imports formulas as cached pre-calculated values and never executes workbook code or macros.

## Import

`import_xlsx(store, path, sheet=None)` imports the first worksheet by default. Pass `sheet` to select another worksheet by its workbook name. The first used row must contain unique, non-empty text headers. Blank rows inside the data region become null rows. The importer supports shared strings, inline strings, numeric cells, booleans, empty cells, and formula cells with cached values (numeric, boolean, or string formula results). It infers one column type from cell values. Mixed types become strings. XLSX cell dates and non-default cell styles are rejected because their interpretation depends on workbook formatting.

The importer reads formula cells as cached values and rejects uncalculated formulas without cached values, macro content, external links, encrypted or malformed archives, XML DTDs and entities, unsupported cell types, and packages that exceed member, expanded-size, part-size, row, column, or shared-string limits. It imports values as data only. It never runs workbook code.

## Export

`export_xlsx(store, revision, path, overwrite=False)` writes visible `Data` and very-hidden `_OpenStat_RowIDs` worksheets. A custom XML part stores OpenStat field IDs, storage and measurement types, codebooks, missing-value definitions, dataset context, and observation unit. Importing the `Data` sheet restores this metadata and stable row IDs. The row-ID sheet and custom XML part are required for a full OpenStat round trip.

XLSX spreadsheet software commonly stores numbers with limited decimal precision. OpenStat writes every float and every integer with 15 or more decimal digits as text. This preserves exact OpenStat values when the workbook is imported again with its OpenStat metadata. External spreadsheet consumers may treat these cells as text, which limits numeric calculations and sorting. Smaller integers and booleans remain numeric cells. Export reports this behavior in `notes`; it reports no OpenStat data loss because the typed metadata preserves all supported values.

The exporter writes to a temporary file in the destination directory and atomically creates or replaces the target. It refuses existing targets unless `overwrite=True`, and refuses paths inside the OpenStat store.

## Limits and errors

The importer accepts at most 128 ZIP members, 128 MiB expanded package data, 64 MiB per part, 1,000,000 shared strings, 1,048,575 data rows, and 1,024 columns. These limits bound memory and parsing work. Errors use `error.xlsx_schema`, `error.xlsx_unsafe`, `error.xlsx_style`, `error.xlsx_limit`, and `error.xlsx_sheet`, plus shared interchange or value-validation errors where applicable.
