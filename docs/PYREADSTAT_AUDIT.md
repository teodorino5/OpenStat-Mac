# PyReadStat packaging audit

Audit date: 2026-10-14. Scope: PyReadStat and its mandatory Python dependencies for this repository's CPython 3.12 and macOS 14+ target. This is a package artifact audit, not a complete application-runtime or legal review.

## Finding

PyReadStat 1.3.6 has a viable permissive-wheel route for both supported macOS architectures, if the runtime pins the audited dependencies and selects NumPy's `macosx_14_0` wheels. The `macosx_10_13` x86_64 and `macosx_11_0` arm64 NumPy wheels include extra native libraries. Do not bundle those older-tag wheels under this audit: they contain OpenBLAS, libgfortran, libquadmath, and libgcc_s. NumPy's build metadata identifies OpenBLAS as BSD-3-Clause plus BSD-3-Clause-Attribution, libgfortran as GPL-3.0 with GCC exception, and libquadmath as LGPL-2.1-or-later for these builds. The GCC exception grants defined distribution permission; this repository's stricter no-copyleft-bundling rule still excludes these wheels. [NumPy wheel licensing notes](https://github.com/numpy/numpy/blob/main/pyproject.toml), [GCC Runtime Library Exception](https://www.gnu.org/licenses/gcc-exception-3.1.en.html)

