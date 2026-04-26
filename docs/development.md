# Desarrollo

## Probar el cookiecutter localmente

```bash
pip install -e .[init]
mkdir /tmp/test_scaffold && cd /tmp/test_scaffold
basekit init --no-input \
  --extra-context project_name="TestApi" \
  --extra-context orm=sqlalchemy \
  --extra-context database=postgres
cd testapi
cp .env.example .env
docker compose up --build
```

## Probar la skill (Claude Code)

```bash
/plugin marketplace add /ruta/local/al/repo
/plugin install fastapi-basekit
/plugin list
```

Luego pide: *"Usa la skill `fastapi-basekit-crud` para crear el recurso Foo con CRUD completo."*

## Modificar templates

Templates están en `fastapi_basekit/templates/project/`. Variables vía Jinja: `{{ cookiecutter.X }}`.

!!! warning "Whitespace control en Jinja"
    Usa `{%- if %}` (con dash) para chomp newline previo, NUNCA `{%- if -%}` ni `{%- else -%}` antes de líneas indentadas — strippea la indentación y rompe el código Python generado.

```jinja
class Foo:
{%- if condition %}
    field: int                 # ← indent preservado
{%- else %}
    field: str
{%- endif %}
```

## Hooks

`hooks/pre_gen_project.py` — valida inputs antes de generar.
`hooks/post_gen_project.py` — limpia archivos no usados (alembic si beanie, docker si opt-out).

## Build docs

```bash
pip install -e .[docs]
mkdocs serve            # http://localhost:8001
mkdocs build            # site/ estático
mkdocs gh-deploy        # publica a GitHub Pages
```

## Versionado de docs (mike)

```bash
pip install mike
mike deploy --push --update-aliases 0.3 latest
mike set-default --push latest
```

## CI/CD

`.github/workflows/`:
- `tests.yml` — pytest + lint en PR
- `docs.yml` — push a main con cambios de docs → deploy alias `dev` (preview)
- `release.yml` — tag `v*` push → PyPI + docs versionadas (mike alias `X.Y` + `latest`). Manual dispatch permite togglear `pypi` y `deploy_docs` independientes.

## Release flow

Tres caminos según qué publicar:

### Release completo (PyPI + docs) — un solo comando

```bash
make release V=0.3.0          # explícito
make release BUMP=patch       # 0.2.1 → 0.2.2
make release BUMP=minor       # 0.2.1 → 0.3.0
make release BUMP=major       # 0.2.1 → 1.0.0
make release-dry V=0.3.0      # preview sin escribir
```

`scripts/release.py` orchesta:

1. Valida semver + working tree limpio + tag no existe
2. Bumpea version en `pyproject.toml`, `plugin.json`, `marketplace.json`
3. Prepend stub a `CHANGELOG.md`
4. Commit `chore: release vX.Y.Z`
5. Tag anotado `vX.Y.Z`
6. Push branch + tag (`--follow-tags`)
7. Imprime URLs para monitorear

Tag `v*` dispara `release.yml` en GitHub Actions:

- Build wheel + sdist
- Publica PyPI (OIDC trusted publishing)
- `mike deploy 0.3 latest` → docs versionadas + alias `latest`
- `mike set-default latest` → root URL apunta a último

`release.yml` corre en cada `v*` tag:
1. Build wheel + sdist
2. Publica PyPI (OIDC trusted publishing)
3. `mike deploy 0.3 latest` → docs versionadas + alias `latest`
4. `mike set-default latest` → URL raíz redirige a último

URLs resultantes:

| URL | Apunta a |
|---|---|
| `https://mundobien2025.github.io/fastapi-basekit/` | última (`latest` alias) |
| `https://mundobien2025.github.io/fastapi-basekit/0.3/` | pin a esa versión |
| `https://mundobien2025.github.io/fastapi-basekit/dev/` | preview de main |

### PyPI sin tocar docs

```bash
make release-no-docs V=0.3.0
```

Bumpea + commit + push (sin tag) + dispatcha `release.yml` con `pypi=true deploy_docs=false`. Útil para patches internos que no cambian docs.

### Docs sin tocar PyPI

```bash
make release-docs-only V=0.3.0
```

Bumpea + commit + push + dispatcha con `pypi=false deploy_docs=true`. Útil para fixes de typos / mejoras de docs sin nueva versión paquete.

### Auto-preview de main (`dev` alias)

`docs.yml` corre en cada push a `main` que toque `docs/`, `mkdocs.yml`, `fastapi_basekit/`. Despliega `dev` sin tocar `latest`. URL: `mundobien2025.github.io/fastapi-basekit/dev/`.

### Bootstrap inicial (una sola vez)

```bash
# 1. Crea gh-pages + primer deploy versionado local
make docs-deploy-version

# 2. GitHub repo → Settings → Pages → Source: gh-pages branch / (root)
# 3. GitHub repo → Settings → Actions → General → Workflow permissions: Read and write
# 4. Configura PyPI Trusted Publishing:
#    - PyPI → Account → Publishing → Add pending publisher
#    - Owner: mundobien2025
#    - Repo: fastapi-basekit
#    - Workflow: release.yml
#    - Environment: pypi
```

Después: `make release` y todo automático.

### Versionado de docs (mike)

```bash
mike list                        # versiones publicadas
mike delete 0.1                  # remueve vieja
mike alias 0.3 stable            # alias custom
mike set-default latest          # cambia URL raíz
```

## Debug del CLI

```bash
python -m fastapi_basekit.cli init --no-input --extra-context project_name=Debug
```

## Probar templates en CI

`.github/workflows/template-smoke.yml`:
```yaml
- run: |
    pip install -e .[init]
    cd /tmp
    basekit init --no-input --extra-context project_name=CI --extra-context orm=sqlalchemy --extra-context database=postgres
    cd ci
    docker compose up -d --build
    sleep 10
    curl -f http://localhost:8000/health
```
