# Audit sources and research boundaries

Audit date: 2026-10-14 (Europe/Prague). This document records the initial research pass; later installed/tested implementation evidence is in VALIDATION.md.

Public vendor pages provide only evidence that a module or named function exists. Statistical algorithms, educational explanations and implementation must come from independent public statistical literature and permissive libraries. No downloaded vendor assets or documentation are included.

V01 is the primary 14.0 module source. V02 describes 14.0.1 basic functions. V03 describes 14.0 data-mining families. V04-V12 are explicitly version-labeled supplemental pages. V13 is older, and V15 is undated/version-unspecified: discovery only. V14 was visible through search-index results, while the web-tool direct open returned no body. A follow-up direct HTTP retrieval succeeded; keyword checks confirmed names for the supplementary distribution, noncentral, life-table, runs-test, NIPALS and X-11 families. No source page was persisted. Keep topic evidence below function-specific documentation and recheck exact variants before claiming parity.

M01-M13, M15-M25 were directly opened in research; Apple pages expose limited text in the web parser. M14 DOI resolution returned an error; NumPy's quantile documentation independently identifies the same paper and definitions. No library was installed or executed to validate numerical behavior. Opening a reference page does not verify every method mapped to it.

The matrix separates brief requirements from vendor function, module, topic and discovery evidence. Unknown families are retained instead of guessed. The discovered module families include fundamentals, ANOVA, regression, nonparametrics, distributions, generalized and nonlinear models, multivariate methods, reliability, time series, survival, power, industrial methods, experimental design, predictive modeling, neural networks, mining, graphs and data/report/workflow management. Enterprise and proprietary compatibility functions are explicitly excluded.

Method bibliography to refine per procedure after approval: Hyndman and Fan (1996), Sample Quantiles in Statistical Packages, DOI 10.1080/00031305.1996.10473566; NIST/SEMATECH e-Handbook; NIST StRD certified problems; published original method references linked by SciPy/statsmodels/scikit-learn/lifelines. Do not copy textbook exercises into sample datasets. Use new small datasets and independently record their arithmetic.

Version-specific method and license evidence must be pinned to release tags and artifact hashes during Phase 0. Rolling documentation is suitable for architectural research, not a reproducible dependency lock.

## Register

