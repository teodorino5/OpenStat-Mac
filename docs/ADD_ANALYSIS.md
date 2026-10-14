# Adding an analysis module

Phase 0 is still active. Do not register statistical procedures until every foundation row has passed its gate. The following tutorial defines the future contribution workflow; it does not imply an analysis registry exists today.

1. Add a stable feature ID or refine an existing row in docs/feature_catalog.json. Record a precise public method, current evidence level, eligible variable roles/scales, assumptions and license-reviewed library.
2. Record numerical conventions: missing values, weights, ties, divisor, quantile definition, alternative hypothesis, confidence level and undefined cases. Never silently substitute a different method.
3. Create an independent reference fixture with provenance, expected values, parameterization and tolerances. Use hand arithmetic, public certified data or a genuinely independent implementation. The same routine used twice is not independent validation.
4. Implement a typed engine procedure and a validation/RPC adapter. Return full-precision typed tables, original learning steps, declarative chart data and localized message keys. Do not print data on protocol stdout.
5. Add acceptance tests marked with each stable feature ID. Reference tests load their fixtures through the `reference_fixture` helper so the coverage gate records actual use. Include boundaries, missing data, constants and unsupported weights.
6. Register nonmodal Swift inspector controls, keyboard alternatives, accessibility descriptions and English/Czech strings. Add code-export equivalence checks when that exporter exists.
7. Run the complete applicable checks. Update status only after successful tests, tracked independent fixtures and phase validation. Run `scripts/feature_matrix.py --write`, then commit with a Conventional Commit.

The coverage validator rejects absent, failed, skipped or unmarked acceptance tests, stale execution evidence and missing/unloaded/untracked fixtures. An implemented row can remain unverified until independent expected values exist. Do not invent a fixture to pass a gate.
