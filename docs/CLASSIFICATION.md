# Data classification and missing-value foundations

These original Phase 0 operations classify data and count cases. They implement no inferential tests. The engine adapter functions live in `openstat_engine.classification`; the caller passes its current store and immutable revision ID.

## Category mapping

`categories(store, revision, source, output, mapping, unmatched="error")` appends one string category variable. Each mapping entry has exactly `value` and `label`. Source values retain their declared storage type: integer values do not silently become strings, and booleans do not silently become integers. Multiple source values may share one output label. Duplicate source values, null mappings and mappings of coded-missing values are rejected. Response-set variables require explicit response operations and cannot be mapped as exclusive categories.

The output definition has a new field ID, unique name, string storage and nominal or ordinal measurement. Its levels follow the first occurrence of labels in the explicit mapping. A supplied level order must match that order. Identifier roles and output missing codes are rejected. A valid unmapped source value raises an error unless `unmatched="missing"` is explicitly selected.

## Interval and open-ended classes

`intervals(store, revision, source, output, classes, unmatched="error")` accepts numeric storage only. Every class explicitly provides `label`, `lower`, `upper`, `include_lower` and `include_upper`. A null bound represents an unbounded side and requires the corresponding inclusion flag to be false. Finite intervals require lower < upper. Integer comparisons retain their integer precision.

Classes must already be ordered and may not overlap. At a shared boundary both sides cannot include the value. For example, `[-2, 0)`, `[0, 10)` and `[10, 11]` place zero in the second class, ten in the third and eleven in the third. `(-infinity, 0)`, `[0, 10)` and `[10, infinity)` are explicit open-ended classes. Gaps are permitted but use the same explicit unmatched policy as category mapping.

For both derivations, null and coded-missing source values produce null in the new class variable. The unchanged source variable retains the distinction between those missing states. Derivation never replaces the source field.

## Contingency counts

`contingency(store, revision, row_field, column_field, mode="exclusive")` returns integer cell counts and row/column margins. It rejects continuous/discrete measurement and identifier roles; these require an explicit prior classification or metadata correction. Declared category levels, excluding missing codes, retain their order, including zero-count categories. Undeclared valid categories follow their first observed order. Values are displayed using the engine's existing canonical string representation, including `True` and `False` for bool storage.

Exclusive mode requires exclusive category variables. Each eligible case contributes one cell. `eligible_cases` is the complete-case denominator, and `pair_count` equals the sum of cell counts.

A response-set axis requires `mode="response_membership"`. Each eligible case contributes the Cartesian product of its two response sets (an exclusive value is a singleton). A case with an empty response set remains eligible but contributes no pairs. Thus pair totals and margins can exceed or be smaller than the eligible-case count. The result explicitly reports `denominator="response_pairs"`, `eligible_cases`, `pair_count` and `empty_response_cases`. No percentages or implicit weighting are calculated. The same response field on both axes means the explicitly requested within-case membership product, including the diagonal.

A null on either axis excludes the case. Otherwise, any coded-missing value excludes the case, including a missing-code member inside a response set. Null exclusion takes precedence when one case contains both missing kinds, making exclusion counts mutually exclusive. Tables above 1,000,000 cells are rejected before dense allocation.

## Missing-value audit

`missing_audit(store, revision, fields=None)` reports each selected field's null, coded-missing and valid case counts, as well as distinct missing-data patterns across selected fields sorted by case frequency and completeness. `empty_response` is a separate subset of valid response-set cases, not an additional missing category. A response set containing a user-coded missing member counts as one coded-missing case. `complete_cases` requires every selected field to be valid. The explicit denominator is the revision's total case count. Unknown/duplicate fields and empty field selections are rejected.

## Persistence and evidence

Reads use the store's projected, bounded stream with current sparse edits applied. Derivations write a new Parquet base in batches of at most 8,192 cases and clear the materialized overlay. Existing field IDs, stable row IDs, row order, context, observation unit, dataset identity and original revision files remain intact. Failed writes remove their incomplete new base. Classification and audit require no additional dependency.

The independent original nine-case fixture is `engine/fixtures/foundations/classification.json`. Its labels and tallies were assigned manually, with literal expectations and provenance. `engine/tests/test_classification.py::test_original_classification_contract` actually loads the fixture and covers DATA-016 through DATA-020. Separate edge tests cover alternate boundary conventions, int64 extrema, empty input, missing-only data, overlays spanning batches, noncontiguous stable IDs, malformed classes, invalid output metadata, response denominators and table size limits. Python verification does not establish native UI acceptance or a complete Phase 0 gate.