The accepted candidate set for reading and writing is PyReadStat 1.3.6, Narwhals 2.27.1, NumPy 2.5.4, pandas 3.0.6, python-dateutil 2.9.0.post0, and six 1.17.0. Pin these versions and wheel hashes in the eventual runtime lock. PyReadStat currently declares `narwhals>=2.10.1` and `numpy` without upper bounds. Pandas declares NumPy and python-dateutil requirements. An unconstrained resolver does not preserve this audit. [PyReadStat package metadata](https://pypi.org/project/pyreadstat/), [Narwhals 2.27.1](https://pypi.org/project/narwhals/2.27.1/), [NumPy 2.5.4](https://pypi.org/project/numpy/2.5.4/), [pandas 3.0.6](https://pypi.org/project/pandas/3.0.6/)

## Inspected artifacts

PyPI JSON supplied these filenames, sizes, and SHA-256 digests. The listed wheels were downloaded from their PyPI `files.pythonhosted.org` URLs, checked as ZIP archives, and inspected without installation.

| Package | CPython/macOS wheel | Size | SHA-256 |
| --- | --- | ---: | --- |
| PyReadStat 1.3.6 | `cp312-cp312-macosx_10_13_x86_64` | 772,771 bytes | `cd3c1b6b948ec8c7ac4cd140f4542a5fd076ef814a1e252d26b218624e975457` |
| PyReadStat 1.3.6 | `cp312-cp312-macosx_11_0_arm64` | 736,578 bytes | `6949c7535dc57115f3d5620b3f381ca76589f0fb079c20c26b7cbcdd5fca54db` |
| Narwhals 2.27.1 | `py3-none-any` | 483,211 bytes | `d057df13f5852b8e157596e82eb5e955fad267425df5e420e0ee9863da483b31` |
| NumPy 2.5.4 | `cp312-cp312-macosx_14_0_x86_64` | 6,789,926 bytes | `aec3fc4b32ff82421274f5d205c559c51c840c8df66a78efd7f3612dd005a26a` |
| NumPy 2.5.4 | `cp312-cp312-macosx_14_0_arm64` | 5,451,717 bytes | `9cb18a327b49c5c337f972b03682f6a49855525faaf3c0d3e9c96cd0fd8880a8` |
| pandas 3.0.6 | `cp312-cp312-macosx_10_13_x86_64` | 10,397,411 bytes | `7dac2d65e9087e8e7b5a45fe15c4920911a221df061ab629943ce016489145c7` |
| pandas 3.0.6 | `cp312-cp312-macosx_11_0_arm64` | 10,051,279 bytes | `9dab635a549e58a053c7b0fa054dc0bd7be22f0ed9a720f4a85d5fb993276172` |
| python-dateutil 2.9.0.post0 | `py2.py3-none-any` | 229,892 bytes | `a8b2bc7bffae282281c8140a97d3aa9c14da0b136dfe83f850eea9a5f7470427` |
| six 1.17.0 | `py2.py3-none-any` | 11,050 bytes | `4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274` |

The PyReadStat wheels contain Python modules, generated Cython C sources, and two native extensions: `_readstat_parser` and `_readstat_writer`. The extension sources build ReadStat into each extension; the wheels contain no separate ReadStat shared library, Cargo components, or other bundled native library. PyReadStat identifies its own code as Apache-2.0 and ReadStat as MIT. The audited extensions link only `/usr/lib/libSystem.B.dylib`, `/usr/lib/libz.1.dylib`, and `/usr/lib/libiconv.2.dylib`; none has an `LC_RPATH`. These are macOS system libraries, not libraries copied into the wheels. [PyReadStat license and component notice](https://github.com/Roche/pyreadstat/blob/master/LICENSE), [ReadStat MIT license](https://github.com/WizardMac/ReadStat/blob/master/LICENSE)

The two NumPy 2.5.4 `macosx_14_0` wheels contain no `.dylibs` directory. Their 19 native extensions link only Apple Accelerate, `/usr/lib/libc++.1.dylib`, and `/usr/lib/libSystem.B.dylib`; none has an `LC_RPATH`. Their wheel metadata declares `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`. This satisfies the repository's stated copyleft restriction for these inspected artifacts. The older x86_64 and arm64 wheel tags do contain the extra libraries named above, so architecture alone is not enough to select a safe NumPy wheel. [NumPy wheel build metadata](https://github.com/numpy/numpy/blob/main/pyproject.toml), [NumPy redistributable binary guidance](https://numpy.org/doc/stable/building/redistributable_binaries.html)

Narwhals 2.27.1 is a pure-Python wheel with MIT metadata and no native extensions. Its backend integrations are optional extras; PyReadStat's base requirements do not request them. NumPy is a mandatory PyReadStat dependency. Pandas is included in the accepted candidate stack because PyReadStat's writer accepts pandas or Polars data frames; no Polars wheel is required or audited.

Pandas 3.0.6 is BSD-3-Clause. Each audited macOS wheel contains 45 native modules, all linking only `/usr/lib/libSystem.B.dylib` and `/usr/lib/libc++.1.dylib`; the wheels contain no `.dylibs` or `.libs` directory and no `LC_RPATH`. The pure-Python python-dateutil 2.9.0.post0 wheel identifies its dual permissive license; it requires six 1.17.0, which is MIT. Pandas does not require pytz or tzdata on macOS. No copyleft native dependency appeared in these exact artifacts. [pandas 3.0.6 metadata](https://pypi.org/project/pandas/3.0.6/), [python-dateutil 2.9.0.post0](https://pypi.org/project/python-dateutil/2.9.0.post0/), [six 1.17.0](https://pypi.org/project/six/1.17.0/)

## Reproduction and limits

Inspection used Python's `zipfile`, PyPI's JSON API, `file`, `otool -L`, `otool -l`, and `nm` on the downloaded archives. Scratch archives and extracted files live under ignored `work/pyreadstat-audit/`; they are not application artifacts. The source distribution was also inspected to confirm that PyReadStat compiles its bundled ReadStat source and links zlib and iconv on macOS.

This finding covers only these exact Python wheels. It does not clear the embedded CPython runtime, PyArrow, the complete application wheel set, signing, or clean-system launch. Those remain separate distribution gates. The allowed route depends on the app's current macOS 14 minimum and CPython 3.12; changing either requires another wheel and native-link audit.

## Format documentation note

Official public documentation is not equally complete across these formats. Stata publishes a `.dta` file-format manual, and SAS documents XPORT transport-file versions and compatibility. IBM's public SPSS help explains that SAV files combine case data and a dictionary with labels and missing-value metadata, but the reviewed page does not provide a byte-level file specification. These sources support implementing bounded, explicitly scoped readers from documented behavior; they do not establish that every version or feature can be implemented from these pages alone. A future original parser must define supported versions, use no proprietary code or test datasets, and verify against independently created fixtures. [Stata `.dta` format manual](https://www.stata.com/manuals/pfileformatsdta.pdf), [SAS transport documentation](https://documentation.sas.com/api/collections/pgmsascdc/v_028/docsets/movefile/content/movefile.pdf), [IBM SPSS data-file description](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=files-spss-statistics-data)