- **V01**: [Public 14.0 academic feature inventory](https://support.tibco.com/external/article/KB0070828/statistica-academic-bundle-feature-detai.html). Vendor module names; not evidence for every option within a module.
- **V02**: [Public 14.0.1 basic analysis overview](https://docs.tibco.com/pub/stat/14.0.1/doc/html/UsersGuide/user-guide/basic-statistics-overview.htm). Frequency, correlation, grouped summaries, t-tests, crosstabs and response tables.
- **V03**: [Public 14.0 data-mining overview](https://docs.tibco.com/pub/stat/14.0.0/doc/html/UsersGuide/GUID-050E6A8F-4660-4B6A-9265-56527282E606.html). Trees, ensembles, text, predictor screening, response coding and deployment.
- **V04**: [Public 14.3 multivariate module inventory](https://docs.tibco.com/pub/stat/14.3.0/doc/html/user-guide/user-guide/multivariate-exploratory-techniques-a.htm). Supplemental 14.x module evidence; does not establish 14.0 availability.
- **V05**: [Public 14.3 two-dimensional graph inventory](https://docs.tibco.com/pub/stat/14.3.0/doc/html/user-guide/6-working-with-graphs/2d-graphs.htm). Supplemental 14.x graph names, not copied artwork or interface design.
- **V06**: [Public 14.3 time-series overview](https://docs.tibco.com/pub/stat/14.3.0/doc/html/user-guide/_shared/time-series-analysis-overview.htm). Supplemental evidence for smoothing, autocorrelation and forecasting.
- **V07**: [Public 14.1 process-analysis overview](https://docs.tibco.com/pub/stat/14.1.0/doc/html/UserGuide/_shared/process-analysis-overview.htm). Capability, measurement systems and failure-time families.
- **V08**: [Public 14.0 attribute chart inventory](https://docs.tibco.com/pub/dsc-stat/14.0.0/doc/html/UsersGuide/GUID-56CBE871-ED56-4A7B-8D8F-9B289A73BA12.html). Function evidence for c, u, np and p charts.
- **V09**: [Public 14.1 sign-test topic](https://docs.tibco.com/pub/stat/14.1.0/doc/html/UserGuide/_shared/nonparametrics-statistics-notes-sign-test.htm). Function existence only; implementation follows independent methods.
- **V10**: [Public 14.1 central-composite design topic](https://docs.tibco.com/pub/stat/14.1.0/doc/html/UserGuide/_shared/design-and-analysis-of-central-composite-response-surface-experiments.htm). Function evidence for central-composite design and surface analysis.
- **V11**: [Public 14.1 factorial-design topic](https://docs.tibco.com/pub/dsc-stat/14.1.0/doc/html/UserGuide/user-guide/factorial-anova-in-grm.htm). Factorial analysis, fractional designs and Box-Behnken families.
- **V12**: [Public 14.1 Six Sigma analysis links](https://docs.tibco.com/pub/stat/14.1.0/doc/html/UserGuide/13-customizing-statistica/analyze-button.htm). Cause-and-effect diagrams, stratification and 3D scatter.
- **V13**: [Public vendor permissions inventory, version 13.4](https://support.tibco.com/external/article/81029/statistica-enterprise-users-analysis-mod.html). Discovery only. Version 13.4 cannot independently prove 14.0 feature availability.
- **V14**: [Public 14.0 documentation topic index](https://docs.tibco.com/pub/stat/14.0.0/doc/html/UsersGuide/suitehelp_topic_list.html). Search-index topic names available; direct open returned no body. Lower-confidence topic evidence only.
- **V15**: [Public reseller desktop module inventory, undated version](https://statistica.pro/en/products/desktop/). Discovery only; dynamic time warping needs version-specific confirmation.
- **M01**: [NIST statistical handbook](https://www.itl.nist.gov/div898/handbook/). Public method reference; use relevant chapter and equation when implementing.
- **M02**: [SciPy statistical API](https://docs.scipy.org/doc/scipy/reference/stats.html). Public methods and API coverage. An API mapping is not implementation verification.
- **M03**: [NumPy quantile definitions](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html). Hyndman-Fan quantile variants; explicit method selection required.
- **M04**: [statsmodels API](https://www.statsmodels.org/stable/api.html). Regression, inference, models, power and time-series methods.
- **M05**: [scikit-learn supervised methods](https://scikit-learn.org/stable/supervised_learning.html). Predictive methods; inference is not implied by a predictor.
- **M06**: [scikit-learn unsupervised methods](https://scikit-learn.org/stable/unsupervised_learning.html). Decomposition, clustering and manifold methods.
- **M07**: [lifelines method documentation](https://lifelines.readthedocs.io/en/latest/). Survival estimators, regression and diagnostics.
- **M08**: [pandas API](https://pandas.pydata.org/docs/reference/index.html). Table operations and file interchange.
- **M09**: [Arrow dataset documentation](https://arrow.apache.org/docs/python/dataset.html). Chunked tables, scans and Parquet datasets.
- **M10**: [Python combinatorial functions](https://docs.python.org/3.12/library/math.html). Exact combinations and permutations.
- **M11**: [NIST statistical reference datasets](https://www.nist.gov/itl/sed/statistical-reference-datasets). Independent numerical references; certified families do not cover all planned features.
- **M12**: [SciPy integration](https://docs.scipy.org/doc/scipy/reference/integrate.html). Numerical quadrature; convergence and domain validation required.
- **M13**: [SciPy optimization](https://docs.scipy.org/doc/scipy/reference/optimize.html). Constrained and unconstrained fitting and scalar root solving.
- **M14**: [Hyndman and Fan, 1996](https://doi.org/10.1080/00031305.1996.10473566). Sample quantile definitions, American Statistician 50(4), 361-365.
- **M15**: [SciPy signal processing](https://docs.scipy.org/doc/scipy/reference/signal.html). Spectral density and periodograms.
- **M16**: [SciPy hierarchical clustering](https://docs.scipy.org/doc/scipy/reference/cluster.hierarchy.html). Linkage and dendrogram geometry.
- **M17**: [Apple Swift Charts](https://developer.apple.com/documentation/charts). Native presentation; numerical chart data come from the engine.
- **M18**: [Apple document architecture](https://developer.apple.com/documentation/appkit/nsdocument). Native document lifecycle, saving and undo.
- **M19**: [SQLite language reference](https://www.sqlite.org/lang.html). Relational querying and SQL data interchange.
- **M20**: [pyreadstat supported formats](https://github.com/Roche/pyreadstat). ReadStat-based interchange; read/write capabilities differ by format.
- **M21**: [Python build standalone distribution metadata](https://github.com/astral-sh/python-build-standalone/blob/main/docs/distributions.rst). Inspect each artifact, architecture and component license before bundling.
- **M22**: [Apple notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution). Developer ID, timestamp, signatures and hardened runtime.
- **M23**: [Apple signing workflow](https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac/). Distribution packaging and manual signing approach.
- **M24**: [CPython 3.12 license](https://docs.python.org/3.12/license.html). PSF and historical license terms; not solely BSD/MIT/Apache.
- **M25**: [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html). Bootstrap confidence intervals and resampling.

## Swift Arrow interoperability slice

The original bounded reader follows the [Apache Arrow columnar/IPC format](https://arrow.apache.org/docs/format/Columnar.html) and public [File.fbs](https://github.com/apache/arrow/blob/main/format/File.fbs), [Message.fbs](https://github.com/apache/arrow/blob/main/format/Message.fbs) and [Schema.fbs](https://github.com/apache/arrow/blob/main/format/Schema.fbs) layouts. These are rolling specifications reviewed on 2026-10-14. The implemented subset is validated against the locked PyArrow 25.0.1 writer. No Apache Arrow Swift source, generated FlatBuffers code or additional dependency is copied into the repository. Unsupported schema features fail explicitly.
