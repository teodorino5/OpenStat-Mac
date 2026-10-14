# Third-party candidate license ledger

Date: 2026-10-14. Contributor slice. **No Python runtime or third-party numerical package is bundled in the app.** This file is not a completed attribution bundle or a clearance of any wheel/runtime artifact. Release tags, exact versions, hashes, full required license texts and all transitive/native notices must be recorded before bundling.

| Candidate | Top-level license or status | Purpose | Public source | Bundling decision |
| --- | --- | --- | --- | --- |
| NumPy | BSD-3-Clause | Arrays and stable reductions | [License](https://github.com/numpy/numpy/blob/main/LICENSE.txt) | Candidate; wheel/native contents pending |
| SciPy | BSD-3-Clause | Public statistical methods | [License](https://github.com/scipy/scipy/blob/main/LICENSE.txt) | Candidate; wheel/native contents pending |
| pandas | BSD-3-Clause | Bounded-size table adapters | [License](https://github.com/pandas-dev/pandas/blob/main/LICENSE) | Candidate; exact artifact pending |
| statsmodels | BSD-3-Clause | Inference and models | [License](https://github.com/statsmodels/statsmodels/blob/main/LICENSE.txt) | Candidate; exact artifact pending |
| scikit-learn | BSD-3-Clause | Predictive and multivariate methods | [License](https://github.com/scikit-learn/scikit-learn/blob/main/COPYING) | Candidate; exact artifact pending |
| lifelines | MIT | Survival methods | [License](https://github.com/CamDavidsonPilon/lifelines/blob/master/LICENSE) | Candidate; transitive dependencies pending |
| pyreadstat | Apache-2.0 | Statistical dataset interchange | [Repository](https://github.com/Roche/pyreadstat) | Candidate; direct public README confirms top-level terms |
| ReadStat | MIT | Native format parser behind pyreadstat | [pyreadstat license description](https://github.com/Roche/pyreadstat/blob/master/README.md?plain=1) | Candidate; full component notices pending |
| CPython 3.12 | PSF and historical terms | Embedded interpreter | [License](https://docs.python.org/3.12/license.html) | Requires dependency-policy decision; not exclusively BSD/MIT/Apache |
| python-build-standalone artifacts | Mixed component licenses; unreviewed exact artifact | Candidate relocatable runtime | [Distribution metadata](https://github.com/astral-sh/python-build-standalone/blob/main/docs/distributions.rst) | Do not bundle until full per-artifact audit excludes all disallowed components |
| Apache Arrow / pyarrow 25.0.1 | Apache-2.0 confirmed from installed wheel metadata; full artifact review pending | IPC, streaming scans and Parquet | [Project](https://arrow.apache.org/) | Candidate; exact native/compression notices pending |
| openpyxl | MIT candidate, not checked at a pinned release | Excel interchange | [Project](https://openpyxl.readthedocs.io/) | Pending precise release/license verification |
| python-docx | MIT candidate, not checked at a pinned release | DOCX reports | [Project](https://python-docx.readthedocs.io/) | Pending precise release/license verification |
| SQLite | Public domain, outside literal BSD/MIT/Apache allowlist | Local SQL interchange | [License](https://www.sqlite.org/copyright.html) | Requires policy decision and exact bundled-component audit |
| Swift Arrow decoder | Original MIT code | Bounded viewport IPC reader | — | Original bounded reader, no third-party Swift parser |
| Swift toolchain/runtime components | Apache-2.0 with runtime exceptions and component terms; artifact audit pending | Native build/distribution | [Swift license](https://www.swift.org/LICENSE.txt) | Build-time and distributed runtime components must be distinguished |
| BLAS, Fortran, compression, crypto, XML and all remaining transitives | Unknown until resolved artifacts exist | Wheel/runtime support | Per-artifact metadata and SBOM required | No approval inferred from parent package license |

## Review rules

Audit the exact files shipped for arm64 and x86_64, including Python standard-library extensions, native wheel dependencies, runtime libraries and full license notices. A top-level permissive license is insufficient evidence for the whole artifact. An SBOM must identify component versions, source/license URLs, SPDX expression, artifact hash and distribution path.

The supplied policy prohibits GPL code and accepts permissive libraries only. This plan interprets that conservatively to also reject other copyleft artifacts, including LGPL, unless the user changes the policy. No GPL tool/runtime is proposed for bundling. An external R cross-check is development evidence only; R must not enter application contents or release images.

The user's literal parenthetical allowlist needs clarification because the requested interpreter is licensed under PSF terms. Recommend explicit individually reviewed permissive exceptions instead of silently marking PSF as BSD. Until the decision and exact artifact audit, runtime distribution remains pending.

## Audited development additions

The developer environment now pins NumPy 2.5.4, Narwhals 2.27.1, PyReadStat 1.3.6, pandas 3.0.6, python-dateutil 2.9.0.post0 and six 1.17.0. The inspected macOS 14 NumPy wheels use system Accelerate and omit GNU runtime libraries. PyReadStat includes MIT ReadStat and links system zlib/iconv; no copies of those system libraries are bundled. Narwhals and six are MIT, pandas is BSD-3-Clause, and python-dateutil has BSD/Apache terms. See [exact artifacts, hashes and native-link inspection](docs/PYREADSTAT_AUDIT.md).

This allows the scoped developer route. It does not clear the complete app runtime. Older-tag NumPy wheels containing GNU runtimes are explicitly excluded from the eventual bundle even though the package top-level license is permissive. The application still embeds no Python runtime or third-party wheels.

## Current development lock

engine/uv.lock pins the actual developer packages and artifact hashes. Python 3.12.14 and pyarrow 25.0.1 ran on Intel. Installed pyarrow metadata identifies Apache-2.0 and includes LICENSE.txt/NOTICE.txt. This is a top-level development check, not a completed binary-component redistribution audit. Test/lint packages are development-only and are not copied into the app. The contributor executable links native system frameworks; only original Swift code and catalog resources are packaged.
