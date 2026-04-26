"""Validate cookiecutter inputs before scaffolding."""

import re
import sys

slug = "{{ cookiecutter.project_slug }}"
orm = "{{ cookiecutter.orm }}"
db = "{{ cookiecutter.database }}"

# 1. Slug must be a valid Python identifier
if not re.match(r"^[a-z][a-z0-9_]*$", slug):
    print(
        f"ERROR: project_slug '{slug}' is invalid. "
        "Must start with a lowercase letter and contain only [a-z0-9_].",
        file=sys.stderr,
    )
    sys.exit(1)

# 2. ORM ↔ database compatibility
if orm == "beanie" and db != "mongodb":
    print(
        f"ERROR: orm=beanie requires database=mongodb (got '{db}').",
        file=sys.stderr,
    )
    sys.exit(1)

if orm in ("sqlalchemy", "sqlmodel") and db == "mongodb":
    print(
        f"ERROR: orm={orm} requires a SQL database (postgres/mariadb/sqlite), got '{db}'.",
        file=sys.stderr,
    )
    sys.exit(1)
