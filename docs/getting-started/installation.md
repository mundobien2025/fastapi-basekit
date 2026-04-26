# Instalación

## Como librería Python

=== "SQLAlchemy (Postgres / MySQL / SQLite)"

    ```bash
    pip install fastapi-basekit[sqlalchemy]
    ```

=== "Beanie (MongoDB)"

    ```bash
    pip install fastapi-basekit[beanie]
    ```

=== "SQLModel"

    ```bash
    pip install fastapi-basekit[sqlmodel]
    ```

=== "Scaffolder (`basekit init`)"

    ```bash
    pip install fastapi-basekit[init]
    ```

=== "Todo"

    ```bash
    pip install fastapi-basekit[all]
    ```

## Generar proyecto nuevo — `basekit init`

```bash
pip install fastapi-basekit[init]
basekit init
```

El scaffolder lanza prompts cookiecutter:

| Prompt | Valores |
|---|---|
| `project_name` | string libre |
| `orm` | `sqlalchemy` · `beanie` |
| `database` | `postgres` · `mariadb` · `sqlite` · `mongodb` |
| `server` | `uvicorn` · `gunicorn` |
| `cache` | `none` · `redis` |
| `background_tasks` | `none` · `arq` |
| `bucket` | `none` · `s3` |
| `include_alembic` | `yes` · `no` |
| `include_docker` | `yes` · `no` |
| `license` | `MIT` · `Apache-2.0` · `GPL-3.0` · `Proprietary` |

!!! tip "Validaciones"
    `orm=beanie` exige `database=mongodb`. `orm=sqlalchemy` exige BD SQL. El hook `pre_gen_project.py` te bloquea si la combinación es inválida.

### Modo no interactivo

```bash
basekit init --no-input \
  --extra-context project_name="My Service" \
  --extra-context orm=sqlalchemy \
  --extra-context database=postgres \
  --extra-context cache=redis \
  --extra-context bucket=s3 \
  --extra-context license=MIT
```

### Boot del proyecto generado

```bash
cd <project_slug>
cp .env.example .env
make up-d
make migrate-create        # autogenera baseline alembic (si SQL)
make migrate-up
make seed                  # crea admin@example.com / ChangeMe2026!
```

Abre [http://localhost:8000/docs](http://localhost:8000/docs).

## Como plugin de Claude Code

Si usas Claude Code, instala el plugin para que la skill `fastapi-basekit-crud` se active automáticamente al crear recursos CRUD:

```bash
/plugin marketplace add https://github.com/mundobien2025/fastapi-basekit
/plugin install fastapi-basekit
/plugin list
```

[:octicons-arrow-right-24: Configuración](configuration.md){ .md-button .md-button--primary }
