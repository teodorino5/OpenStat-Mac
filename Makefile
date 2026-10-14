UV ?= uv
PYTHON = engine/.venv/bin/python

.PHONY: setup build check test python-test lint package run benchmark benchmark-large benchmark-paging feature-matrix
setup:
	$(UV) sync --directory engine --python 3.12 --locked
	$(PYTHON) scripts/localization.py
build:
	$(PYTHON) scripts/localization.py
	swift build
python-test:
	$(UV) run --directory engine pytest --cov=openstat_engine --cov-report=term-missing --cov-report=json:coverage.json --junitxml=junit.xml
lint:
	$(UV) run --directory engine ruff check src tests ../scripts
	$(UV) run --directory engine mypy src
	swift format lint --strict --recursive App Sources Tests Package.swift
feature-matrix:
	$(PYTHON) scripts/feature_matrix.py
check: build python-test lint
	$(PYTHON) scripts/arrow_fixtures.py
	swift run OpenStatSmoke
	$(PYTHON) scripts/feature_matrix.py
	$(PYTHON) scripts/check_localization.py
test: check
	swift test
package: build
	$(PYTHON) scripts/package_devapp.py
run: package
	open "build/OpenStat Mac.app"
benchmark:
	$(PYTHON) scripts/benchmark.py

benchmark-large:
	$(PYTHON) scripts/benchmark_large.py
benchmark-paging:
	$(PYTHON) scripts/benchmark_paging.py
