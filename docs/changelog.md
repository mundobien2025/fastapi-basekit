# Changelog

Ver el archivo raw en el repo: [CHANGELOG.md](https://github.com/mundobien2025/fastapi-basekit/blob/main/CHANGELOG.md)

## 0.3.1 — current

### Agregado

- **Beanie filter alias `<field>_id`** en `BaseRepository.build_filter_query`.
  Filtros tipo `customer_id`, `user_id`, `tool_id` se traducen automáticamente
  a `Model.<field>.id == ObjectId(v)` cuando el campo base es `Link[X]`.
  Ver [Filtering > Beanie Link alias](user-guide/filtering.md#filtros-con-beanie-linkx--alias-field_id-031).
- **Coerción automática `str` → `ObjectId`** para queries contra `Link.id`.
  El front puede mandar el id crudo del query string sin cast.

### Corregido

- Import roto `from bson import ObjectId, Link` → `from beanie import Link`
  (`Link` no existe en bson; vive en `beanie.odm.fields.Link`).
  En 0.3.0 el import explotaba al cargar `BaseRepository` aislado.

### Cambiado

- Mínimos de deps: `pydantic>=2.13`, `pyjwt>=2.12.1`,
  extras `[beanie]` ahora pide `beanie>=2.0,<3` (sin `motor`),
  extras `[sqlalchemy]` ahora pide `SQLAlchemy[asyncio]>=2.0.30,<3`.

## 0.3.0

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
