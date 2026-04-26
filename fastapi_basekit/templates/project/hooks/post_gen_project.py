"""Cleanup files that aren't needed for the chosen options."""

import os
import shutil
from pathlib import Path

ORM = "{{ cookiecutter.orm }}"
DB = "{{ cookiecutter.database }}"
INCLUDE_ALEMBIC = "{{ cookiecutter.include_alembic }}" == "yes"
INCLUDE_DOCKER = "{{ cookiecutter.include_docker }}" == "yes"
CACHE = "{{ cookiecutter.cache }}"
BUCKET = "{{ cookiecutter.bucket }}"

PROJECT_DIR = Path(os.getcwd())


def rm(path: str) -> None:
    p = PROJECT_DIR / path
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    elif p.exists():
        p.unlink()


# 1. Beanie projects don't use alembic
if ORM == "beanie" or not INCLUDE_ALEMBIC:
    rm("alembic")
    rm("alembic.ini")

# 2. Docker is opt-out
if not INCLUDE_DOCKER:
    rm("docker-compose.yml")
    rm("Dockerfile")

# 3. Print next steps
print(
    f"\n✓ Project scaffolded at {PROJECT_DIR}\n"
    f"  ORM      : {ORM}\n"
    f"  Database : {DB}\n"
    f"  Cache    : {CACHE}\n"
    f"  Bucket   : {BUCKET}\n"
    f"  Alembic  : {'yes' if INCLUDE_ALEMBIC and ORM != 'beanie' else 'no'}\n"
    f"  Docker   : {'yes' if INCLUDE_DOCKER else 'no'}\n"
    f"\nNext steps:\n"
    f"  cd {PROJECT_DIR.name}\n"
    f"  cp .env.example .env       # edit values\n"
    + ("  make up                    # start containers\n" if INCLUDE_DOCKER else "  pip install -r requirements.txt\n  uvicorn app.main:app --reload\n")
    + (f"  make migrate-create        # generate baseline alembic\n  make migrate-up\n" if ORM != 'beanie' and INCLUDE_ALEMBIC else "")
    + f"  make seed                  # seed admin user\n"
    f"\nVisit http://localhost:8000/docs\n"
)
