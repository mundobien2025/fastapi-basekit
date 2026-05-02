# Guía de contribución

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

### Correr la suite

```bash
pytest tests/                                           # 134 tests (~3s)
pytest tests/ -v -k "test_repository"                   # filtrar por patrón
pytest tests/ --cov=fastapi_basekit --cov-report=html   # cobertura HTML en htmlcov/
pytest tests/test_beanie_aggregation_hooks.py           # un solo archivo
pytest tests/ -x                                        # parar al primer fail
```

Configuración en `pytest.ini`: `asyncio_mode = auto` (no hace falta
decorar cada test async con `@pytest.mark.asyncio`).

### Cobertura por ORM

| ORM | Archivo | Estilo |
|-----|---------|--------|
| Beanie | `test_crud_beanie_controller.py` | Integración con `mongomock-motor` (in-memory) |
| Beanie | `test_beanie_aggregation_hooks.py` | Unit con mocks (`AsyncMock`, `patch`) |
| Beanie | `test_beanie_aggregation_integration.py` | Pipeline shapes vs raw pymongo collection |
| Beanie | `test_base_service.py` | Unit con `FakeRepository` |
| SQLAlchemy | `test_crud_controller.py` | Integración con SQLite-in-memory |
| SQLAlchemy | `test_sql_queryset_override.py` | `build_list_queryset` overrides reales |
| SQLModel | `test_crud_sqlmodel_repository_service.py` | SQLite-in-memory + `SQLModelAsyncSession` |
| SQLModel | `test_sql_queryset_override.py` (mismo archivo) | Mirror de SQLAlchemy patterns |

### Cómo escribir tests nuevos

#### SQL (SQLAlchemy / SQLModel) — SQLite-in-memory

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def async_engine():
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def async_session(async_engine):
    maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
```

`StaticPool` es obligatorio — sin él, cada conexión abre una BD distinta
(SQLite `:memory:` no comparte estado entre conexiones).

Para SQLModel, swap `AsyncSession` por
`sqlmodel.ext.asyncio.session.AsyncSession` y `Base.metadata` por
`SQLModel.metadata`.

#### Beanie — mongomock-motor

```python
import mongomock_motor
import pytest
from beanie import init_beanie

@pytest.fixture
async def mongo_client():
    client = mongomock_motor.AsyncMongoMockClient()
    yield client
    client.close()

@pytest.fixture
async def db(mongo_client):
    await init_beanie(database=mongo_client.test_db, document_models=[MyDoc])
    yield
    await MyDoc.get_pymongo_collection().drop()
```

⚠️ **Caveat conocido**: Beanie 2.x + mongomock-motor tienen incompatibilidad
con `Doc.aggregate(...).to_list()` — el cursor `AsyncIOMotorLatentCommandCursor`
no es awaitable. Workaround para tests de pipelines: ejecutar vía
`Doc.get_pymongo_collection().aggregate(pipeline).to_list(None)`. Ver
`test_beanie_aggregation_integration.py` para el patrón.

#### Override de hooks (`build_list_queryset` / `build_list_pipeline`)

Cubrir overrides con BD real, no mocks. Verifica que la query/pipeline
emitida produce los rows esperados:

```python
class PostRepoSoftDelete(BaseRepository):
    model = Post

    def build_list_queryset(self, **kwargs):
        return select(Post).where(Post.deleted_at.is_(None))

@pytest.mark.asyncio
async def test_soft_delete_hides_deleted(sql_session, seeded_posts):
    repo = PostRepoSoftDelete(db=sql_session)
    rows, total = await repo.list_paginated(page=1, count=50)
    assert total == 4  # 5 seeded - 1 deleted
    assert all(r.deleted_at is None for r in rows)
```

#### Unit tests con mocks

Cuando la lógica es puramente algorítmica (shape de pipeline, dispatch,
flags), evita la BD y usa `unittest.mock`:

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_paginate_pipeline_appends_facet():
    repo = FakeRepo()
    agg_chain = MagicMock()
    agg_chain.to_list = AsyncMock(
        return_value=[{"metadata": [{"total": 0}], "data": []}]
    )
    with patch.object(FakeModel, "aggregate", return_value=agg_chain) as mock_agg:
        await repo.paginate_pipeline([], page=1, count=10)
    pipeline = mock_agg.call_args[0][0]
    assert "$facet" in pipeline[-1]
```

#### Estructura recomendada

```python
class TestSomething:
    """Tests del comportamiento X."""

    @pytest.mark.asyncio
    async def test_happy_path(self, fixture):
        ...

    @pytest.mark.asyncio
    async def test_edge_case(self, fixture):
        ...
```

- Una clase `TestX` por unidad lógica.
- Nombres `test_<verb>_<expectation>`.
- Docstring corta describiendo el comportamiento bajo test.

#### Reglas hard

| Regla | Por qué |
|-------|---------|
| Tests `feat:` y `fix:` son **obligatorios** | Bug regression sin test = bug que vuelve |
| BD real (SQLite/mongomock) > mocks | Mocks pasan tests pero esconden bugs reales (ver `test_validate_true_skips_unvalidatable_rows` para el motivo) |
| `StaticPool` para SQLite-in-memory async | Sin él, cada connection abre BD nueva |
| Una assertion por concept | Tests legibles fallan en una línea, no en un mar de `assert` |
| Fixtures async con `yield`, cleanup después | Recursos liberados aunque el test falle |
| Tests que escriben en BD usan fixture aislado por test | Sin shared state entre tests |
| Mockear solo lo externo (HTTP, LLMs, S3) | Mockear código propio = test acoplado al impl |

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
