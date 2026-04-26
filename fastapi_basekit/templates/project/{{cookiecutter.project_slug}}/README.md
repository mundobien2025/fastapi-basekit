# {{ cookiecutter.project_name }}

{{ cookiecutter.description }}

Built with [fastapi-basekit](https://github.com/mundobien2025/fastapi-basekit) — async CBV pattern, repositories + services + controllers, JWT middleware, soft delete.

## Stack

- **Python** {{ cookiecutter.python_version }}
- **ORM** {{ cookiecutter.orm }}
- **Database** {{ cookiecutter.database }}
- **Server** {{ cookiecutter.server }}
{% if cookiecutter.cache == "redis" %}- **Cache** Redis{% endif %}
{% if cookiecutter.background_tasks == "arq" %}- **Background tasks** ARQ{% endif %}
{% if cookiecutter.bucket == "s3" %}- **Object storage** S3{% endif %}
{% if cookiecutter.include_alembic == "yes" and cookiecutter.orm != "beanie" %}- **Migrations** Alembic{% endif %}

## Quickstart

```bash
cp .env.example .env
{% if cookiecutter.include_docker == "yes" %}make up-d
{% if cookiecutter.orm != "beanie" and cookiecutter.include_alembic == "yes" %}make migrate-create   # answer: baseline
make migrate-up
{% endif %}make seed
{% else %}pip install -r requirements.txt
uvicorn app.main:app --reload
{% endif %}```

Open http://localhost:8000/docs

## Default admin

```
{{ "${ADMIN_EMAIL}" }}   (default: admin@example.com)
{{ "${ADMIN_PASSWORD}" }} (default: ChangeMe2026!)
```

## License

{{ cookiecutter.license }}
