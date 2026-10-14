# Feature matrix

Audit date: 2026-10-14 (Europe/Prague). Phase 0 active; implementation authorized.

**Coverage: 25 of 353 planned functions implemented, 20 verified against reference values.**

## Scope and evidence limits

This is a complete register of the functions explicitly scoped in this draft, expanded from the supplied brief and the public module inventories reviewed below. It is **not a claim of an exhaustive vendor-function census**. Unknown and excluded families appear separately. The public sources vary by version and license tier. The core module inventory is version 14.0 (V01); 14.0.1, 14.1 and 14.3 sources are explicitly labeled. Older or undated sources provide discovery evidence only. Function details unavailable from a public source are not presented as confirmed vendor features.

All labels, method descriptions and proposed workflows here are original. No vendor images, sample datasets, help passages, code, binaries or internal file specifications are stored. Vendor source links are research provenance, never app branding.

Each row is one independently accepted function unit. A distribution calculator is one unit whose contract includes all listed operations; counting every tail/parameter combination would artificially inflate coverage. Shared adapters do not earn multiple rows without acceptance tests for each row. Product infrastructure and numerical methods are counted separately by module and phase; README totals always use this declared row-based denominator. Unknown/not-planned rows are excluded from the denominator and reported separately.

**Evidence notation:** `brief` = directly requested or original extension, vendor equivalence unconfirmed; `Vxx:function` = function explicitly named in the linked public page; `Vxx:module` = only parent family confirmed, this function is a proposed scoped interpretation; `V14:topic` = search-index topic evidence, lower confidence because direct page body was unavailable; `Vxx:discovery` = older/undated source, not 14.0 confirmation. Method references are separate from vendor evidence.

**Library mappings are candidate coverage, not implemented capabilities.** All require adapters, pinned-version compatibility checks and a complete permissive-license artifact audit. `Needs custom implementation` means public method primitives may be reused, but a maintained engine procedure does not already cover the full contract.

The five accepted rows are engine data foundations. The three verified rows share an original data/codebook acceptance fixture, not a statistical calculation. Native workflow, scale, runtime and accessibility gates remain incomplete.

## Phase totals

| Phase | Planned functions | Implemented | Verified |
| --- | ---: | ---: | ---: |
| 0 | 47 | 25 | 20 |
| 1 | 65 | 0 | 0 |
| 2 | 37 | 0 | 0 |
| 3 | 62 | 0 | 0 |
| 4 | 81 | 0 | 0 |
| 5 | 61 | 0 | 0 |

## Planned functions


