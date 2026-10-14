# Derived-column operations

The original Phase 0 column engine lives in `engine/src/openstat_engine/columns.py`. Each operation returns an immutable dataset descriptor. It appends one fresh field UUID, preserves every existing field and actual row ID in the current order, materializes sparse edits, and leaves the source revision untouched. A failed operation removes its partial output and does not register a revision. Existing dataset context and observation-unit metadata are retained.

These operations are engine building blocks. Their native interaction, persisted transformation recipes and full reproducibility UI remain separate acceptance work. Saved projects contain resulting values; opening a project does not execute expressions.

## Operations and conventions

| Function | Feature | Contract |
| --- | --- | --- |
| `recode` | DATA-010 | Typed `{from, to}` pairs, exact source-value equality, up to 1,000 unique mappings. `unmatched` is `keep` or `null`. Source raw null always remains null. The output can use an explicit new storage type and does not inherit a closed codebook. Incompatible retained values reject the whole transformation. |
| `compute` | DATA-011 | Validated JSON expression tree with `field` and finite numeric `constant` leaves. Unary `negate`, `abs`, `sqrt`, `log`, `exp`; binary `add`, `subtract`, `multiply`, `divide`. No evaluation of Python, names, attributes, imports or code. Maximum depth 16 and 256 nodes per tree; validation completes before output allocation. Numeric fields only; the derived storage is float64. |
| `rank` | DATA-022 | Numeric ascending or descending ranks. Tie policies `average`, `min`, `max`, `dense`, `first` are explicit; `first` follows current row order within ties. One-based float64 ranks. Missing observations receive null. Integer sorting preserves int64 distinctions. |
| `lag` | DATA-023 | `direction` is `lag` or `lead`, `steps` is a positive integer. Shift follows current row order, including missing positions, with null padding. No grouping or implicit sorting. Original storage and codebook are retained. |
| `standardize` | DATA-024 | `(x-mean)/SD`, with explicit `ddof=1` (sample, default) or `ddof=0` (population). Raw/coded missing exclusion is defined below. Constant columns and insufficient observations reject with `error.zero_variance`. Centering before scaling preserves differences between adjacent large integers and avoids overflow for extreme finite float values. |
| `box_cox` | DATA-027 | Box-Cox power transform for strictly positive data ($y > 0$). If $\lambda \ne 0$: $(y^\lambda - 1)/\lambda$; if $\lambda = 0$: $\ln(y)$. Accepts explicit finite parameter `lmbda` or fits optimal $\hat{\lambda}$ via profile log-likelihood Brent minimization. Non-positive values reject with `error.transform_domain`; constant columns or $< 2$ observations reject with `error.zero_variance`. |
| `duplicates` | DATA-026 | Append a boolean flag for exact equality across selected fields. `keep=first` or `last` flags every repetition except that occurrence; `none` flags all members of repeated groups. Null compares equal to null. Coded missing values are literal values. Multiple-response arrays compare in their stored order. No rows are removed. |

Except duplicate detection, every API accepts a strictly boolean `include_missing_codes` option, default `false`. Raw null always remains missing. With exclusion, values whose string representation matches their field's declared missing-code key become null in the new column. With inclusion, they are ordinary values. Source cells and metadata stay unchanged. Duplicate detection deliberately compares source literals, including codes and nulls.

Computed float64 output has ordinary float64 arithmetic precision. Numeric constants and intermediate results must be finite; division by zero, invalid logarithm/square root, overflow and nonfinite results reject the operation with `error.transform_domain`. Null operands propagate null without evaluating an invalid operation on that row. An invalid expression structure is rejected even for an empty dataset.

## Resource limits

Recode and compute consume source rows in batches of at most 8,192, through `Store.iter_tables`, then write a new Parquet base. Each written batch reports its actual row count to the active job and checks cancellation. Cancellation removes partial output and does not register a revision. Sparse-overlay bookkeeping grows with the number of edits and variable values can have variable byte lengths; the batch count is not a universal byte limit.

Rank, lag/lead, standardization and duplicate detection reject datasets over 100,000 rows with `error.global_limit`. Their exact algorithms hold selected column values or duplicate keys in memory. Rank is O(n log n), duplicate detection is O(n) expected, and the remaining global algorithms are O(n). This is an explicit contributor implementation limit, not a claim of a streamed exact global algorithm or satisfaction of the 5-million-row performance gate.

## Evidence

`engine/fixtures/foundations/columns.json` is original hand-calculated data. Its acceptance test loads the fixture and compares recoding, expression evaluation, all tie policies, sample/population standardization, lag/lead and all duplicate policies. Expected answers are literal values, not generated by the functions being tested.

`engine/tests/test_columns.py` also checks immutable overlays and project round trips, noncontiguous stable IDs across a batch boundary, int64 neighbors near the maximum value, float values up to 1e308, raw versus coded missing values, empty data, malicious or oversized expression trees, a 256-node accepted tree and 257-node rejection before writing, cyclic expressions, strict option types, global memory limits and atomic cleanup on numerical failures or cancellation. Native UI acceptance and both-architecture validation are pending.
