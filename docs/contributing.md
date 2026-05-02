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

### Commits — Conventional Commits estricto

Formato:

```
<type>(<scope>): <subject>

<body opcional>

<footer opcional>
```

**Tipos permitidos** (cualquier otro = rechazado por hook):

| Tipo | Cuándo usar |
|------|-------------|
| `feat` | Funcionalidad nueva visible al usuario de la lib |
| `fix` | Bug que afectaba comportamiento documentado |
| `docs` | Solo `README.md`, `docs/`, docstrings, CHANGELOG |
| `refactor` | Reestructuración sin cambio de comportamiento |
| `perf` | Optimización de performance |
| `test` | Tests añadidos/modificados, sin tocar código de producción |
| `build` | `pyproject.toml`, requirements, packaging |
| `ci` | `.github/workflows/`, scripts de release |
| `chore` | Mantenimiento (bumps, renames, gitignore) |
| `style` | Formato (black, isort) — sin cambio funcional |
| `revert` | Revertir commit previo |

**Reglas de subject** (línea 1):

- Imperativo presente: `add X`, no `added X` ni `adds X`
- Lowercase, sin punto final
- ≤ 72 caracteres
- Sin emoji ni marketing fluff (`amazing new feature` ← no)
- Inglés (PyPI / GitHub audiencia internacional)
- Scope opcional pero útil: `feat(beanie):`, `fix(repository):`, `docs(api-reference):`

**Ejemplos reales del repo**:

```
✓ feat(beanie): add build_list_pipeline + build_list_queryset hooks
✓ fix(repository): coerce str → ObjectId in Link.id filters
✓ docs(api-reference): document use_aggregation flag
✓ chore: bump version to 0.3.2
✓ build: pin setuptools to emit Core Metadata 2.3
✓ refactor(service): extract _build_match_stage helper

✗ feature: add stuff                  ← typo + vago
✗ fix: changes                        ← no es fix + vago
✗ add version                         ← sin tipo + vago
✗ Update README.md                    ← UI commit GitHub (evitar)
```

**Body** (opcional, separado por línea en blanco):

- Wrap a 72 chars
- Explica el *por qué*, no el *qué* (el diff ya muestra el qué)
- Issue references al final: `Closes #123`, `Refs #456`

### Setup del template + hook

```bash
# Activa template global del repo
git config --local commit.template .gitmessage

# Hook commitlint (rechaza commits que no cumplan)
pip install pre-commit
pre-commit install --hook-type commit-msg
```

### Branches

- `feat/<descripción-corta>` — features nuevas
- `fix/<bug-id-o-descripción>` — bugfixes
- `docs/<área>` — solo docs
- `chore/<descripción>` — mantenimiento

### PRs

- Título: mismo formato que commit
- Descripción: contexto + cambios + tests + breaking changes (si aplica)
- Link a issue: `Closes #N`
- Tests obligatorios para `feat:` y `fix:`

### Versioning

- Semver. Bump en `pyproject.toml` + `plugin.json` + `marketplace.json` + `CHANGELOG.md`
- `make release V=X.Y.Z` automatiza todo

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
