---
hide:
  - navigation
  - toc
---

<div class="bk-hero" markdown>

<img class="bk-hero-logo" src="assets/logo-mark.svg" alt="fastapi-basekit" width="96">

# fastapi-basekit

<p class="bk-tagline">
Construye APIs FastAPI listas para producción en minutos —
repos, services, controllers, paginación, JWT y migrations
ya resueltos. Multi-ORM (SQLAlchemy · SQLModel · Beanie).
</p>

<div class="bk-actions" markdown>
[:material-rocket-launch-outline: Empezar](getting-started/installation.md){ .md-button .md-button--primary }
[:material-github: GitHub](https://github.com/mundobien2025/fastapi-basekit){ .md-button }
[:material-package-variant: PyPI](https://pypi.org/project/fastapi-basekit/){ .md-button }
</div>

<p class="bk-badges">
  <img src="https://img.shields.io/pypi/v/fastapi-basekit?style=flat-square&color=009485&logo=pypi&logoColor=white" alt="PyPI">
  <img src="https://img.shields.io/badge/python-3.11+-2c5282?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLAlchemy-2.0-c41616?style=flat-square" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/MongoDB-Beanie-47A248?style=flat-square&logo=mongodb&logoColor=white" alt="Beanie">
  <img src="https://img.shields.io/badge/license-MIT-009485?style=flat-square" alt="License">
</p>

</div>

## ¿Por qué `fastapi-basekit`?

Cada proyecto FastAPI repite lo mismo: paginación, filtros, búsqueda, soft delete, JWT middleware, exception handlers, alembic env. **basekit lo trae resuelto** en clases base que extiendes.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } &nbsp; **Inicio en minutos**

    ---

    `basekit init` genera proyecto completo: `app/`, alembic, docker-compose, Makefile, JWT, seed admin. Listo en 1 comando.

    [:octicons-arrow-right-24: Primeros pasos](getting-started/installation.md)

-   :material-database-cog:{ .lg .middle } &nbsp; **Multi-ORM**

    ---

    SQLAlchemy 2.0 async, SQLModel y Beanie (MongoDB) con la misma API: `Repository` + `Service` + `Controller`.

    [:octicons-arrow-right-24: Repositories](user-guide/repositories.md)

-   :material-shield-key:{ .lg .middle } &nbsp; **Auth incluido**

    ---

    JWT middleware, `BasePermission` classes async, `request.state.user` resuelto una vez por request.

    [:octicons-arrow-right-24: Permisos](advanced/permissions.md)

-   :material-magnify:{ .lg .middle } &nbsp; **Filtros + paginación**

    ---

    `?page=1&count=10&search=foo&order_by=-created_at` listo en cada controller, sin escribir SQL.

    [:octicons-arrow-right-24: Paginación](user-guide/pagination.md)

-   :material-shape-plus:{ .lg .middle } &nbsp; **Convenciones probadas**

    ---

    Patrón usado en producción en `axion_accounter`, `pulbot`, `fluxio`, `swapdealer`. Battle-tested.

    [:octicons-arrow-right-24: Convenciones](user-guide/controllers.md)

-   :material-robot-happy:{ .lg .middle } &nbsp; **Plugin Claude Code**

    ---

    La skill `fastapi-basekit-crud` enseña el patrón a Claude para que scaffolde recursos automáticamente.

    [:octicons-arrow-right-24: Instalar plugin](getting-started/installation.md#como-plugin-de-claude-code)

</div>

## Quickstart

```bash
pip install fastapi-basekit[init]
basekit init                    # cookiecutter prompts
cd <project_slug>
cp .env.example .env
make up-d
make migrate-create && make migrate-up
make seed
```

Visita [http://localhost:8000/docs](http://localhost:8000/docs) y entra con `admin@example.com` / `ChangeMe2026!`.

## Arquitectura

```mermaid
flowchart LR
    R[Request] --> M[AuthenticationMiddleware]
    M --> C[@cbv Controller]
    C --> S[BaseService]
    S --> Repo[BaseRepository]
    Repo --> DB[(Database)]
    DB -.-> Repo
    Repo -.-> S
    S -.-> C
    C --> F[format_response]
    F --> Resp[BaseResponse]
    style C fill:#009485,color:#fff
    style S fill:#00b89c,color:#fff
    style Repo fill:#00d4b8,color:#003a35
```

| Capa | Responsabilidad | Hooks útiles |
|---|---|---|
| **Controller** | Validar params, permisos, schema response | `get_schema_class()`, `check_permissions()` |
| **Service** | Lógica de negocio, scoping | `get_filters()`, `get_kwargs_query()` |
| **Repository** | Queries, soft-delete filter | `build_list_queryset()` |

[:octicons-arrow-right-24: Conoce el patrón completo](user-guide/controllers.md){ .md-button .md-button--primary }
[:octicons-arrow-right-24: CRUD básico paso a paso](examples/basic-crud.md){ .md-button }
