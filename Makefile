.PHONY: help install test format lint build clean \
        release release-no-docs release-docs-only release-dry _release \
        docs docs-serve docs-deploy-dev docs-deploy-version \
        template-test bump

VERSION ?= $(shell python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
ALIAS    = $(shell echo $(VERSION) | cut -d. -f1-2)

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

## ── Dev ─────────────────────────────────────────────────────────────────────
install: ## Editable install + all extras
	pip install -e .[all]

test: ## Run pytest
	pytest tests/ -v

format: ## black + isort
	black --line-length 100 fastapi_basekit/ tests/
	isort fastapi_basekit/ tests/

lint: ## flake8
	flake8 --max-line-length 100 fastapi_basekit/

build: ## Build wheel + sdist
	rm -rf dist/ build/ *.egg-info
	pip install --upgrade build
	python -m build

clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info site/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

## ── Release (one command, bumps everything) ────────────────────────────────
release: ## Full release. Usage: make release V=0.3.0  |  make release BUMP=patch|minor|major
	@$(MAKE) -s _release ARGS=""

release-no-docs: ## PyPI only. Usage: make release-no-docs V=0.3.0
	@$(MAKE) -s _release ARGS="--pypi-only"

release-docs-only: ## Docs only. Usage: make release-docs-only V=0.3.0
	@$(MAKE) -s _release ARGS="--docs-only"

release-dry: ## Preview changes without writing. Usage: make release-dry V=0.3.0
	@$(MAKE) -s _release ARGS="--dry-run"

_release:
	@if [ -n "$(V)" ] && [ -n "$(BUMP)" ]; then \
		echo "ERROR: pass either V= or BUMP=, not both"; exit 1; \
	elif [ -n "$(V)" ]; then \
		python3 scripts/release.py $(V) $(ARGS); \
	elif [ -n "$(BUMP)" ]; then \
		python3 scripts/release.py --bump $(BUMP) $(ARGS); \
	else \
		echo "Usage:"; \
		echo "  make release V=0.3.0                 # full PyPI + docs"; \
		echo "  make release BUMP=patch              # auto +1 patch"; \
		echo "  make release-no-docs V=0.3.0         # PyPI only"; \
		echo "  make release-docs-only V=0.3.0       # docs only"; \
		echo "  make release-dry V=0.3.0             # dry-run"; \
		exit 1; \
	fi

bump: ## Print current version
	@echo "$(VERSION)"

## ── Docs ────────────────────────────────────────────────────────────────────
docs: ## Build static docs site
	pip install -e .[docs]
	mkdocs build

docs-serve: ## Serve docs locally :8001
	pip install -e .[docs]
	mkdocs serve -a localhost:8001

docs-deploy-dev: ## Local manual deploy → `dev` alias (mike)
	pip install -e .[docs]
	mike deploy --push dev

docs-deploy-version: ## Local manual deploy current version + alias `latest`
	pip install -e .[docs]
	mike deploy --push --update-aliases $(ALIAS) latest
	mike set-default --push latest

## ── Template ────────────────────────────────────────────────────────────────
template-test: ## Smoke test cookiecutter scaffold
	rm -rf /tmp/basekit_template_test
	mkdir /tmp/basekit_template_test
	cd /tmp/basekit_template_test && basekit init --no-input \
	  --extra-context project_name="Smoke Test" \
	  --extra-context orm=sqlalchemy \
	  --extra-context database=postgres
	@echo "Generated at /tmp/basekit_template_test/smoke_test"
