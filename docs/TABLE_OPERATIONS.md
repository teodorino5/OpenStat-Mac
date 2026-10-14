# Table operations

Phase 0 table functions create new immutable datasets. Inputs remain unchanged. New datasets receive fresh row IDs. Stack and join append source dataset UUIDs beside source row IDs because row IDs are unique only within one dataset. Aggregate and reshape outputs do not carry row-level source provenance; their fresh row IDs identify output rows only.

## APIs

| Function | Contract |
| --- | --- |
| `stack(store, revisions, name, match="name")` | Append datasets by field name (`name`) or field UUID (`id`). Field order follows first appearance across inputs. Missing fields become null. Matched fields must have the same storage and measurement. |
| `join(store, left, right, keys, name, how="inner", missing="never", cardinality="many_to_many", suffixes=None)` | Exact keyed join with ordered key pairs. `how` is `inner`, `left`, or `full`; there is no right-only mode. Key fields appear once in output. |
| `transpose(store, revision, name, fields=None)` | Matrix transpose: selected source fields become output rows, and source cases become output columns. Selected fields must share one supported storage type. Output rows record source field ID/name; output columns encode source row IDs in their names. |
| `pivot(store, revision, index, column, value, name)` | Convert each distinct non-null category in `column` into a wide output field. Each index/category pair must be unique. Missing combinations become null. |
| `aggregate(store, revision, groups, aggregations, name, include_missing_codes=False)` | Group by exact raw field values in first-seen order. Support `count`, `sum`, `mean`, `min`, and `max`. Raw null never contributes; coded missing contributes only when explicitly included. |

## Join and stack behavior

Join raw-null keys never match with `missing="never"`; `missing="equal"` allows null tuples to match. User-coded missing values remain literal keys under either policy. Key fields must use the same storage type. Cardinality checks enforce uniqueness on the sides named by `one_to_one`, `many_to_one`, or `one_to_many`; `many_to_many` permits duplicates. Duplicate output names require collision-free suffixes or the operation fails with `error.duplicate_fields`. Output follows left input order and right-match order; full joins append unmatched right rows in right input order.

Stack streams source batches directly to Parquet and has no operation-specific row-count cap. It validates all source schemas before writing. Stack output fields get new IDs, while source dataset and row IDs are retained in explicit provenance fields. Join output also gets new IDs and four source dataset/row provenance fields. Never treat source row IDs from different datasets as globally unique.

## Type, missing, order, and size rules

Transpose supports homogeneous `float64`, `int64`, `string`, or `bool` fields. It rejects mixed storage and multiple-response values. Raw nulls and coded values retain their stored values. Source row IDs label generated case columns; source field IDs/names occupy two provenance columns. The source row count therefore determines output width.

Pivot preserves first-seen group and category order. Null category values do not create output fields. Duplicate index/category pairs fail rather than being silently aggregated. Aggregation also preserves first-seen group order. Group keys use raw values, including null and coded-missing values. Aggregated rows do not retain source row IDs or a source-group membership map. `count` counts eligible nonmissing values; sum, mean, min, and max return null when a group has no eligible values. Integer sums remain exact and reject values outside int64 range. Floating sums and means use exact accumulation before the final float conversion and reject nonfinite output.

Join, transpose, pivot, and aggregate reject any source dataset above 100,000 rows. Join rejects a result above 100,000 rows while building its match list. Join also limits the combined input field count plus four provenance fields to 1,024. Transpose limits selected source fields plus two provenance columns to 1,024, and its generated case columns plus two provenance columns to 1,024. Pivot limits index and category output fields to 1,024. Pivot and aggregate also reject input schemas above 1,024 fields. These operations materialize bounded input rows in memory; they do not claim disk-backed global algorithms. Stack has no corresponding fixed row or column cap in this implementation.

## Evidence and native scope

`engine/fixtures/foundations/tables.json` contains original hand-calculated inputs and literal expected rows. `engine/tests/test_tables.py::test_hand_calculated_table_contract` loads the fixture. Adversarial tests cover provenance, null-key policy, cardinality, duplicate pivot cells, overlays, type errors, limits, and atomic cleanup. DATA-015 currently implements wide pivot only; a long-form unpivot operation remains pending. Native table-operation controls and saved transformation recipes remain pending. Engine acceptance does not establish native workflow acceptance or performance beyond the stated bounds.
