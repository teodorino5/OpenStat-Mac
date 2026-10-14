# Numerical conventions

No numerical statistical procedure is implemented yet. These conventions bind future procedures; current data behavior is tested separately.

Physical nulls remain separate from declared raw missing codes. Input data is never silently replaced with made-up statistics. Identifiers are not eligible for statistics merely because stored as numbers. Multiple responses form sets distinct from mutually exclusive nominal levels.

Default descriptive spread will use sample variance with n−1; explicit population context will use n. Every saved analysis records and displays the selected convention. A singleton sample variance is undefined; a singleton population variance is zero. Constant-data correlation is undefined.

Quantiles default to Hyndman-Fan type 7 with all nine definitions available. Mode retains ties. Geometric means require strictly positive values. Within/between decomposition uses centered sums of squares and the same divisor. Open-ended grouped classes have no invented midpoint.

Numerical values remain full precision in protocol and projects; rounding is presentation only. Czech decimal commas are accepted by typed cell parsing. The engine CSV API supports explicit comma-decimal parsing when the delimiter differs. The current native import picker does not yet expose those options.

Future fixtures must state method, exact source/independent calculation and tolerances. NIST StRD does not certify every proposed statistic. Current infrastructure fixtures are literal original typed-data contracts, not numerical analysis references.
