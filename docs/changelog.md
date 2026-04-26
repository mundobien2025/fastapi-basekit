# Changelog

Ver el archivo raw en el repo: [CHANGELOG.md](https://github.com/mundobien2025/fastapi-basekit/blob/main/CHANGELOG.md)

## 0.3.0 — current

### Agregado

- **`basekit init`** — scaffolder cookiecutter con multi-ORM (sqlalchemy/beanie),
  multi-DB (postgres/mariadb/sqlite/mongodb), opcional redis/s3/arq, license picker.
  Genera proyecto completo: `app/`, `alembic/`, `docker-compose.yml`, `Dockerfile`,
  `Makefile`, `.env.example`, tests scaffold. `pip install fastapi-basekit[init]`.
- **Sitio docs MkDocs Material** versionado con `mike` (aliases `latest`, `X.Y`, `dev`).
  Auto-deploy a GitHub Pages.
- **Workflows GitHub Actions**: `publish.yml` (tag `v*` → PyPI OIDC + docs versionadas) y
  `docs.yml` (push main → preview en `dev` alias).
- **`scripts/release.py` + Makefile** — comando único `make release V=X.Y.Z`
  bumpea pyproject + plugin.json + marketplace.json + CHANGELOG, commit + tag + push.
  Modos: `--bump patch|minor|major`, `--dry-run`, `--pypi-only`, `--docs-only`.
- **Skill `fastapi-basekit-crud` v2** con secciones nuevas (§22-28): BaseService policy,
  alembic `render_item`, JWTService API real, `get_db` lean.
- **`RELEASING.md`** doc interna de mantenimiento.

### Corregido

- `BasePaginationResponse[Schema]` (era `[List[Schema]]` doble-anidado, rompía 8 errores per row).
- Mermaid runtime en docs (Material 9.7+ no auto-bootstrap).
- Alembic `render_item` para tipos custom (`GUID` y `LowercaseEnum`).

### Cambiado

- `get_db` lean — solo session lifecycle. Translation de errores en handlers.
- `self.action` automático en controllers/services. Skill: nunca asignar manual.
- `mkdocs.yml` con `pymdownx.emoji`, palette teal/deep-orange, font Inter + JetBrains Mono.

### Empaquetado

- Optional extras nuevos: `[init]` (cookiecutter), `[docs]` (mkdocs-material).
- `[project.scripts]`: `basekit = "fastapi_basekit.cli:main"`.

## 0.2.1

- Plugin Claude Code estable.
- Skill expandida con real-world fixes.

## 0.2.0

- Soporte SQLModel ORM (`fastapi_basekit.aio.sqlmodel`).
- BaseRepository / BaseService / SQLModelBaseController.

## 0.1.x

- Versiones iniciales con SQLAlchemy + Beanie.
- BaseRepository, BaseService, BaseController genérico.
- Sistema de permisos basado en clases.
- Paginación, búsqueda multi-campo, extracción automática de parámetros.
