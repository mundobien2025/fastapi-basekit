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

{% if cookiecutter.include_docker == "yes" -%}
Set unique values for `JWT_SECRET` and `ADMIN_PASSWORD` in `.env` before starting
the containers. The example values are placeholders.

{% endif -%}
```bash
cp .env.example .env
{% if cookiecutter.include_docker == "yes" %}make up-d
{% if cookiecutter.orm != "beanie" and cookiecutter.include_alembic == "yes" %}make migrate-create   # answer: baseline
make migrate-up
{% endif %}make seed
{% else %}python -m pip install -r requirements.txt
{% if cookiecutter.orm != "beanie" and cookiecutter.include_alembic == "yes" %}make migrate-create   # answer: baseline
make migrate-up
{% endif %}export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export ADMIN_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"
python -m app.scripts.init
python -m uvicorn app.main:app --reload
{% endif %}```

Open http://localhost:8000/docs

## Admin account

```
{{ "${ADMIN_EMAIL}" }}   (default: admin@example.com)
{{ "${ADMIN_PASSWORD}" }} (default: ChangeMe2026!)
```

## License

{{ cookiecutter.license }}
