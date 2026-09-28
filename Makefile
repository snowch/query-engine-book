# Queries, operator by operator: the commands the book tells you to run.
#
#   make            build the figures and the site
#   make serve      serve the built site at http://localhost:8000
#   make check      everything CI runs
#
# The engine is python/query_lab; its scan layer is the Parquet book's reader, from the
# external/parquet-book submodule. The site, the figures and the tests are views of both.

PYTHON ?= python3
PORT   ?= 8000
SHELL  := /bin/bash
export PYTHONPATH := python:external/parquet-book/python

.DEFAULT_GOAL := all

.PHONY: help
help:  ## Show this list
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

.PHONY: all
all: figures site  ## Build everything: figures and site

# -- setup ---------------------------------------------------------------------------------

.PHONY: install
install:  ## Install what the build needs: the submodule, Python packages, MyST, Pyodide
	git submodule update --init
	$(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt
	npm install -g "mystmd@$$(node -p "require('./package.json').devDependencies.mystmd")"
	npm install --no-audit --no-fund

# -- the engine ----------------------------------------------------------------------------

.PHONY: figures
figures:  ## Recompute every generated fragment the chapters include
	$(PYTHON) -m query_lab figures

.PHONY: fixtures
fixtures:  ## Rewrite the fixtures with the pinned pyarrow and DuckDB (rarely needed)
	$(PYTHON) fixtures/generate.py

# -- the book ------------------------------------------------------------------------------

.PHONY: site
site:  ## Parse the pages with MyST and render the site into _build/html
	./scripts/parse-book.sh
	$(PYTHON) scripts/build-site.py --out _build/html

.PHONY: serve
serve:  ## Serve the built site (run `make` first)
	@echo "  http://localhost:$(PORT)"
	@cd _build/html && $(PYTHON) -m http.server $(PORT)

.PHONY: chapter
chapter:  ## Write skeletons for chapters in tools/outline.py that have no page yet
	$(PYTHON) scripts/new-chapter.py --all

# -- tests ---------------------------------------------------------------------------------

.PHONY: test
test:  ## Run the tests
	$(PYTHON) -m pytest -q

.PHONY: browser-test
browser-test: all  ## Drive the DuckDB probe, every panel and workbench, and the site's chrome, in Chromium
	./scripts/browser-probe.sh
	node tests/browser/panels.mjs _build/html
	node tests/browser/workbench.mjs _build/html
	node tests/browser/site.mjs _build/html

.PHONY: check
check:  ## Everything CI runs
	./scripts/ci-check.sh

.PHONY: clean
clean:  ## Remove build output (committed fixtures and figures are kept)
	rm -rf _build
