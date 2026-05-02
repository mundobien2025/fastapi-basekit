<div align="center">

<img src="docs/assets/logo-mark.svg" width="120" alt="fastapi-basekit">

# fastapi-basekit

**FastAPI toolkit con repos, services y controllers listos para producción.**
**Multi-ORM · CLI scaffolder · plugin Claude Code.**

[![PyPI](https://img.shields.io/pypi/v/fastapi-basekit?style=flat-square&color=009485&logo=pypi&logoColor=white)](https://pypi.org/project/fastapi-basekit/)
[![Python](https://img.shields.io/badge/python-3.11+-2c5282?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/fastapi-basekit/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-c41616?style=flat-square)](https://www.sqlalchemy.org/)
[![Beanie](https://img.shields.io/badge/MongoDB-Beanie-47A248?style=flat-square&logo=mongodb&logoColor=white)](https://beanie-odm.dev/)
[![License](https://img.shields.io/badge/license-MIT-009485?style=flat-square)](./LICENSE)

[**Docs**](https://mundobien2025.github.io/fastapi-basekit) ·
[**PyPI**](https://pypi.org/project/fastapi-basekit/) ·
[**Issues**](https://github.com/mundobien2025/fastapi-basekit/issues) ·
[**Changelog**](./CHANGELOG.md)

</div>

---

## Quickstart

```bash
pip install fastapi-basekit[init]
basekit init                                    # cookiecutter prompts
cd <project_slug>
cp .env.example .env
make up-d
make migrate-create && make migrate-up
make seed
```

Abre http://localhost:8000/docs. Login con `admin@example.com` / `ChangeMe2026!`.

## ¿Qué incluye?

- **Repository / Service / Controller** base async para SQLAlchemy 2.0, SQLModel y Beanie
- **Paginación, filtrado, búsqueda, ordenamiento** vía query string out-of-the-box
- **JWT middleware** + `BasePermission` classes + soft-delete
- **`basekit init`** — scaffolder cookiecutter (multi-ORM, multi-DB, redis, s3, license)
- **Plugin Claude Code** — la skill `fastapi-basekit-crud` enseña el patrón a Claude

## Documentación

**[mundobien2025.github.io/fastapi-basekit](https://mundobien2025.github.io/fastapi-basekit)**

| Sección | Contenido |
|---|---|
| [Primeros pasos](https://mundobien2025.github.io/fastapi-basekit/getting-started/installation) | Instalación, `basekit init`, primer CRUD |
| [Guía de usuario](https://mundobien2025.github.io/fastapi-basekit/user-guide/controllers) | Controllers, services, repositories, paginación, filtros |
| [Avanzado](https://mundobien2025.github.io/fastapi-basekit/advanced/permissions) | Permisos, soft-delete, logging, performance |
| [Referencia API](https://mundobien2025.github.io/fastapi-basekit/api-reference/base-controller) | Docstrings de `BaseController`, `BaseService`, `BaseRepository`, `Schemas` |
| [Ejemplos](https://mundobien2025.github.io/fastapi-basekit/examples/basic-crud) | CRUD básico, filtros complejos, relaciones, auth |

## Como plugin de Claude Code

Dentro de Claude Code (terminal) corre:

```bash
/plugin marketplace add mundobien2025/fastapi-basekit
/plugin install fastapi-basekit@fastapi-basekit
/plugin list                                       # verifica instalación
```

Eso registra el marketplace `fastapi-basekit` desde el repo de GitHub e
instala el plugin (que incluye la skill `fastapi-basekit-crud`). Luego
pide: *"Crea el recurso `Invoice` con CRUD completo siguiendo
fastapi-basekit"* — Claude detecta la skill y aplica el patrón canónico
(model → repo → service → schema → controller con `@cbv`).

Para actualizar a una versión nueva:

```bash
/plugin update fastapi-basekit@fastapi-basekit
```

## Instalación por ORM

```bash
pip install fastapi-basekit[sqlalchemy]   # Postgres / MySQL / SQLite
pip install fastapi-basekit[beanie]       # MongoDB
pip install fastapi-basekit[sqlmodel]
pip install fastapi-basekit[init]         # solo scaffolder
pip install fastapi-basekit[all]          # todo
```

## Contribuir

PRs bienvenidos. Setup local en [docs/contributing](https://mundobien2025.github.io/fastapi-basekit/contributing).

## Licencia

[MIT](./LICENSE) — © Jerson Moreno
