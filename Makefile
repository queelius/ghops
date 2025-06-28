.PHONY: help install clean build publish serve-docs build-docs deploy-docs bump-version test test-unit test-integration test-coverage

# Get the version from pyproject.toml
VERSION := $(shell grep "^version" pyproject.toml | awk -F' = ' '{print $$2}' | tr -d '"')

help:
	@echo "Commands:"
	@echo "  install       - Install the project in editable mode with dev dependencies."
	@echo "  clean         - Clean up build artifacts and caches."
	@echo "  build         - Build the wheel and sdist."
	@echo "  publish       - Publish the package to PyPI."
	@echo "  serve-docs    - Serve the documentation locally."
	@echo "  build-docs    - Build the documentation site."
	@echo "  deploy-docs   - Deploy the documentation to GitHub Pages."
	@echo "  bump-version  - Bump the package version (e.g., make bump-version BUMP=minor)."
	@echo "  test          - Run all tests."
	@echo "  test-unit     - Run unit tests only."
	@echo "  test-integration - Run integration tests only."
	@echo "  test-coverage - Run tests with coverage report."

install:
	pip install -e .[dev]

install-test:
	pip install -e .[test]

clean:
	@rm -rf build dist .eggs *.egg-info site .pytest_cache .mypy_cache .coverage __pycache__ ghops/__pycache__ tests/__pycache__

test:
	python -m pytest tests/ -v

test-unit:
	python -m pytest tests/test_utils.py tests/test_status.py tests/test_pypi.py tests/test_config.py tests/test_social.py -v

test-integration:
	python -m pytest tests/test_integration.py -v

test-coverage:
	python -m pytest tests/ --cov=ghops --cov-report=html --cov-report=term-missing

test-simple:
	python tests/run_tests.py

build:
	python -m build

publish: clean build
	twine upload dist/*

serve-docs:
	mkdocs serve

build-docs:
	mkdocs build

deploy-docs:
	mkdocs gh-deploy

bump-version:
	@python scripts/bump_version.py $(BUMP)