### Data foundations

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| DATA-001 | Variable roles and measurement types | Storage type plus identifier/characteristic role and measurement scale | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original openstat_engine metadata and validation | 0 | implemented | brief | `engine/tests/test_store.py::test_storage_scale_role_round_trip` | — |
| DATA-002 | Population and sample context | Observation unit, sampling scope and descriptive/inferential labels | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original openstat_engine metadata and validation | 0 | implemented | brief | `engine/tests/test_store.py::test_context_is_explicit_and_persisted` | — |
| DATA-003 | Category labels and ordered levels | Explicit codebook with category order and value labels | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original openstat_engine metadata and validation | 0 | verified against reference values | brief | `engine/tests/test_reference.py::test_original_codebook_contract`, `engine/tests/test_store.py::test_codebook_and_raw_missing_preserve_source` | `engine/fixtures/foundations/codebook.json` |
| DATA-004 | Multiple-response representation | Response sets distinct from mutually exclusive categories | [M08](https://pandas.pydata.org/docs/reference/index.html) | pyarrow list arrays + original set validation | 0 | verified against reference values | brief | `engine/tests/test_reference.py::test_original_codebook_contract`, `engine/tests/test_store.py::test_codebook_and_raw_missing_preserve_source` | `engine/fixtures/foundations/codebook.json` |
| DATA-005 | Missing-value definitions | Nulls and named missing codes; no silent numeric substitution | [M08](https://pandas.pydata.org/docs/reference/index.html) | pyarrow validity + original missing-code metadata | 0 | verified against reference values | brief | `engine/tests/test_reference.py::test_original_codebook_contract`, `engine/tests/test_store.py::test_codebook_and_raw_missing_preserve_source` | `engine/fixtures/foundations/codebook.json` |
| DATA-006 | Case selection | Typed Boolean predicates with three-valued missing logic | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original safe predicates and stable bounded external merge; see docs/VIEWS.md | 0 | verified against reference values | brief | `engine/tests/test_views.py::test_original_case_contract` | `engine/fixtures/foundations/cases.json` |
| DATA-007 | Case weights | Frequency and analytic weights with method-specific validation | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original frequency/analytic weight inspection; persistence and method dispatch pending | 0 | in progress | brief | — | — |
| DATA-008 | Sort cases | Stable sort with explicit missing placement | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original safe predicates and stable bounded external merge; see docs/VIEWS.md | 0 | verified against reference values | brief | `engine/tests/test_views.py::test_original_case_contract` | `engine/fixtures/foundations/cases.json` |
| DATA-009 | Filter cases | Predicate evaluation and retained row identities | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original safe predicates and stable bounded external merge; see docs/VIEWS.md | 0 | verified against reference values | brief | `engine/tests/test_views.py::test_original_case_contract` | `engine/fixtures/foundations/cases.json` |
| DATA-010 | Recode values | Versioned explicit mapping and unmatched-value policy | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original immutable column operations; global operations bounded to 100k cases | 0 | verified against reference values | brief | `engine/tests/test_columns.py::test_original_columns_contract` | `engine/fixtures/foundations/columns.json` |
| DATA-011 | Compute variables | Typed expression tree; function allowlist and autocomplete | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original safe numeric expression tree; autocomplete pending | 0 | in progress | brief | — | — |
| DATA-012 | Transpose table | Dimension exchange with size checks and metadata policy | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original typed table operations; see docs/TABLE_OPERATIONS.md for limits | 0 | verified against reference values | brief | `engine/tests/test_tables.py::test_hand_calculated_table_contract` | `engine/fixtures/foundations/tables.json` |
| DATA-013 | Join tables | Keyed join with cardinality and unmatched-row checks | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original typed table operations; see docs/TABLE_OPERATIONS.md for limits | 0 | verified against reference values | brief | `engine/tests/test_tables.py::test_hand_calculated_table_contract` | `engine/fixtures/foundations/tables.json` |
| DATA-014 | Stack tables | Schema-compatible row concatenation | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original typed table operations; see docs/TABLE_OPERATIONS.md for limits | 0 | verified against reference values | brief | `engine/tests/test_tables.py::test_hand_calculated_table_contract` | `engine/fixtures/foundations/tables.json` |
| DATA-015 | Unstack and reshape | Long/wide reshape with duplicate-key checks | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original bounded wide pivot; long reshape pending | 0 | in progress | brief | — | — |
| DATA-016 | Simple classification | Disjoint exhaustive categories and explicit unknown handling | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original typed classification and declared contingency denominators | 0 | verified against reference values | brief | `engine/tests/test_classification.py::test_original_classification_contract` | `engine/fixtures/foundations/classification.json` |
| DATA-017 | Interval classification | Endpoint ownership, coverage, overlaps and gaps | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original typed classification and declared contingency denominators | 0 | verified against reference values | brief | `engine/tests/test_classification.py::test_original_classification_contract` | `engine/fixtures/foundations/classification.json` |
| DATA-018 | Open-ended classes | Infinite bounds and explicit undefined-midpoint policy | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original typed classification and declared contingency denominators | 0 | verified against reference values | brief | `engine/tests/test_classification.py::test_original_classification_contract` | `engine/fixtures/foundations/classification.json` |
| DATA-019 | Contingency counts and margins | Two-way count table with row/column totals | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original typed classification and declared contingency denominators | 0 | verified against reference values | brief | `engine/tests/test_classification.py::test_original_classification_contract` | `engine/fixtures/foundations/classification.json` |
| DATA-020 | Missing-data audit | Per-variable and pattern-based missing counts | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original per-field missing audit; full missing-pattern counts pending | 0 | in progress | brief | — | — |
| DATA-021 | Outlier flags | Declared Tukey fences and optional standardized scores | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original exact type-7 quartiles and strict Tukey fences; 100k-case limit | 0 | verified against reference values | brief | `engine/tests/test_outliers.py::test_hand_calculated_outlier_contract` | `engine/fixtures/foundations/outliers.json` |
| DATA-022 | Ranks | Average/min/max/dense ranks with documented ties | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original immutable column operations; global operations bounded to 100k cases | 0 | verified against reference values | brief | `engine/tests/test_columns.py::test_original_columns_contract` | `engine/fixtures/foundations/columns.json` |
| DATA-023 | Lag and lead columns | Ordered offsets within optional groups | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original immutable column operations; global operations bounded to 100k cases | 0 | verified against reference values | brief | `engine/tests/test_columns.py::test_original_columns_contract` | `engine/fixtures/foundations/columns.json` |
| DATA-024 | Standardize columns | Declared center, scale and zero-scale rejection | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original immutable column operations; global operations bounded to 100k cases | 0 | verified against reference values | brief | `engine/tests/test_columns.py::test_original_columns_contract` | `engine/fixtures/foundations/columns.json` |
| DATA-025 | Group aggregation | Typed split-apply-combine with row provenance | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original bounded count/sum/mean/min/max; grouped row provenance pending | 0 | in progress | brief | — | — |
| DATA-026 | Duplicate detection | Declared keys and stable duplicate identities | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original immutable column operations; global operations bounded to 100k cases | 0 | verified against reference values | brief | `engine/tests/test_columns.py::test_original_columns_contract` | `engine/fixtures/foundations/columns.json` |
| DATA-027 | Box-Cox transformation | Positive-data power transform with fitted lambda | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.boxcox | 0 | not started | V01:function | — | — |
| DATA-028 | CSV import and export | Streaming delimiter parser with explicit schema and encoding | [M08](https://pandas.pydata.org/docs/reference/index.html) | Arrow CSV import + original streaming CSV export and locale options | 0 | implemented | brief | `engine/tests/test_interchange.py::test_flat_text[,-.]`, `engine/tests/test_interchange.py::test_flat_text[;-,]`, `engine/tests/test_interchange.py::test_numeric_flat_text_import_export[,-DATA-028]`, `engine/tests/test_interchange.py::test_numeric_flat_text_import_export[\t-DATA-029]`, `engine/tests/test_store.py::test_streamed_locale_import[,-.-Name,Value\ncedar,1.5\nclover,2.75\n-expected0]`, `engine/tests/test_store.py::test_streamed_locale_import[;-,-Name;Value\n\u010derven\xe1;1,5\nmodr\xe1;2,75\n-expected1]`, `engine/tests/test_store.py::test_streamed_locale_import[\t-.-Name\tValue\ncedar\t1.5\nclover\t2.75\n-expected2]` | — |
| DATA-029 | TSV import and export | Tab-separated interchange with quoting | [M08](https://pandas.pydata.org/docs/reference/index.html) | Arrow TSV import + original quoted TSV export | 0 | implemented | brief | `engine/tests/test_interchange.py::test_flat_text[\t-.]`, `engine/tests/test_interchange.py::test_numeric_flat_text_import_export[,-DATA-028]`, `engine/tests/test_interchange.py::test_numeric_flat_text_import_export[\t-DATA-029]`, `engine/tests/test_store.py::test_streamed_locale_import[,-.-Name,Value\ncedar,1.5\nclover,2.75\n-expected0]`, `engine/tests/test_store.py::test_streamed_locale_import[;-,-Name;Value\n\u010derven\xe1;1,5\nmodr\xe1;2,75\n-expected1]`, `engine/tests/test_store.py::test_streamed_locale_import[\t-.-Name\tValue\ncedar\t1.5\nclover\t2.75\n-expected2]` | — |
| DATA-030 | Excel import and export | Workbook cells, sheets and typed values; import formulas as cached values | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original bounded OOXML subset; cached formulas and broader workbook support pending | 0 | in progress | brief | — | — |
| DATA-031 | JSON import and export | Declared records or column schema; streaming large input | [M08](https://pandas.pydata.org/docs/reference/index.html) | Original bounded typed JSON envelope; general records and large streaming import pending | 0 | in progress | brief | — | — |
| DATA-032 | Parquet import and export | Columnar schema-preserving interchange | [M08](https://pandas.pydata.org/docs/reference/index.html) | PyArrow columnar interchange with typed schema metadata | 0 | implemented | brief | `engine/tests/test_interchange.py::test_rich_roundtrip[parquet]`, `engine/tests/test_interchange.py::test_empty_and_batched[parquet]`, `engine/tests/test_interchange.py::test_noncontiguous_stable_ids_and_order[parquet]` | — |
| DATA-033 | SPSS interchange | SAV read/write with value-label and missing-code reconciliation | [M20](https://github.com/Roche/pyreadstat) | Audited PyReadStat SAV subset; missing declarations lost on export | 0 | in progress | brief | — | — |
| DATA-034 | Stata interchange | DTA read/write with explicit format version | [M20](https://github.com/Roche/pyreadstat) | Audited PyReadStat DTA subset; tagged missing and format reconciliation pending | 0 | in progress | brief | — | — |
| DATA-035 | SAS dataset reading | SAS7BDAT read only; preserve metadata where available | [M20](https://github.com/Roche/pyreadstat) | Audited PyReadStat SAS7BDAT reader; source metadata persistence and genuine fixture pending | 0 | in progress | brief | — | — |
| DATA-036 | SQLite import and export | Read-only import query and transactional explicit export | [M19](https://www.sqlite.org/lang.html) | Original typed SQLite envelope; general read-only table/query import pending | 0 | in progress | brief | — | — |
| DATA-037 | Native project package | Versioned manifest, immutable Parquet revisions and JSON specs | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom implementation | 0 | in progress | brief | — | — |
| DATA-038 | Virtualized grid data access | Paged visible cells and bounded cache independent of total rows | [M09](https://arrow.apache.org/docs/python/dataset.html) | NSTableView + Arrow sidecar | 0 | in progress | brief | `engine/tests/test_store.py::test_sparse_revisions_allow_undo_without_mutating_base`, `engine/tests/test_store.py::test_extend_preserves_revisions_overlays_ids_and_save_open` | — |
| DATA-039 | Undo, redo and autosave | Reversible edit journal and atomic snapshot publication | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | NSDocument / UndoManager + custom journal | 0 | verified against reference values | brief | `engine/tests/test_store.py::test_undo_redo_autosave_contract` | `engine/fixtures/foundations/undo_redo.json` |

### Descriptive statistics and tables

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| DESC-001 | Absolute frequencies | Category or interval counts | [M08](https://pandas.pydata.org/docs/reference/index.html) | NumPy / pandas | 1 | not started | V02:function | — | — |
| DESC-002 | Relative frequencies | Counts divided by declared eligible denominator | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy + custom denominator policy | 1 | not started | brief | — | — |
| DESC-003 | Cumulative counts | Ordered running sum; unavailable for unordered categories | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy cumsum | 1 | not started | brief | — | — |
| DESC-004 | Cumulative proportions | Ordered running relative frequencies | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy cumsum | 1 | not started | brief | — | — |
| DESC-005 | Grouped frequency summaries | Interval counts with exact boundaries and overflow handling | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy histogram + custom class validation | 1 | not started | brief | — | — |
| DESC-006 | Multiple-response summaries | Case-based and response-based denominators shown separately | [M08](https://pandas.pydata.org/docs/reference/index.html) | Needs custom implementation | 1 | not started | V02:function | — | — |
| DESC-007 | Grouped descriptive summaries | Independent statistics per declared grouping levels | [M08](https://pandas.pydata.org/docs/reference/index.html) | pandas + statistics adapters | 1 | not started | V02:function | — | — |
| DESC-008 | Banner-style summary tables | Crossed categorical groups with nested display and explicit bases | [M08](https://pandas.pydata.org/docs/reference/index.html) | Needs custom implementation | 1 | not started | V02:function | — | — |
| DESC-009 | Minimum | Smallest eligible value | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy min | 1 | not started | brief | — | — |
| DESC-010 | Maximum | Largest eligible value | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy max | 1 | not started | brief | — | — |
| DESC-011 | Modes including ties | All values attaining maximum frequency | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom wrapper; pandas mode | 1 | not started | brief | — | — |
| DESC-012 | Arbitrary quantiles | Hyndman-Fan types 1-9 and named NumPy method | [M03](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html) | numpy.quantile | 1 | not started | brief | — | — |
| DESC-013 | Quartiles | Quantiles at 0.25, 0.50 and 0.75 using saved method | [M14](https://doi.org/10.1080/00031305.1996.10473566) | numpy.quantile | 1 | not started | brief | — | — |
| DESC-014 | Median | Central order statistic; midpoint for even sample | [M01](https://www.itl.nist.gov/div898/handbook/) | numpy.median | 1 | not started | brief | — | — |
| DESC-015 | Arithmetic mean | Sum divided by eligible count | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy mean; stable reduction | 1 | not started | brief | — | — |
| DESC-016 | Weighted mean | Sum of weight-times-value divided by sum of weights | [M01](https://www.itl.nist.gov/div898/handbook/) | numpy.average + weight validation | 1 | not started | brief | — | — |
| DESC-017 | Combined group mean | Size-weighted average of group means | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 1 | not started | brief | — | — |
| DESC-018 | Geometric mean | Exp of average log, positive finite inputs only | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.gmean | 1 | not started | brief | — | — |
| DESC-019 | Mean absolute increment | Last minus first divided by n minus one on declared ordering | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 1 | not started | brief | — | — |
| DESC-020 | Growth coefficients | Successive value ratios; zero denominators rejected | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 1 | not started | brief | — | — |
| DESC-021 | Increment coefficients and percentage rates | Growth coefficient minus one; averaging blocked | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 1 | not started | brief | — | — |
| DESC-022 | Mean growth coefficient | Geometric mean of positive successive ratios | [M01](https://www.itl.nist.gov/div898/handbook/) | SciPy + custom ordered-series validation | 1 | not started | brief | — | — |
| DESC-023 | Range | Maximum minus minimum | [M01](https://www.itl.nist.gov/div898/handbook/) | numpy.ptp | 1 | not started | brief | — | — |
| DESC-024 | Interquartile range | Third quartile minus first using saved method | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy quantile | 1 | not started | brief | — | — |
| DESC-025 | Mean absolute deviation | Average absolute difference from declared constant, median default | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 1 | not started | brief | — | — |
| DESC-026 | Population variance | Centered sum of squares divided by n | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy var ddof=0 | 1 | not started | brief | — | — |
| DESC-027 | Sample variance | Centered sum of squares divided by n minus one; n >= 2 | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy var ddof=1 | 1 | not started | brief | — | — |
| DESC-028 | Standard deviation | Square root of selected variance convention | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy std | 1 | not started | brief | — | — |
| DESC-029 | Coefficient of variation | SD divided by positive mean; percentage convention recorded | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom domain policy | 1 | not started | brief | — | — |
| DESC-030 | Total sum of squares | Sum of squared deviations from mean | [M01](https://www.itl.nist.gov/div898/handbook/) | NumPy stable reduction | 1 | not started | brief | — | — |
| DESC-031 | Variance decomposition | TSS = within-group SS + between-group SS; shared denominator | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 1 | not started | brief | — | — |
| DESC-032 | Covariance | Centered product sum with declared sample/population divisor | [M01](https://www.itl.nist.gov/div898/handbook/) | numpy.cov + custom conventions | 1 | not started | brief | — | — |
| DESC-033 | Pearson correlation | Standardized covariance; zero-scale inputs undefined | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.pearsonr | 1 | not started | V02:function | — | — |
| DESC-034 | Correlation matrix | Pairwise coefficients with per-cell eligible counts and missing policy | [M08](https://pandas.pydata.org/docs/reference/index.html) | NumPy / pandas + custom provenance | 1 | not started | V02:function | — | — |
| DESC-035 | Skewness | Fisher-Pearson third standardized moment; bias convention explicit | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.skew | 1 | not started | brief | — | — |
| DESC-036 | Excess kurtosis | Fourth standardized moment minus 3; bias convention explicit | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.kurtosis fisher=True | 1 | not started | brief | — | — |
| DESC-037 | Robustness annotations | Original explanation of outlier influence and breakdown limits | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs original authored content | 1 | not started | brief | — | — |
| DESC-038 | Formula and working panels | Statistic formula, eligible inputs, substitutions and exact/approximate provenance | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom explanation adapters | 1 | not started | brief | — | — |
| DESC-039 | Grouped location estimates | Midpoint-based estimates only for finite intervals; explicit approximation | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 1 | not started | brief | — | — |
| DESC-040 | Grouped variability estimates | Weighted midpoint spread; refuse unsupported open-class estimates | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 1 | not started | brief | — | — |

### Charts and graph interaction

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| PLOT-001 | Single-series pie | Proportions of nonnegative parts of one total; reject multi-series | [M17](https://developer.apple.com/documentation/charts) | Swift Charts SectorMark | 1 | not started | V05:function | — | — |
| PLOT-002 | Categorical bars | Discrete categories separated by gaps | [M17](https://developer.apple.com/documentation/charts) | Swift Charts BarMark | 1 | not started | V05:function | — | — |
| PLOT-003 | Histograms | Contiguous numerical intervals; unequal-width density scaling | [M17](https://developer.apple.com/documentation/charts) | Swift Charts / Core Graphics | 1 | not started | V05:function | — | — |
| PLOT-004 | Clustered bars | Separate bars per category and series with common basis | [M17](https://developer.apple.com/documentation/charts) | Swift Charts | 1 | not started | brief | — | — |
| PLOT-005 | Time-series lines | Chronological line plot; optional explicitly labeled second axis | [M17](https://developer.apple.com/documentation/charts) | Swift Charts + custom dual-axis layout | 1 | not started | V05:function | — | — |
| PLOT-006 | Radar plot | Radial axes with declared comparable scale and original layout | [M17](https://developer.apple.com/documentation/charts) | Core Graphics custom renderer | 1 | not started | brief | — | — |
| PLOT-007 | Box plot | Quartiles, whiskers; mild outliers at 1.5 IQR and extremes at 3 IQR | [M17](https://developer.apple.com/documentation/charts) | Core Graphics custom renderer | 1 | not started | V05:function | — | — |
| PLOT-008 | Scatter plot | Paired numerical values with explicit omissions | [M17](https://developer.apple.com/documentation/charts) | Swift Charts PointMark | 1 | not started | V05:function | — | — |
| PLOT-009 | Distribution-shape sketches | Original symmetric/skewed and tail-weight illustrations | [M17](https://developer.apple.com/documentation/charts) | Core Graphics custom renderer | 1 | not started | brief | — | — |
| PLOT-010 | Error bars | Declared confidence interval, SD or SE; no ambiguous generic error | [M17](https://developer.apple.com/documentation/charts) | Swift Charts + engine intervals | 1 | not started | V05:function | — | — |
| PLOT-011 | Range plot | Declared min/max or interval endpoints | [M17](https://developer.apple.com/documentation/charts) | Swift Charts | 1 | not started | V05:function | — | — |
| PLOT-012 | Scatter with marginal summaries | Joint scatter plus aligned marginal histogram/box plot | [M17](https://developer.apple.com/documentation/charts) | Native composite chart | 1 | not started | V05:function | — | — |
| PLOT-013 | Faceted charts | Same chart and comparable scales across grouping levels | [M17](https://developer.apple.com/documentation/charts) | Native chart layout | 1 | not started | V05:function | — | — |
| PLOT-014 | Linked point selection | Row-ID brushing synchronized with grid; explicit sampling labels | [M17](https://developer.apple.com/documentation/charts) | Needs custom selection model | 1 | not started | brief | — | — |
| PLOT-015 | Chart PNG export | Offscreen rendering at explicit scale and resolution | [M17](https://developer.apple.com/documentation/charts) | Core Graphics / ImageIO | 1 | not started | brief | — | — |
| PLOT-016 | Chart PDF export | Vector presentation of chart primitives | [M17](https://developer.apple.com/documentation/charts) | Core Graphics PDF | 1 | not started | brief | — | — |
| PLOT-017 | Chart SVG export | Shared scene model serialized as accessible SVG | [M17](https://developer.apple.com/documentation/charts) | Needs custom SVG renderer | 1 | not started | brief | — | — |

### Probability and combinatorics

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| PROB-001 | Classical probability | Favorable over equally likely outcomes with assumption stated | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | Needs custom validation | 2 | not started | brief | — | — |
| PROB-002 | Conditional probability | Joint probability divided by conditioning probability; denominator > 0 | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | Needs custom validation | 2 | not started | brief | — | — |
| PROB-003 | Combinations | Exact binomial coefficient | [M10](https://docs.python.org/3.12/library/math.html) | math.comb | 2 | not started | brief | — | — |
| PROB-004 | Permutations | Exact ordered selection count | [M10](https://docs.python.org/3.12/library/math.html) | math.perm | 2 | not started | brief | — | — |
| PROB-005 | Discrete-table moments | Validated support/probability table; E[X] and E[X squared] minus mean squared | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | NumPy + custom validation | 2 | not started | brief | — | — |
| PROB-006 | Bernoulli calculator | PMF, CDF, inclusive tails, inverse CDF, moments and modes | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.bernoulli | 2 | not started | brief | — | — |
| PROB-007 | Binomial calculator | PMF, CDF, inclusive tails, inverse CDF, moments and tied modes | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.binom | 2 | not started | brief | — | — |
| PROB-008 | Hypergeometric calculator | Finite-population PMF, CDF, inclusive tails, moments and modes | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.hypergeom | 2 | not started | brief | — | — |
| PROB-009 | Uniform calculator | Density, CDF, inverse CDF, moments and interval/tail area | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.uniform | 2 | not started | brief | — | — |
| PROB-010 | Normal calculator | Density, CDF, inverse CDF, moments and interval/tail area | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.norm | 2 | not started | brief | — | — |
| PROB-011 | Student t calculator | Density, CDF, inverse CDF and existence conditions for moments | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.t | 2 | not started | brief | — | — |
| PROB-012 | Chi-square calculator | Density, CDF, inverse CDF and moments | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.chi2 | 2 | not started | brief | — | — |
| PROB-013 | F calculator | Density, CDF, inverse CDF and existence conditions for moments | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.f | 2 | not started | brief | — | — |
| PROB-014 | Normal standardization | z = (x minus mu) divided by sigma with parameter convention shown | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | Needs custom explanation adapter | 2 | not started | brief | — | — |
| PROB-015 | Distribution plots | Discrete masses or density with shaded areas and quantile lines | [M17](https://developer.apple.com/documentation/charts) | Swift Charts + custom area geometry | 2 | not started | brief | — | — |
| PROB-016 | Minimum trials for a success | Solve 1 minus (1 minus p)^n >= level using stable logs and integer check | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | Needs custom implementation | 2 | not started | brief | — | — |
| PROB-017 | Independent normal sums | Mean n*mu and variance n*sigma squared; independence explicit | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + custom explanation | 2 | not started | brief | — | — |
| PROB-018 | Independent normal averages | Mean mu and variance sigma squared divided by n | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + custom explanation | 2 | not started | brief | — | — |
| PROB-019 | Normal square to chi-square | U squared for standard normal gives chi-square with df=1 | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + original derivation | 2 | not started | brief | — | — |
| PROB-020 | Sum of normal squares | Sum of independent squared standard normals gives chi-square df=n | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + original derivation | 2 | not started | brief | — | — |
| PROB-021 | Normal and chi-square t ratio | Independent U and V, U divided by sqrt(V/df) | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + original derivation | 2 | not started | brief | — | — |
| PROB-022 | Chi-square F ratio | Independent chi-square values divided by their df then ratio | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + original derivation | 2 | not started | brief | — | — |
| PROB-023 | Hypergeometric approximation | Binomial approximation with visible sampling fraction and declared threshold | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + custom warning policy | 2 | not started | brief | — | — |
| PROB-024 | Binomial normal approximation | Require n*p*(1-p) > 9; optional continuity correction; exact comparison | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + custom interval adapter | 2 | not started | brief | — | — |
| PROB-025 | User-defined density | Restricted formula, support, nonnegativity, normalization, quadrature and quantile roots | [M12](https://docs.scipy.org/doc/scipy/reference/integrate.html) | scipy.integrate / optimize + custom parser | 2 | not started | brief | — | — |
| PROB-026 | Parameter-driven problem solver | Structured distribution inputs and original step-by-step answer | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | Needs custom deterministic explanation | 2 | not started | brief | — | — |
| PROB-027 | Poisson calculator | PMF, CDF, inclusive tails, quantiles and moments | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.poisson | 2 | not started | V14:topic | — | — |
| PROB-028 | Beta calculator | Density, CDF, quantiles and moments | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.beta | 2 | not started | V14:topic | — | — |
| PROB-029 | Gamma calculator | Density, CDF, quantiles and moments | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.gamma | 2 | not started | V14:topic | — | — |
| PROB-030 | Exponential calculator | Density, CDF, quantiles and moments | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.expon | 2 | not started | V14:topic | — | — |
| PROB-031 | Lognormal calculator | Density, CDF, quantiles; log-scale parameters explicit | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.lognorm | 2 | not started | V14:topic | — | — |
| PROB-032 | Weibull calculator | Density, CDF, quantiles and moments; shape/scale explicit | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.weibull_min | 2 | not started | V14:topic | — | — |
| PROB-033 | Logistic calculator | Density, CDF, quantiles and moments | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.logistic | 2 | not started | V14:topic | — | — |
| PROB-034 | Cauchy calculator | Density, CDF and quantiles; mean and variance undefined | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.cauchy | 2 | not started | V14:topic | — | — |
| PROB-035 | Noncentral t calculator | Density, CDF and quantiles with noncentrality parameter | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.nct | 2 | not started | V14:topic | — | — |
| PROB-036 | Noncentral chi-square calculator | Density, CDF and quantiles with noncentrality parameter | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.ncx2 | 2 | not started | V14:topic | — | — |
| PROB-037 | Noncentral F calculator | Density, CDF and quantiles with noncentrality parameter | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.ncf | 2 | not started | V14:topic | — | — |

### Inference and basic tests

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| TEST-001 | Mean confidence interval | t-based interval with assumptions, df and confidence level | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + custom adapter | 3 | not started | brief | — | — |
| TEST-002 | Proportion confidence interval | Wilson and exact binomial intervals | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.stats.proportion | 3 | not started | V14:topic | — | — |
| TEST-003 | Variance confidence interval | Chi-square interval under independent normal observations | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + custom adapter | 3 | not started | brief | — | — |
| TEST-004 | Correlation confidence interval | Fisher-z interval with sample-size restrictions | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy PearsonRResult.confidence_interval | 3 | not started | brief | — | — |
| TEST-005 | One-sample t test | Student t statistic for a specified mean | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.ttest_1samp | 3 | not started | V02:function | — | — |
| TEST-006 | Independent pooled t test | Equal-variance two-group Student t test | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.ttest_ind equal_var=True | 3 | not started | V02:function | — | — |
| TEST-007 | Welch t test | Unequal-variance two-group t with Satterthwaite df | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.ttest_ind equal_var=False | 3 | not started | brief | — | — |
| TEST-008 | Paired t test | One-sample t on matched differences | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.ttest_rel | 3 | not started | V02:function | — | — |
| TEST-009 | Single proportion test | Exact binomial or explicitly chosen asymptotic test | [M04](https://www.statsmodels.org/stable/api.html) | SciPy binomtest / statsmodels | 3 | not started | V02:function | — | — |
| TEST-010 | Independent proportion comparison | Two-proportion z test with declared null standard error | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.stats.proportion | 3 | not started | V02:function | — | — |
| TEST-011 | Independent correlation comparison | Fisher-z difference for independent groups | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | Needs custom implementation | 3 | not started | V02:function | — | — |
| TEST-012 | Variance ratio test | F test for independent normal samples | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy F + custom adapter | 3 | not started | brief | — | — |
| TEST-013 | Crosstab independence | Pearson chi-square with expected-count checks | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.chi2_contingency | 3 | not started | brief | — | — |
| TEST-014 | Fisher exact test | Exact two-by-two conditional test; alternatives explicit | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.fisher_exact | 3 | not started | brief | — | — |
| TEST-015 | McNemar paired binary test | Discordant-pair exact or continuity-corrected test | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.stats.contingency_tables | 3 | not started | V14:topic | — | — |
| TEST-016 | Association effect sizes | Phi and Cramer V; bias correction named | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.contingency.association + custom option | 3 | not started | brief | — | — |
| TEST-017 | Shapiro-Wilk normality | Normality test with sample limits and large-n warning | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.shapiro | 3 | not started | brief | — | — |
| TEST-018 | Anderson-Darling normality | Tail-sensitive normality statistic and documented calibration | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.anderson | 3 | not started | brief | — | — |
| TEST-019 | Lilliefors normality | KS statistic with estimated normal parameters and corrected calibration | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.stats.diagnostic.lilliefors | 3 | not started | brief | — | — |
| TEST-020 | Levene and Brown-Forsythe tests | Scale homogeneity centered at mean or median | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.levene | 3 | not started | brief | — | — |
| TEST-021 | Bartlett variance test | Variance homogeneity under normality | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.bartlett | 3 | not started | brief | — | — |
| TEST-022 | Mann-Whitney test | Independent-sample rank statistic; ties and exact/asymptotic policy | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.mannwhitneyu | 3 | not started | brief | — | — |
| TEST-023 | Wilcoxon signed ranks | Paired rank statistic; zeros, ties and method explicit | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.wilcoxon | 3 | not started | brief | — | — |
| TEST-024 | Kruskal-Wallis test | Independent-group rank test with tie correction | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.kruskal | 3 | not started | brief | — | — |
| TEST-025 | Friedman test | Repeated-block rank test with complete matched blocks | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.friedmanchisquare | 3 | not started | brief | — | — |
| TEST-026 | Spearman association | Rank correlation with ties and documented p-value policy | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.spearmanr | 3 | not started | V02:function | — | — |
| TEST-027 | Kendall association | Tau-b default; variant and ties explicit | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.kendalltau | 3 | not started | V02:function | — | — |
| TEST-028 | Paired sign test | Binomial count of positive nonzero paired differences | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy binomtest + custom tie policy | 3 | not started | V09:function | — | — |
| TEST-029 | Median comparison | Contingency test around pooled median; ties policy explicit | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.median_test | 3 | not started | V14:topic | — | — |
| TEST-030 | Two-sample distribution comparison | Kolmogorov-Smirnov statistic for two continuous samples | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.ks_2samp | 3 | not started | V14:topic | — | — |
| TEST-031 | Runs test | Wald-Wolfowitz ordering test with declared dichotomization | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.sandbox candidate; needs custom stable adapter | 3 | not started | V14:topic | — | — |
| TEST-032 | Cochran Q test | Matched binary outcomes over multiple conditions | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.stats.contingency_tables | 3 | not started | V14:topic | — | — |
| TEST-033 | Rank concordance | Kendall W with ties correction and explicit testing assumptions | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | Needs custom implementation | 3 | not started | V14:topic | — | — |
| TEST-034 | Ordinal gamma association | Concordant-minus-discordant pair ratio; tied pairs excluded | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | Needs custom implementation | 3 | not started | V14:topic | — | — |
| TEST-035 | Multiplicity adjustment | Bonferroni, Holm and Benjamini-Hochberg families | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.stats.multitest | 3 | not started | brief | — | — |
| TEST-036 | Bootstrap confidence intervals | Seeded resampling with percentile/basic/BCa convention | [M25](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) | scipy.stats.bootstrap | 3 | not started | brief | — | — |

### ANOVA and linear models

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| ANOVA-001 | One-way ANOVA | Independent-group F test and sums of squares | [M04](https://www.statsmodels.org/stable/api.html) | SciPy / statsmodels | 3 | not started | V02:function | — | — |
| ANOVA-002 | Factorial ANOVA | OLS design with interaction terms and declared SS type | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels OLS + anova_lm | 3 | not started | V11:function | — | — |
| ANOVA-003 | Repeated-measures ANOVA | Balanced within-subject design with assumption diagnostics | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels AnovaRM + custom diagnostics | 3 | not started | V14:topic | — | — |
| ANOVA-004 | Analysis of covariance | OLS with factor and covariate terms; interaction checks | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels OLS | 3 | not started | V14:topic | — | — |
| ANOVA-005 | Planned linear contrasts | Predeclared estimable contrasts with covariance-aware tests | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels contrast API | 3 | not started | V14:topic | — | — |
| ANOVA-006 | Tukey comparisons | Familywise pairwise mean comparisons with simultaneous intervals | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels pairwise_tukeyhsd | 3 | not started | brief | — | — |
| ANOVA-007 | Bonferroni comparisons | Pairwise tests with declared family and alpha correction | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels + custom family adapter | 3 | not started | brief | — | — |
| ANOVA-008 | Scheffe comparisons | All-contrast F-based simultaneous comparison bounds | [M04](https://www.statsmodels.org/stable/api.html) | Needs custom implementation | 3 | not started | brief | — | — |
| ANOVA-009 | Estimated marginal means | Reference-grid averages and explicit weighting convention | [M04](https://www.statsmodels.org/stable/api.html) | Needs custom adapter over model covariance | 3 | not started | brief | — | — |
| ANOVA-010 | ANOVA assumptions and effect sizes | Residual checks, eta squared/omega squared and declared SS basis | [M04](https://www.statsmodels.org/stable/api.html) | Needs custom adapter | 3 | not started | brief | — | — |

### Regression and diagnostics

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| REG-001 | Simple linear regression | Intercept/slope ordinary least squares | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels OLS | 3 | not started | brief | — | — |
| REG-002 | Multiple linear regression | Full-rank OLS design with explicit categorical contrasts | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels OLS | 3 | not started | V01:module | — | — |
| REG-003 | Weighted least squares | Inverse-variance weights distinct from frequency weights | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels WLS | 3 | not started | V14:topic | — | — |
| REG-004 | Model coefficient intervals and tests | Model covariance, df and declared confidence level | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels results API | 3 | not started | brief | — | — |
| REG-005 | Predictions and intervals | Mean-response interval separate from individual prediction interval | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels get_prediction | 3 | not started | brief | — | — |
| REG-006 | Residual diagnostics | Residual/fitted plots, scale and normal probability checks | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels + chart adapters | 3 | not started | brief | — | — |
| REG-007 | Influence diagnostics | Leverage, studentized residuals and Cook distance | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels OLSInfluence | 3 | not started | brief | — | — |
| REG-008 | Collinearity diagnostics | VIF and condition number with scaling noted | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels + NumPy | 3 | not started | brief | — | — |
| REG-009 | Heteroskedasticity diagnostics | Breusch-Pagan/White with assumptions recorded | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.stats.diagnostic | 3 | not started | brief | — | — |
| REG-010 | Robust covariance | Explicit HC variants without changing coefficients | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels robust covariance | 3 | not started | brief | — | — |
| REG-011 | Partial correlations | Residualized association with conditioning variables declared | [M04](https://www.statsmodels.org/stable/api.html) | OLS + custom adapter | 3 | not started | V12:function | — | — |
| REG-012 | Stepwise regression | Declared entry/removal rule; selection bias warning | [M04](https://www.statsmodels.org/stable/api.html) | Needs custom implementation | 3 | not started | V14:topic | — | — |
| REG-013 | Best-subset regression | Bounded subset enumeration and explicit objective | [M04](https://www.statsmodels.org/stable/api.html) | Needs custom implementation | 3 | not started | V14:topic | — | — |
| REG-014 | Binary logistic regression | Bernoulli response and logit link; separation diagnosis | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels Logit / GLM | 3 | not started | brief | — | — |
| REG-015 | Poisson regression | Count response and log link with overdispersion checks | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels GLM | 3 | not started | brief | — | — |
| REG-016 | Generalized linear models | Validated family/link combinations and convergence status | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels GLM | 3 | not started | V01:module | — | — |

### Advanced linear and nonlinear models

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| ADV-001 | Probit regression | Bernoulli likelihood with normal CDF link | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels Probit | 4 | not started | V01:module | — | — |
| ADV-002 | Multinomial response regression | Unordered multinomial logistic likelihood | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels MNLogit | 4 | not started | V01:module | — | — |
| ADV-003 | Ordered response regression | Threshold model with logit/probit link | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels OrderedModel | 4 | not started | V01:module | — | — |
| ADV-004 | Negative-binomial regression | Overdispersed count likelihood with parameterization explicit | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels NegativeBinomial / GLM | 4 | not started | V01:module | — | — |
| ADV-005 | Generalized estimating equations | Marginal correlated-response models with working correlation | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels GEE | 4 | not started | brief | — | — |
| ADV-006 | Mixed linear models | Random intercepts/slopes, ML or REML and convergence checks | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels MixedLM | 4 | not started | V01:module | — | — |
| ADV-007 | Variance components | Random-effect covariance estimates with boundary diagnostics | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels MixedLM + custom reporting | 4 | not started | V01:module | — | — |
| ADV-008 | Nonlinear least squares | User formula with starting values, bounds and convergence | [M13](https://docs.scipy.org/doc/scipy/reference/optimize.html) | scipy.optimize.least_squares | 4 | not started | V01:module | — | — |
| ADV-009 | Fixed nonlinear model catalog | Original named exponential/logistic growth models | [M13](https://docs.scipy.org/doc/scipy/reference/optimize.html) | SciPy optimization + original model definitions | 4 | not started | V01:module | — | — |
| ADV-010 | Generalized additive models | Penalized smooth effects with basis and smoothing choices | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels GLMGam | 4 | not started | V01:function | — | — |
| ADV-011 | Log-linear count tables | Poisson log-linear model over contingency cells | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels GLM + custom design | 4 | not started | V01:module | — | — |
| ADV-012 | Partial least squares regression | PLS components with scaling and validation protocol | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.cross_decomposition.PLSRegression | 4 | not started | V01:module | — | — |
| ADV-013 | Ridge regression | L2-penalized predictive linear model | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.linear_model.Ridge | 4 | not started | brief | — | — |
| ADV-014 | Lasso regression | L1-penalized predictor selection with scaled predictors | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.linear_model.Lasso | 4 | not started | V01:function | — | — |
| ADV-015 | Elastic-net regression | Combined L1/L2 predictive regularization | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.linear_model.ElasticNet | 4 | not started | brief | — | — |
| ADV-016 | Response-surface models | Polynomial effects, interactions and original prediction profiler | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels + custom design | 4 | not started | V10:function | — | — |

### Multivariate exploration

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| MULTI-001 | Principal components | SVD decomposition with centering/scaling choices and scores | [M06](https://scikit-learn.org/stable/unsupervised_learning.html) | sklearn.decomposition.PCA | 4 | not started | V01:module | — | — |
| MULTI-002 | Exploratory factor analysis | Common-factor ML or principal-axis extraction, factor count explicit | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.multivariate.factor | 4 | not started | V01:module | — | — |
| MULTI-003 | Factor rotation | Named orthogonal/oblique rotations with pattern/structure distinction | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels factor_rotation | 4 | not started | V01:module | — | — |
| MULTI-004 | K-means clustering | Within-cluster squared-distance objective; seeded initialization | [M06](https://scikit-learn.org/stable/unsupervised_learning.html) | sklearn.cluster.KMeans | 4 | not started | V03:function | — | — |
| MULTI-005 | Hierarchical clustering | Named linkage and compatible distance metric | [M16](https://docs.scipy.org/doc/scipy/reference/cluster.hierarchy.html) | scipy.cluster.hierarchy | 4 | not started | V01:module | — | — |
| MULTI-006 | Dendrogram | Tree geometry with merge heights and stable labels | [M16](https://docs.scipy.org/doc/scipy/reference/cluster.hierarchy.html) | SciPy linkage + Core Graphics | 4 | not started | brief | — | — |
| MULTI-007 | Linear discriminant classifier | Class-conditional shared-covariance model; priors explicit | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.discriminant_analysis.LinearDiscriminantAnalysis | 4 | not started | V01:module | — | — |
| MULTI-008 | Quadratic discriminant classifier | Class-specific covariance model with conditioning checks | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.discriminant_analysis.QuadraticDiscriminantAnalysis | 4 | not started | V01:module | — | — |
| MULTI-009 | MANOVA | Multivariate linear model and named omnibus statistics | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels MANOVA | 4 | not started | V11:function | — | — |
| MULTI-010 | MANCOVA | Multivariate model with factors and covariates | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels MANOVA + custom design | 4 | not started | V14:topic | — | — |
| MULTI-011 | Correspondence analysis | Chi-square standardized contingency residual SVD | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation; NumPy/SciPy primitives | 4 | not started | V01:module | — | — |
| MULTI-012 | Canonical correlation | Correlation-maximizing linear combinations of two variable sets | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.cross_decomposition.CCA + custom inference | 4 | not started | V01:module | — | — |
| MULTI-013 | Multidimensional scaling | Metric/nonmetric embedding with stress and initialization explicit | [M06](https://scikit-learn.org/stable/unsupervised_learning.html) | sklearn.manifold.MDS | 4 | not started | V01:module | — | — |
| MULTI-014 | Independent components | Independent-source decomposition with seeded FastICA | [M06](https://scikit-learn.org/stable/unsupervised_learning.html) | sklearn.decomposition.FastICA | 4 | not started | V13:discovery | — | — |
| MULTI-015 | Gaussian mixture clustering | EM likelihood fit with covariance form and seed declared | [M06](https://scikit-learn.org/stable/unsupervised_learning.html) | sklearn.mixture.GaussianMixture | 4 | not started | V03:function | — | — |
| MULTI-016 | Reliability coefficient alpha | Classical internal consistency with raw/standardized variants | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 4 | not started | V01:module | — | — |
| MULTI-017 | Item diagnostics | Item-total relationships and alpha after item removal | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 4 | not started | V01:module | — | — |
| MULTI-018 | Intraclass correlation | Named variance-component ICC with design-specific intervals | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 4 | not started | V14:topic | — | — |
| MULTI-019 | Cohen agreement coefficient | Observed-vs-chance categorical agreement | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.stats.inter_rater | 4 | not started | V07:module | — | — |

### Time series and forecasting

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| TIME-001 | ARIMA | Differenced autoregressive moving-average model with residual diagnostics | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels.tsa.arima.model.ARIMA | 4 | not started | V14:topic | — | — |
| TIME-002 | Seasonal ARIMA | Seasonal differencing and AR/MA terms with declared period | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels SARIMAX | 4 | not started | V06:module | — | — |
| TIME-003 | Exponential smoothing | Simple, Holt and seasonal Holt-Winters with selected initialization | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels Holt-Winters / ETS | 4 | not started | V06:function | — | — |
| TIME-004 | Classical decomposition | Additive/multiplicative trend, seasonal and residual components | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels seasonal_decompose | 4 | not started | V14:topic | — | — |
| TIME-005 | STL decomposition | LOESS-based seasonal/trend decomposition with period and smoothing choices | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels STL | 4 | not started | brief | — | — |
| TIME-006 | Autocorrelation | Lag correlations with convention and interval method stated | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels acf | 4 | not started | V06:function | — | — |
| TIME-007 | Partial autocorrelation | Declared estimator for conditional lag correlation | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels pacf | 4 | not started | V14:topic | — | — |
| TIME-008 | Cross-correlation | Lagged association with direction and normalization explicit | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels ccf | 4 | not started | V14:topic | — | — |
| TIME-009 | Moving-average smoothing | Declared window, boundary treatment and missing policy | [M08](https://pandas.pydata.org/docs/reference/index.html) | pandas rolling | 4 | not started | V06:module | — | — |
| TIME-010 | Differencing and integration | Ordered discrete differences and cumulative reconstruction | [M08](https://pandas.pydata.org/docs/reference/index.html) | NumPy / pandas | 4 | not started | V14:topic | — | — |
| TIME-011 | Spectral analysis | Periodogram/Welch power spectrum with frequency units | [M15](https://docs.scipy.org/doc/scipy/reference/signal.html) | scipy.signal | 4 | not started | V14:topic | — | — |
| TIME-012 | Intervention forecasting | Predeclared intervention regressors in ARIMA error model | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels SARIMAX + custom design | 4 | not started | V14:topic | — | — |
| TIME-013 | Distributed-lag regression | Lagged regressors with declared lag window | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels + custom design | 4 | not started | V14:topic | — | — |
| TIME-014 | Forecast validation | Rolling-origin evaluation, leakage checks and interval coverage | [M04](https://www.statsmodels.org/stable/api.html) | Needs custom implementation | 4 | not started | brief | — | — |

### Survival and failure time

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| SURV-001 | Kaplan-Meier estimator | Right-censored product-limit survival with event coding explicit | [M07](https://lifelines.readthedocs.io/en/latest/) | lifelines KaplanMeierFitter | 4 | not started | V14:topic | — | — |
| SURV-002 | Life table estimator | Actuarial interval estimator with within-interval assumption | [M07](https://lifelines.readthedocs.io/en/latest/) | Needs custom implementation | 4 | not started | V14:topic | — | — |
| SURV-003 | Log-rank comparison | Observed-vs-expected event comparison over risk sets | [M07](https://lifelines.readthedocs.io/en/latest/) | lifelines logrank_test | 4 | not started | V14:topic | — | — |
| SURV-004 | Cox proportional hazards | Partial likelihood with tie method and censoring convention | [M07](https://lifelines.readthedocs.io/en/latest/) | lifelines CoxPHFitter | 4 | not started | V01:function | — | — |
| SURV-005 | Cox time-varying covariates | Start-stop intervals and time-varying partial likelihood | [M07](https://lifelines.readthedocs.io/en/latest/) | lifelines CoxTimeVaryingFitter | 4 | not started | V14:topic | — | — |
| SURV-006 | Proportional-hazards diagnostics | Schoenfeld residual-based diagnostics | [M07](https://lifelines.readthedocs.io/en/latest/) | lifelines check_assumptions | 4 | not started | brief | — | — |
| SURV-007 | Parametric survival | Weibull, exponential and lognormal models; AFT/PH distinction | [M07](https://lifelines.readthedocs.io/en/latest/) | lifelines fitters | 4 | not started | V07:module | — | — |
| SURV-008 | Survival hazard and reliability curves | Declared survival, cumulative hazard and hazard estimates | [M07](https://lifelines.readthedocs.io/en/latest/) | lifelines + chart adapters | 4 | not started | V07:module | — | — |

### Distribution fitting and simulation

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| FIT-001 | Continuous distribution fitting | Maximum likelihood with support/parameter constraints | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.fit / distribution.fit | 4 | not started | V01:module | — | — |
| FIT-002 | Discrete distribution fitting | Discrete likelihood with integer support and bounds | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.fit + custom discrete parameter adapters | 4 | not started | V01:module | — | — |
| FIT-003 | Chi-square goodness of fit | Expected-bin counts, fitted-parameter df and sparse-bin policy | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | scipy.stats.chisquare + custom calibration | 4 | not started | brief | — | — |
| FIT-004 | KS goodness of fit | Specified-distribution KS; do not use uncorrected fitted-parameter p-values | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy kstest; parametric bootstrap for fitted cases | 4 | not started | brief | — | — |
| FIT-005 | Anderson-Darling goodness of fit | Specified-family or fitted-parameter calibrated statistic | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy anderson / goodness_of_fit | 4 | not started | brief | — | — |
| FIT-006 | Q-Q plot | Declared plotting positions and selected reference quantiles | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy probplot + Core Graphics | 4 | not started | V05:function | — | — |
| FIT-007 | P-P plot | Empirical probabilities against reference CDF with plotting positions | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | Needs custom implementation | 4 | not started | V05:function | — | — |
| FIT-008 | Seeded random simulation | Named random-generator algorithm and saved seed | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | NumPy Generator | 4 | not started | V01:module | — | — |
| FIT-009 | Correlated simulation | Declared covariance or documented copula construction | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | NumPy multivariate_normal; custom general copula adapter | 4 | not started | V14:topic | — | — |
| FIT-010 | Monte Carlo uncertainty | Simulation precision separate from statistical uncertainty | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | Needs custom implementation | 4 | not started | brief | — | — |

### Power and sample size

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| POWER-001 | One-sample and paired t power | Noncentral t power and minimum integer sample size | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels TTestPower | 4 | not started | V14:topic | — | — |
| POWER-002 | Independent t power | Noncentral t with declared allocation and equal-variance assumption | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels TTestIndPower | 4 | not started | V14:topic | — | — |
| POWER-003 | ANOVA power | Noncentral F for supported fixed-effect design | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels FTestAnovaPower; custom complex designs | 4 | not started | V14:topic | — | — |
| POWER-004 | Regression power | Noncentral F under explicit full/reduced model degrees of freedom | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels FTestPower + custom df adapter | 4 | not started | V14:topic | — | — |
| POWER-005 | Proportion power | Normal or exact binomial planning with assumptions explicit | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels NormalIndPower; custom exact solver | 4 | not started | V14:topic | — | — |
| POWER-006 | Chi-square power | Chi-square effect size and noncentral reference distribution | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels GofChisquarePower | 4 | not started | V14:topic | — | — |
| POWER-007 | Correlation power | Fisher-z approximation labeled; exact variant requires custom implementation | [M04](https://www.statsmodels.org/stable/api.html) | Needs custom implementation | 4 | not started | V14:topic | — | — |
| POWER-008 | Power curves | Solve effect size, power or n with bounds and integer recheck | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels power API + custom plotting | 4 | not started | V14:topic | — | — |

### Industrial statistics and Six Sigma

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| QC-001 | Subgroup mean and range charts | X-bar/R limits from rational subgroup estimates | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | brief | — | — |
| QC-002 | Subgroup mean and SD charts | X-bar/S limits with subgroup-size correction | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V14:topic | — | — |
| QC-003 | Individuals and moving-range charts | I-MR estimates from consecutive differences | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | brief | — | — |
| QC-004 | Fraction nonconforming chart | p limits using subgroup-specific binomial variance | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V08:function | — | — |
| QC-005 | Count nonconforming chart | np chart for fixed subgroup sizes | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V08:function | — | — |
| QC-006 | Defect count chart | c chart for defects with constant exposure | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V08:function | — | — |
| QC-007 | Defect rate chart | u chart with varying exposure | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V08:function | — | — |
| QC-008 | Cumulative-sum chart | CUSUM reference value and decision interval declared | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | brief | — | — |
| QC-009 | Exponentially weighted chart | EWMA weight, startup variance and limits explicit | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | brief | — | — |
| QC-010 | Control-rule checks | Named run/zone rules and baseline-vs-monitoring distinction | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | brief | — | — |
| QC-011 | Within-process capability | Cp/Cpk from declared within-subgroup sigma and limits | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V07:module | — | — |
| QC-012 | Overall-process performance | Pp/Ppk from overall SD; distinguish from capability | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V07:module | — | — |
| QC-013 | Non-normal capability | Distribution-based percentile convention with fit diagnostics | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V07:module | — | — |
| QC-014 | Binomial/Poisson capability | Attribute rate and declared confidence limits | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V07:function | — | — |
| QC-015 | Tolerance intervals | Normal or distribution-free population-content intervals | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V07:function | — | — |
| QC-016 | Crossed gauge repeatability and reproducibility | Variance-component crossed part/operator design | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels mixed models + custom estimator | 5 | not started | V07:function | — | — |
| QC-017 | Nested gauge studies | Nested part/operator variance components | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels mixed models + custom estimator | 5 | not started | V07:module | — | — |
| QC-018 | Gauge bias and linearity | Reference-value differences, slope and uncertainty | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels OLS + custom report | 5 | not started | V07:function | — | — |
| QC-019 | Attribute agreement study | Rater/reference agreement with chance correction and intervals | [M04](https://www.statsmodels.org/stable/api.html) | statsmodels + custom study adapter | 5 | not started | V07:function | — | — |
| QC-020 | Acceptance sampling | Exact binomial/hypergeometric operating-characteristic curves | [M02](https://docs.scipy.org/doc/scipy/reference/stats.html) | SciPy + custom plan search | 5 | not started | V07:module | — | — |
| QC-021 | Weibull failure analysis | Censoring-aware failure-time fit and reliability curves | [M07](https://lifelines.readthedocs.io/en/latest/) | lifelines WeibullFitter | 5 | not started | V07:function | — | — |
| QC-022 | Hotelling process chart | T squared from declared baseline covariance and calibration | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V01:module | — | — |
| QC-023 | PCA/PLS process monitoring | Score T squared and residual Q with phase-specific calibration | [M06](https://scikit-learn.org/stable/unsupervised_learning.html) | sklearn + custom limits | 5 | not started | V01:module | — | — |
| QC-024 | Pareto defect chart | Sorted counts and cumulative proportions | [M17](https://developer.apple.com/documentation/charts) | Native chart renderer | 5 | not started | V14:topic | — | — |
| QC-025 | Cause-and-effect diagram | Original editable cause categories and causal hypotheses | [M17](https://developer.apple.com/documentation/charts) | Needs custom implementation | 5 | not started | V12:function | — | — |
| QC-026 | Six Sigma study workflow | Original define/measure/analyze/improve/control report structure | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V01:module | — | — |

### Experimental design and optimization

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| DOE-001 | Full factorial designs | Cartesian factor-level design with randomized run order | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | brief | — | — |
| DOE-002 | Fractional factorial designs | Generator-defined fractions with alias structure and resolution | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V11:function | — | — |
| DOE-003 | Central-composite designs | Factorial, axial and center points with alpha choice | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V10:function | — | — |
| DOE-004 | Box-Behnken designs | Three-level incomplete factorial surface design | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V11:function | — | — |
| DOE-005 | Mixture designs | Simplex constraints and Scheffe mixture polynomial | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V14:topic | — | — |
| DOE-006 | Blocking and randomization | Declared blocks and reproducible randomized run order | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | brief | — | — |
| DOE-007 | Design model analysis | Estimable effects, lack-of-fit and pure-error separation | [M01](https://www.itl.nist.gov/div898/handbook/) | statsmodels + custom design adapter | 5 | not started | brief | — | — |
| DOE-008 | Response optimization | Bounded prediction objective with declared desirability functions | [M13](https://docs.scipy.org/doc/scipy/reference/optimize.html) | SciPy optimize + custom desirability | 5 | not started | V13:discovery | — | — |

### Machine learning and neural networks

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| ML-001 | Classification trees | CART impurity splits and pruning with seed recorded | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.tree.DecisionTreeClassifier | 5 | not started | V01:function | — | — |
| ML-002 | Regression trees | CART squared-error splits and pruning | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.tree.DecisionTreeRegressor | 5 | not started | V01:function | — | — |
| ML-003 | Random forests | Seeded bagged decision-tree classification/regression | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.ensemble.RandomForest* | 5 | not started | V03:function | — | — |
| ML-004 | Gradient boosting | Sequential loss-gradient trees; loss and stopping explicit | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.ensemble.GradientBoosting* / HistGradientBoosting* | 5 | not started | V03:function | — | — |
| ML-005 | Support-vector machines | Support-vector classification/regression with kernel and scaling | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.svm | 5 | not started | V01:function | — | — |
| ML-006 | Nearest neighbors | Distance-based prediction with metric, k and tie policy | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.neighbors | 5 | not started | V01:function | — | — |
| ML-007 | Feedforward neural networks | MLP classification/regression with preprocessing and convergence | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.neural_network.MLP* | 5 | not started | V01:module | — | — |
| ML-008 | Cross-validation | Stratified/grouped/time-aware splits appropriate to data | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.model_selection | 5 | not started | brief | — | — |
| ML-009 | Hyperparameter search | Nested validation with declared objective and random seed | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn GridSearchCV / RandomizedSearchCV | 5 | not started | brief | — | — |
| ML-010 | Confusion matrices and classification metrics | Declared positive class, averaging and threshold | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.metrics | 5 | not started | brief | — | — |
| ML-011 | ROC curves and AUC | Score-ranked sensitivity and false-positive rate | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.metrics | 5 | not started | brief | — | — |
| ML-012 | Precision-recall curves and average precision | Score-ranked precision/recall with declared class | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.metrics | 5 | not started | brief | — | — |
| ML-013 | Regression validation metrics | MAE/RMSE/R squared with baseline and weighting explicit | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.metrics | 5 | not started | brief | — | — |
| ML-014 | Permutation feature importance | Held-out metric change under seeded permutation | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.inspection.permutation_importance | 5 | not started | brief | — | — |
| ML-015 | Model-based importance | Impurity/coefficient importance with bias warnings | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn model attributes + original notes | 5 | not started | brief | — | — |
| ML-016 | Predictor screening | Univariate score plus leakage-safe validation | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.feature_selection | 5 | not started | V03:function | — | — |
| ML-017 | Weight-of-evidence encoding | Training-only smoothed event odds by bins with leakage guard | [M05](https://scikit-learn.org/stable/supervised_learning.html) | Needs custom implementation | 5 | not started | V03:function | — | — |
| ML-018 | Optimal binning | Constrained supervised bin grouping with saved cutpoints | [M13](https://docs.scipy.org/doc/scipy/reference/optimize.html) | Needs custom implementation | 5 | not started | V13:discovery | — | — |
| ML-019 | Text feature extraction | Bag-of-words and TF-IDF from user-authorized local text | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn.feature_extraction.text | 5 | not started | V03:module | — | — |
| ML-020 | Association rules | Frequent itemsets and support/confidence/lift with explicit bases | [M01](https://www.itl.nist.gov/div898/handbook/) | Needs custom implementation | 5 | not started | V03:module | — | — |
| ML-021 | Model scoring | Versioned schema-checked predictions in original engine | [M05](https://scikit-learn.org/stable/supervised_learning.html) | sklearn + custom model artifact validation | 5 | not started | V03:module | — | — |

### Advanced charts

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| VIZ-001 | Three-dimensional scatter | Perspective projection with depth cue and accessible 2D/table alternative | [M17](https://developer.apple.com/documentation/charts) | Metal / Core Graphics custom renderer | 4 | not started | V12:function | — | — |
| VIZ-002 | Contour plot | Declared interpolated/analytic surface and contour levels | [M17](https://developer.apple.com/documentation/charts) | SciPy primitives + custom renderer | 4 | not started | brief | — | — |
| VIZ-003 | Surface plot | Mesh from declared function or grid with original camera controls | [M17](https://developer.apple.com/documentation/charts) | Metal custom renderer | 4 | not started | V10:module | — | — |
| VIZ-004 | Scatter matrix | Pairwise plots and aligned variable labels with bounded sampling | [M17](https://developer.apple.com/documentation/charts) | Native composite charts | 4 | not started | V14:topic | — | — |
| VIZ-005 | Parallel coordinates | Per-axis scaling, ordering and accessible table equivalent | [M17](https://developer.apple.com/documentation/charts) | Core Graphics custom renderer | 4 | not started | V05:function | — | — |
| VIZ-006 | Heatmap | Numerical cell colors with labeled legend and missing state | [M17](https://developer.apple.com/documentation/charts) | Swift Charts / Core Graphics | 4 | not started | brief | — | — |

### Results, reproducibility and extensibility

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| WORK-001 | Native document windows and tabs | Document ownership, coordinated edits and native tab behavior | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | NSDocument / NSWindow | 0 | in progress | brief | — | — |
| WORK-002 | Project sidebar and inspector | Dataset/analysis/result/workflow navigation and nonmodal forms | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | SwiftUI / AppKit | 0 | in progress | brief | — | — |
| WORK-003 | Searchable analysis launcher | Stable command registry shared with Statistics menu | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom command registry | 0 | not started | brief | — | — |
| WORK-004 | Type-aware variable pickers | Eligibility by scale/role with accessible keyboard alternatives | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom declarative form model | 0 | not started | brief | — | — |
| WORK-005 | Declarative analysis specifications | Versioned parameters, revision hash and statistical conventions | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom JSON schema | 0 | not started | brief | — | — |
| WORK-006 | Results workbook blocks | Ordered tables/charts/notes with collapse and annotations | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom block document model | 0 | not started | brief | — | — |
| WORK-007 | English and Czech localization | String Catalog keys, locale-aware display and numeric input | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Xcode String Catalogs + Foundation | 0 | in progress | brief | — | — |
| WORK-008 | Accessibility and appearance | VoiceOver, keyboard focus, contrast, text scaling and Dark Mode | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Native controls + accessibility adapters | 0 | in progress | brief | — | — |

### Results exports and learning

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| REPORT-001 | Learning mode across descriptive outputs | Original formulas, inputs and recorded working for every Phase 1 statistic | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom explanation registry | 1 | not started | brief | — | — |
| REPORT-002 | PDF workbook export | Paginated original table/chart/note layouts | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Core Graphics PDF / AppKit print renderer | 1 | not started | brief | — | — |
| REPORT-003 | HTML workbook export | Escaped static report with accessible tables and SVG | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom exporter | 1 | not started | brief | — | — |
| REPORT-004 | Markdown workbook export | Original tables, notes and linked chart assets | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom exporter | 1 | not started | brief | — | — |
| REPORT-005 | DOCX workbook export | Original report structure, captions and table styles | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | python-docx candidate + custom adapter | 1 | not started | brief | — | — |
| REPORT-006 | LaTeX table export | Escaped tabular content with declared rounding | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom exporter | 1 | not started | brief | — | — |
| REPORT-007 | Python reproducibility export | Version-pinned engine/library calls with saved analysis spec | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom code generator | 1 | not started | brief | — | — |
| REPORT-008 | R reproducibility export | Original equivalent formulas; R remains external and unbundled | [M18](https://developer.apple.com/documentation/appkit/nsdocument) | Needs custom code generator and cross-checks | 1 | not started | brief | — | — |

### Workflow and plugins

| ID | Function | Statistical method or contract | Public method reference | Candidate library | Phase | Status | Origin evidence | Test | Reference fixture |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| FLOW-001 | Visual workflow editor | Typed acyclic import/transform/analyze/report graph | [M08](https://pandas.pydata.org/docs/reference/index.html) | Needs custom implementation | 5 | not started | brief | — | — |
| FLOW-002 | Workflow reruns | Revision-keyed topological execution and cache invalidation | [M08](https://pandas.pydata.org/docs/reference/index.html) | Needs custom scheduler | 5 | not started | brief | — | — |
| FLOW-003 | Python plugin manifest | Version, method IDs, license, dependencies and trust status | [M08](https://pandas.pydata.org/docs/reference/index.html) | Needs custom schema | 5 | not started | brief | — | — |
| FLOW-004 | Declarative plugin forms | Restricted UI schema with validation and localization keys | [M08](https://pandas.pydata.org/docs/reference/index.html) | Needs custom implementation | 5 | not started | brief | — | — |
| FLOW-005 | Plugin lifecycle and isolation | Explicit user enablement and separate supervised process | [M08](https://pandas.pydata.org/docs/reference/index.html) | Needs custom implementation | 5 | not started | brief | — | — |
| FLOW-006 | Batch analyses by groups | Repeated original specs with grouped dataset views | [M08](https://pandas.pydata.org/docs/reference/index.html) | Needs custom implementation | 5 | not started | V13:discovery | — | — |

## Not planned / unknown

These entries are not implementation commitments. Candidate phases are research placeholders, not approved scope.

| ID | Family or gap | Candidate phase | Disposition | Reason |
| --- | --- | --- | --- | --- |
| GAP-01 | Proprietary file formats and binary compatibility | No phase | Not planned | STA and internal workbook formats are expressly excluded; open interchange only. |
| GAP-02 | Exact vendor menu and parameter parity | Unassigned | Unknown | Public sources do not establish every license tier, patch, method option or numerical default. No completeness claim. |
| GAP-03 | Structural equation and path models | 4 candidate | Unknown | V01 confirms module; estimator coverage and permissive implementation not established. Do not silently substitute regression. |
| GAP-04 | Structural-equation power and fit intervals | 4 candidate | Unknown | V14 topic evidence only; finite-sample reference and implementation remain unselected. |
| GAP-05 | Exact correlation-distribution calculators | 2/4 candidate | Unknown | V14 mentions correlation/R-squared probability tools; parameterization and calibrated coverage need separate research. |
| GAP-06 | Multivariate adaptive regression splines | 5 candidate | Unknown | V01 confirms module; no approved engine dependency or original implementation plan. Do not bundle GPL implementations. |
| GAP-07 | CHAID tree variants | 5 candidate | Unknown | V01 confirms family; adjusted split tests, merging rules and permissive implementation require research. |
| GAP-08 | Interactive tree growth and pruning | 5 candidate | Unknown | V01 confirms feature family; exact editor scope and reproducibility semantics unresolved. |
| GAP-09 | Radial-basis neural networks and automatic network ensembles | 5 candidate | Unknown | Neural module alone does not establish each network type; scikit-learn MLP does not provide all architectures. |
| GAP-10 | Deep-learning architecture catalog | 5 candidate | Unknown | V01 confirms label; scope, runtime size and approved permissive artifacts remain unknown. |
| GAP-11 | Sequence mining and link analysis | 5 candidate | Unknown | V01 confirms families; algorithms, visualization and license-vetted implementation not selected. |
| GAP-12 | Web crawling | 5 candidate | Not planned | V14 discovery only; external collection is outside the requested local statistics application scope. |
| GAP-13 | X-11 seasonal adjustment | 4 candidate | Unknown | V14 topic evidence; no approved bundled implementation. External tools require artifact and license review. |
| GAP-14 | NIPALS with missing data | 4 candidate | Unknown | V14 and older V13 discovery; ordinary PCA/PLS mapping does not guarantee missing-data NIPALS. |
| GAP-15 | Special SS conventions and general repeated mixed designs | 3/4 candidate | Unknown | Types beyond planned I/II/III, sphericity corrections, unbalanced repeated designs and random-design tests require validated adapters. |
| GAP-16 | Best-subset and stepwise discriminant/probit/ANCOVA variants | 4 candidate | Unknown | Module and topic evidence is insufficient to assign a tested general selection implementation. |
| GAP-17 | Special capability and time-dependent process models | 5 candidate | Unknown | V07 names broader families; true-position, time-dependent and other nonstandard estimators need independent references. |
| GAP-18 | Precision studies and complex gauge designs | 5 candidate | Unknown | V01 confirms precision family; exact study designs and finite-sample intervals remain unaudited. |
| GAP-19 | Taguchi, optimal and general custom DOE | 5 candidate | Unknown | Requested DOE scope is enumerated above; additional design families need function-specific public confirmation and reference fixtures. |
| GAP-20 | Predictive QC and automatic process optimizers | 5 candidate | Unknown | Discovery exists in 14.x sources; baseline rules, leakage controls and exact method scope remain unresolved. |
| GAP-21 | Enterprise administration, document server and product traceability | No phase | Not planned | Older V13 confirms enterprise families; local research documents do not require enterprise compatibility. |
| GAP-22 | Vendor scripting, external proprietary scoring and application embedding | No phase | Not planned | Original Python plugins and original exporters replace vendor automation; no compatible proprietary scripting runtime. |
| GAP-23 | Dynamic time warping | 4/5 candidate | Unknown | V15 lists it but gives no 14.0 version evidence; method and permissive dependency need confirmation. |
| GAP-24 | Icon, bag, image, ternary and specialized 3D chart families | 1/4/5 candidate | Unknown | V05/V14 discovery includes graph families beyond scoped charts. Exact variants and accessible original implementations are unaudited. |
| GAP-25 | Legacy calculator distributions beyond this inventory | 2/4 candidate | Unknown | Additional named distributions appear in V14; create individually sourced rows before adding coverage. No guessed variants. |
| GAP-26 | PMML import and export | 5 candidate | Unknown | V01 mentions scoring. Executable model safety, supported model subset and permissive dependency remain unselected. |
| GAP-27 | Simulation optimization and general nonnormal correlated generators | 4/5 candidate | Unknown | Simulation family confirmed by V01; copula/marginal combinations and numerical references need scoped research. |
| GAP-28 | Nested/general plugin distribution service | 5 candidate | Not planned | Local plugin manifests are planned; marketplace, remote installation and automatic untrusted execution are excluded. |

## Maintenance and future CI gate

Use `docs/feature_catalog.json` as the stable-ID source of truth. Generate this Markdown table and README counters from it; never independently edit counts. Every status starts at `not started`. The gate is implemented in scripts/feature_matrix.py for the executed Python acceptance tests. Full native UI gates remain pending.

The current `scripts/feature_matrix.py` checks executed acceptance tests, freshness and tracked fixture usage. The following rules govern it and future native-test adapters:

1. Unique stable ID, valid phase/status, public method source, explicit evidence level and candidate library for every planned row.
2. `implemented` requires a registered runnable acceptance test for that ID, not merely an existing file or a test containing the ID as a string. CI must execute it successfully.
3. `verified against reference values` requires the same acceptance test plus a tracked fixture containing independent expected values, provenance, convention, tolerance and regeneration evidence. CI must execute the fixture comparison successfully.
4. Numerical tests must exercise public engine/CLI or RPC adapters as appropriate. Product/UI rows require end-to-end acceptance fixtures; do not fabricate numeric references for infrastructure.
5. No pending/skipped/xfailed acceptance test promotes status. No expected-value generation with the same function under test qualifies as independent verification.
6. Reject stale rendered matrix/README, missing fixture targets, fabricated implementation counters and undeclared phase promotion.
7. Verified is a subset of implemented. Coverage equals implemented plus verified rows, counted once; verified count is reported separately. Unknown rows never increase coverage.

Before a feature starts, refine its reference to a precise public chapter/equation or API page and decide its acceptance subcases. The current broad chapter links are audit-level references, not sufficient fixture provenance. Every listed operation must pass before the parent row advances.

## Public-source register

Research uses feature names and original paraphrases only. It does not reproduce documentation, figures, examples or source data. Sources were reviewed or discovered on 2026-10-14; see SOURCES.md for access and verification limits.

- **V01** — [Public 14.0 academic feature inventory](https://support.tibco.com/external/article/KB0070828/statistica-academic-bundle-feature-detai.html). Vendor module names; not evidence for every option within a module.
- **V02** — [Public 14.0.1 basic analysis overview](https://docs.tibco.com/pub/stat/14.0.1/doc/html/UsersGuide/user-guide/basic-statistics-overview.htm). Frequency, correlation, grouped summaries, t-tests, crosstabs and response tables.
- **V03** — [Public 14.0 data-mining overview](https://docs.tibco.com/pub/stat/14.0.0/doc/html/UsersGuide/GUID-050E6A8F-4660-4B6A-9265-56527282E606.html). Trees, ensembles, text, predictor screening, response coding and deployment.
- **V04** — [Public 14.3 multivariate module inventory](https://docs.tibco.com/pub/stat/14.3.0/doc/html/user-guide/user-guide/multivariate-exploratory-techniques-a.htm). Supplemental 14.x module evidence; does not establish 14.0 availability.
- **V05** — [Public 14.3 two-dimensional graph inventory](https://docs.tibco.com/pub/stat/14.3.0/doc/html/user-guide/6-working-with-graphs/2d-graphs.htm). Supplemental 14.x graph names, not copied artwork or interface design.
- **V06** — [Public 14.3 time-series overview](https://docs.tibco.com/pub/stat/14.3.0/doc/html/user-guide/_shared/time-series-analysis-overview.htm). Supplemental evidence for smoothing, autocorrelation and forecasting.
- **V07** — [Public 14.1 process-analysis overview](https://docs.tibco.com/pub/stat/14.1.0/doc/html/UserGuide/_shared/process-analysis-overview.htm). Capability, measurement systems and failure-time families.
- **V08** — [Public 14.0 attribute chart inventory](https://docs.tibco.com/pub/dsc-stat/14.0.0/doc/html/UsersGuide/GUID-56CBE871-ED56-4A7B-8D8F-9B289A73BA12.html). Function evidence for c, u, np and p charts.
- **V09** — [Public 14.1 sign-test topic](https://docs.tibco.com/pub/stat/14.1.0/doc/html/UserGuide/_shared/nonparametrics-statistics-notes-sign-test.htm). Function existence only; implementation follows independent methods.
- **V10** — [Public 14.1 central-composite design topic](https://docs.tibco.com/pub/stat/14.1.0/doc/html/UserGuide/_shared/design-and-analysis-of-central-composite-response-surface-experiments.htm). Function evidence for central-composite design and surface analysis.
- **V11** — [Public 14.1 factorial-design topic](https://docs.tibco.com/pub/dsc-stat/14.1.0/doc/html/UserGuide/user-guide/factorial-anova-in-grm.htm). Factorial analysis, fractional designs and Box-Behnken families.
- **V12** — [Public 14.1 Six Sigma analysis links](https://docs.tibco.com/pub/stat/14.1.0/doc/html/UserGuide/13-customizing-statistica/analyze-button.htm). Cause-and-effect diagrams, stratification and 3D scatter.
- **V13** — [Public vendor permissions inventory, version 13.4](https://support.tibco.com/external/article/81029/statistica-enterprise-users-analysis-mod.html). Discovery only. Version 13.4 cannot independently prove 14.0 feature availability.
- **V14** — [Public 14.0 documentation topic index](https://docs.tibco.com/pub/stat/14.0.0/doc/html/UsersGuide/suitehelp_topic_list.html). Search-index topic names available; direct open returned no body. Lower-confidence topic evidence only.
- **V15** — [Public reseller desktop module inventory, undated version](https://statistica.pro/en/products/desktop/). Discovery only; dynamic time warping needs version-specific confirmation.
- **M01** — [NIST statistical handbook](https://www.itl.nist.gov/div898/handbook/). Public method reference; use relevant chapter and equation when implementing.
- **M02** — [SciPy statistical API](https://docs.scipy.org/doc/scipy/reference/stats.html). Public methods and API coverage. An API mapping is not implementation verification.
- **M03** — [NumPy quantile definitions](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html). Hyndman-Fan quantile variants; explicit method selection required.
- **M04** — [statsmodels API](https://www.statsmodels.org/stable/api.html). Regression, inference, models, power and time-series methods.
- **M05** — [scikit-learn supervised methods](https://scikit-learn.org/stable/supervised_learning.html). Predictive methods; inference is not implied by a predictor.
- **M06** — [scikit-learn unsupervised methods](https://scikit-learn.org/stable/unsupervised_learning.html). Decomposition, clustering and manifold methods.
- **M07** — [lifelines method documentation](https://lifelines.readthedocs.io/en/latest/). Survival estimators, regression and diagnostics.
- **M08** — [pandas API](https://pandas.pydata.org/docs/reference/index.html). Table operations and file interchange.
- **M09** — [Arrow dataset documentation](https://arrow.apache.org/docs/python/dataset.html). Chunked tables, scans and Parquet datasets.
- **M10** — [Python combinatorial functions](https://docs.python.org/3.12/library/math.html). Exact combinations and permutations.
- **M11** — [NIST statistical reference datasets](https://www.nist.gov/itl/sed/statistical-reference-datasets). Independent numerical references; certified families do not cover all planned features.
- **M12** — [SciPy integration](https://docs.scipy.org/doc/scipy/reference/integrate.html). Numerical quadrature; convergence and domain validation required.
- **M13** — [SciPy optimization](https://docs.scipy.org/doc/scipy/reference/optimize.html). Constrained and unconstrained fitting and scalar root solving.
- **M14** — [Hyndman and Fan, 1996](https://doi.org/10.1080/00031305.1996.10473566). Sample quantile definitions, American Statistician 50(4), 361-365.
- **M15** — [SciPy signal processing](https://docs.scipy.org/doc/scipy/reference/signal.html). Spectral density and periodograms.
- **M16** — [SciPy hierarchical clustering](https://docs.scipy.org/doc/scipy/reference/cluster.hierarchy.html). Linkage and dendrogram geometry.
- **M17** — [Apple Swift Charts](https://developer.apple.com/documentation/charts). Native presentation; numerical chart data come from the engine.
- **M18** — [Apple document architecture](https://developer.apple.com/documentation/appkit/nsdocument). Native document lifecycle, saving and undo.
- **M19** — [SQLite language reference](https://www.sqlite.org/lang.html). Relational querying and SQL data interchange.
- **M20** — [pyreadstat supported formats](https://github.com/Roche/pyreadstat). ReadStat-based interchange; read/write capabilities differ by format.
- **M21** — [Python build standalone distribution metadata](https://github.com/astral-sh/python-build-standalone/blob/main/docs/distributions.rst). Inspect each artifact, architecture and component license before bundling.
- **M22** — [Apple notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution). Developer ID, timestamp, signatures and hardened runtime.
- **M23** — [Apple signing workflow](https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac/). Distribution packaging and manual signing approach.
- **M24** — [CPython 3.12 license](https://docs.python.org/3.12/license.html). PSF and historical license terms; not solely BSD/MIT/Apache.
- **M25** — [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html). Bootstrap confidence intervals and resampling.
