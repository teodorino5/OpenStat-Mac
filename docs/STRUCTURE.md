# Case and variable removal

The engine provides two immutable operations in `openstat_engine.structure`:

```python
delete_cases(store, revision, row_ids)
drop_fields(store, revision, fields)
```

Both operations read the selected revision in bounded Arrow batches. They write a new Parquet base, materialize the revision's current edits, clear the new overlay, and return a new revision descriptor. The source revision and source base remain available. The new revision keeps the same dataset ID, name, context and observation unit.

`delete_cases` accepts a list of up to 100,000 unique, nonnegative integer case IDs. Booleans are invalid even though Python treats them as integers. IDs are stable case IDs, not row positions. Every requested ID must exist; an unknown ID fails with `error.row_id`. The operation preserves the original IDs and order of retained cases. An empty request creates an equivalent new revision. Deleting every case creates a valid empty dataset.

`drop_fields` accepts unique existing field IDs. The operation preserves original order and all metadata for retained fields. It requires at least one field to remain. An empty request creates an equivalent new revision. Invalid field IDs and an attempt to remove every field fail with `error.field_id`; repeated IDs fail with `error.duplicate_fields`.

Both operations call the job checkpoint API during scans and writes. Cancellation or any other failure removes the incomplete output file and does not register a revision. These operations only create new revision files; they never remove project files, source data, or older revision files.
