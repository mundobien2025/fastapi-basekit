# Guía de contribución

!!! info "Mantenedores"
    Para release flow, CI/CD, mike y troubleshooting ver [`RELEASING.md`](https://github.com/mundobien2025/fastapi-basekit/blob/main/RELEASING.md) en el repo.

## Setup local

```bash
git clone https://github.com/mundobien2025/fastapi-basekit
cd fastapi-basekit
python -m venv .venv
source .venv/bin/activate
pip install -e .[all]
pip install -r requirements-dev.txt
```

## Tests

```bash
pytest tests/
pytest tests/ -v -k "test_repository"
pytest tests/ --cov=fastapi_basekit --cov-report=html
```

## Linting

```bash
black --line-length 100 fastapi_basekit/ tests/
isort fastapi_basekit/ tests/
flake8 --max-line-length 100 fastapi_basekit/
```

## Build local

```bash
pip install build
python -m build
ls dist/   # → fastapi_basekit-X.Y.Z-py3-none-any.whl
```

## Publicar a PyPI

```bash
pip install twine
python -m build
twine upload dist/*
```

## Convenciones

- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`)
- **Branches**: `feat/...`, `fix/...`, `docs/...`
- **PRs**: descripción clara, link a issue si existe, tests para cambios funcionales
- **Versioning**: semver. Bump en `pyproject.toml` + `CHANGELOG.md`

## Estructura del repo

```
fastapi_basekit/
├── aio/                    ← clases async (sqlalchemy, sqlmodel, beanie)
├── exceptions/             ← APIException + handlers
├── schema/                 ← BaseResponse, TokenSchema
├── servicios/              ← JWTService
├── cli/                    ← `basekit init` CLI
└── templates/              ← cookiecutter project template
.claude/
└── skills/
    └── fastapi-basekit-crud/SKILL.md   ← Claude Code skill
docs/                       ← MkDocs Material
tests/                      ← pytest
examples/                   ← apps de ejemplo por patrón
```

## Reportar bug

Issues en GitHub. Incluye:
- Versión de Python, fastapi-basekit, ORM
- Snippet mínimo reproducible
- Stack trace completo
- Comportamiento esperado vs actual

[:octicons-arrow-right-24: Desarrollo](development.md){ .md-button .md-button--primary }
