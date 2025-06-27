.PHONY: help install clean build publish serve-docs build-docs deploy-docs bump-version

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

install:
	pip install -e .

clean:
	@rm -rf build dist .eggs *.egg-info site .pytest_cache .mypy_cache .coverage __pycache__ ghops/__pycache__

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

