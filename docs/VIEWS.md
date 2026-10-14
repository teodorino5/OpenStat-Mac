# Case views

The Phase 0 case operations provide typed selection, filtering, stable sorting, and weight inspection. They operate on the current immutable revision, including sparse edits already applied by `Store.iter_tables`.

## Selection and filtering

`dataset.select` evaluates a typed predicate and reports total, true, false, and unknown case counts. It does not create a revision. `dataset.filter` writes a new revision containing only cases whose predicate is true. False and unknown cases are excluded. Filtering preserves source row IDs and their current order; the source revision remains unchanged.

Predicates support exact `eq`/`ne`, numeric comparisons, declared ordinal-level comparisons, `in`, multiple-response `contains`, and explicit `is_null`, `is_coded_missing`, and `is_missing` tests. `and`, `or`, and `not` use three-valued logic: missing comparisons are unknown, while decisive false/true results follow Kleene logic. Raw null and user-coded missing remain distinguishable. A coded missing value yields unknown for ordinary comparisons. For multiple-response fields, any coded-missing member marks the whole response set missing.

Predicate trees have a maximum depth of 16 and at most 64 children per Boolean node; `not` requires one child. `in` accepts 1 to 1,024 non-null values. The native panel supports up to 16 flat conditions joined by `and` or `or`; nested Boolean trees and `in` remain engine-only. Selection and filtering scan in batches and have no operation-specific row-count cap. Source import and project limits still apply. There is no separate total-node budget for predicate trees yet.

## Sorting

`dataset.sort` accepts one or more distinct field IDs, a direction per field, and explicit null placement (`first` or `last`). Sort keys may use any storage except multiple-response arrays. Declared ordinal levels sort in codebook order. Raw null and coded missing values both use the selected missing placement; ties preserve input order. The output revision retains the original row IDs in sorted order.

The engine sorts bounded input batches into temporary Parquet runs, then performs stable multi-pass merges with a maximum fan-in of 16. Temporary runs are removed after success or failure, and partial output is removed on failure. Sorting has no operation-specific row-count cap, but temporary disk usage scales with input size. The implementation has not passed the five-million-row performance gate.

## Weight inspection

`dataset.weights` inspects one numeric, non-identifier field. It reports eligible, missing, zero, and total weight counts. Null and coded-missing values are excluded. Frequency weights must be nonnegative integers and are totaled exactly; `total_weight_exact` returns their decimal integer representation. Analytic weights must be finite and nonnegative; their sum uses compensated floating-point summation and rejects overflow.

Weight inspection does not change data, save an active weight setting, or pass weights into statistical procedures. The native panel displays the inspection only. Frequency and analytic procedures need method-specific dispatch before inferential or descriptive methods can claim weight support.

## Current scope

The native panel exposes flat predicate editing, stable sorting, and frequency/analytic weight inspection. It does not expose nested Boolean construction, `in` lists, explicit missing-placement controls for predicates, or saved/reusable filter and sort recipes. Engine API coverage and native workflow coverage are separate acceptance claims. No statistical output charts or summaries are produced by these case operations.
