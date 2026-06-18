---
name: fastapi-basekit-docker-layout
description: >
  Scaffold the three-env Docker layout (local / dev / prod + db) for a
  fastapi-basekit project, including per-env Dockerfiles, compose files,
  entrypoints, and the `ENV=...`-driven Makefile. Use proactively when:
  setting up Docker for a new fastapi-basekit app, asked to "add Docker",
  "dockerize", "set up local/dev/prod stacks", "wire docker-compose",
  "add Makefile for docker", or when the project has `app/` and `requirements.txt`
  but no `docker/` directory. Also trigger when migrating an existing single
  `docker-compose.yml` to the three-env split, or when prepping a project
  for EC2 + RDS deploy.
tools: Read, Edit, Write, Bash, Glob, Grep
---

# fastapi-basekit — Docker multi-env layout (local / dev / prod + db)

**Source of truth project:** `eventsvileads_backend/` (vileads_events_backend).

This skill codifies the exact Docker layout that ships there. It is **not**
a generic "add Dockerfile" skill — it imposes the three-environment split
(`local` ≠ `dev` ≠ `prod`), the per-env entrypoint differences, the Makefile
contract, and the CI/CD deploy invocation. Copy the templates verbatim and
only deviate with explicit reason (see §9).

---

## Core rule — three envs, not two

| Env | Source mount | DB | Reload | DEBUG | Workers | Debug port |
|-----|--------------|------------------------------|--------|---------------|---------|------------|
| dev | no           | container postgres           | yes    | env-driven    | 1       | none       |
| local | yes (live edit) | container postgres        | yes    | toggle by env | 1       | debugpy:5680 |
| prod | no (immutable) | RDS external via DATABASE_URL | no    | no            | 2       | none       |

- **`local`** is the developer's machine: live source mount, uvicorn `--reload`,
  optional debugpy, adminer sidecar, tests profile.
- **`dev`** is a shared remote environment (staging-like): no source mount, no
  debugpy, no adminer; code is the build snapshot. Rebuild to roll new code.
- **`prod`** is what runs on EC2: immutable image, non-root user, build deps
  purged after `pip install`, 2 uvicorn workers, `--proxy-headers`, RDS via
  `DATABASE_URL` (no `db` service in compose).

If you find yourself collapsing `local` and `dev` into one compose file:
**STOP.** They have fundamentally different runtime characteristics (volumes,
debugpy, adminer, tests profile) and merging them re-introduces the "works on
my machine vs shared dev" ambiguity this layout exists to eliminate.

---

## Layout — the directory tree is part of the contract

```
docker/
  db/Dockerfile.postgres                  base postgres:16-alpine, slot for init SQL
  dev/
    Dockerfile.dev                        Python + deps, --reload, no volume
    docker-compose.dev.yml                api + db (shared env)
  local/
    Dockerfile.local                      Python + deps + debugpy
    Dockerfile.test                       pytest runner image
    entrypoint.sh                         alembic upgrade + init.py + uvicorn (debugpy)
    entrypoint.test.sh                    pytest invoker
    docker-compose.local.yml              api + db + adminer + tests profile, volumes mounted
  prod/
    Dockerfile.prod                       non-root, build deps purged, uvicorn workers 2
    entrypoint.sh                         alembic + init.py + uvicorn --proxy-headers
    docker-compose.prod.yml               api on 80:8000; DB = RDS external via .env
Makefile                                  ENV=local|dev|prod target dispatcher
```

The Makefile resolves `docker/$(ENV)/docker-compose.$(ENV).yml` by convention —
the directory names and file names matter. Don't rename them.

---

## Design decisions you MUST preserve

1. **3 envs, not 2.** `dev` ≠ `local`. `local` = developer machine (live reload,
   debugpy, adminer, tests profile). `dev` = shared env (no volumes, no debugpy,
   no adminer). `prod` = EC2 with RDS external.
2. **DB in compose only for `local` + `dev`.** In prod, `DATABASE_URL` points
   to managed RDS; there is **no `db` service** in `docker-compose.prod.yml`.
3. **Entrypoint differs per env.** `local/entrypoint.sh` toggles debugpy via
   `if [ "$DEBUG" = "true" ]`. `prod/entrypoint.sh` runs uvicorn with
   `--workers 2 --proxy-headers --forwarded-allow-ips '*'` so it sees the
   `X-Forwarded-For` from the proxy.
4. **Non-root user in prod.** `Dockerfile.prod` creates `useradd -m -u 1000 <user>`
   and `USER <user>`. Build deps (`build-essential`) are purged after `pip install`
   to shrink the image.
5. **Port 80 mapped to 8000 internal.** Compose prod uses `ports: ["80:8000"]` —
   the host binds 80 (privileged), the container listens on 8000 (no root needed).
   Cloudflare proxy reaches the EC2 EIP on 80.
6. **Cloudflare SSL = Flexible at start.** For Full(strict), add an nginx sidecar
   with a Cloudflare Origin Certificate. Document this in the prod compose
   comments so the next operator knows the path forward.
7. **Tests profile in local compose.** The `tests:` service has
   `profiles: ["tests"]` — it only spins up via `make test-local` or
   `docker compose --profile tests run --rm tests`.

---

## Environment variables that drive behavior

| Var | Role |
|-----|------|
| `DEBUG` | In local, toggles debugpy listener on `:5680`. |
| `DATABASE_URL` | In prod points to RDS; in local/dev points to the compose `db`. |
| `RUNNING_IN_DOCKER` | Set by compose; `settings.py` uses it to skip `.env` file load. |
| `RUNNING_TESTS` | Set in the `tests` container; forces SQLite via `conftest`. |
| `TRUSTED_PROXY_COUNT` | Prod = 1 (Cloudflare in front). |

---

## CI/CD interaction — prod compose is invoked by CI, not by hand

The GitHub Actions workflow (`.github/workflows/ci.yml`) deploy step SSHes
into the EC2 (typically via SSM) and runs:

```bash
COMPOSE="docker compose -f docker/prod/docker-compose.prod.yml"
$COMPOSE pull || true
$COMPOSE build
$COMPOSE up -d
$COMPOSE ps
```

That is the contract: **the operator does not `make ENV=prod up` from their
laptop**. Prod compose is the CI's responsibility on the EC2 host. The
Makefile prod targets exist so the operator can debug on the EC2 directly
(`make ENV=prod logs`, `make ENV=prod ps`, `make ENV=prod shell`), not so
they can deploy.

---

## 0. Before writing anything — read first

```bash
ls app/                                   # confirm fastapi-basekit project layout
ls docker/ 2>/dev/null                    # confirm no prior docker/ tree
test -f requirements.txt && echo OK       # required by Dockerfiles
test -f alembic.ini && echo OK            # entrypoints call `alembic upgrade head`
grep -n "^def init\|^if __name__" app/scripts/init.py 2>/dev/null  # entrypoints call this
```

If `app/scripts/init.py` doesn't exist, the entrypoints' `python -m app.scripts.init`
will fail. Either create it (idempotent seed runner) or strip that line from
the entrypoints — but document the deviation.

If `alembic` is not configured yet, wire it before this skill. Migrations are
the first thing both entrypoints run.

---

## 1. `docker/db/Dockerfile.postgres` — verbatim

```dockerfile
FROM postgres:16-alpine

# Placeholder para extender la imagen base de PostgreSQL (init scripts SQL,
# extensiones, etc.). Hoy se usa tal cual; scripts de Python (init_admin,
# init_terms) corren en el entrypoint del API, no aqui.
#
# Para inyectar SQL de inicializacion, copiar a /docker-entrypoint-initdb.d/:
# COPY docker/db/init/*.sql /docker-entrypoint-initdb.d/
```

The image exists as its own Dockerfile (not raw `image: postgres:16-alpine`
in compose) so future SQL init scripts have an obvious home. Don't inline it.

---

## 2. `docker/dev/Dockerfile.dev` — verbatim

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Build deps + curl (debug + healthchecks).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Modo dev compartido (no es la maquina del developer — eso es local/).
# Sin mount de volumen: el codigo es el snapshot del build. Para cambios, rebuild.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

Why `--reload` in dev when there's no volume mount: hot reload is cheap and
helps when shelling in to patch a file for a quick repro. The canonical path
is still rebuild.

---

## 3. `docker/dev/docker-compose.dev.yml` — verbatim (rename project name)

Replace `vileads` with your project name in service names, container names,
DB user/pass/db, secret key, and base domain. Otherwise verbatim:

```yaml
services:
  api:
    build:
      context: ../..
      dockerfile: docker/dev/Dockerfile.dev
    container_name: vileads-api-dev
    ports:
      - "8001:8000"
    environment:
      ENVIRONMENT: dev
      DEBUG: "true"
      DATABASE_URL: postgresql+asyncpg://vileads:vileads@db:5432/vileads
      SECRET_KEY: dev-secret-do-not-use-in-prod-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
      APP_BASE_DOMAIN: vileadsevents.local
      APP_BASE_URL: http://api.vileadsevents.local:8001
      ALLOWED_ORIGINS: http://localhost:3000,http://localhost:5173
    depends_on:
      db:
        condition: service_healthy
    networks:
      - vileads-network

  db:
    build:
      context: ../..
      dockerfile: docker/db/Dockerfile.postgres
    container_name: vileads-db-dev
    environment:
      POSTGRES_DB: vileads
      POSTGRES_USER: vileads
      POSTGRES_PASSWORD: vileads
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vileads"]
      interval: 5s
      timeout: 5s
      retries: 30
    networks:
      - vileads-network

networks:
  vileads-network:
    driver: bridge

volumes:
  db_data:
```

Notes:

- Port `8001` (not `8000`) so a dev compose can run on the same host as a
  local compose without collision.
- `SECRET_KEY` is a fake constant — that is intentional. `dev` is shared, not
  trusted. Production secrets live only in the prod `.env`.
- `depends_on.db.condition: service_healthy` + the `pg_isready` healthcheck
  is the only correct way to gate API startup on Postgres being live.

---

## 4. `docker/local/Dockerfile.local` — verbatim

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Build deps + curl + git (utiles para debug local).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir debugpy

COPY . .

# 8000 = uvicorn  |  5680 = debugpy (cuando DEBUG=true)
EXPOSE 8000 5680

COPY --chmod=755 docker/local/entrypoint.sh /backend/entrypoint.sh

CMD ["/backend/entrypoint.sh"]
```

`git` is included for local-only debugging (e.g. `git diff` inside a running
container while reproducing a bug). It's stripped from prod.

---

## 5. `docker/local/Dockerfile.test` — verbatim

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

COPY --chmod=755 docker/local/entrypoint.test.sh /backend/entrypoint.test.sh

# RUNNING_TESTS=true fuerza el conftest a usar SQLite en memoria/local.
ENV RUNNING_TESTS=true

CMD ["/backend/entrypoint.test.sh"]
```

Separate test image (not `Dockerfile.local` + override) so the test profile
boots without the debugpy install and without `git`. Faster, smaller, and
isolates test deps if you ever add `pytest-xdist` etc.

---

## 6. `docker/local/entrypoint.sh` — verbatim

```sh
#!/bin/sh
set -e

echo "DATABASE_URL=$DATABASE_URL"

# Espera implicita: depends_on con condition: service_healthy en compose ya
# garantiza que postgres responde antes de arrancar el API.

echo "Aplicando migraciones (alembic upgrade head)..."
alembic upgrade head

echo "Seed: init admin + terms..."
python -m app.scripts.init || echo "(init.py fallo o ya estaba seeded — sigo)"

if [ "$DEBUG" = "true" ] || [ "$DEBUG" = "True" ]; then
    echo "API en modo DEBUG (debugpy en :5680, uvicorn --reload)..."
    exec python -m debugpy --listen 0.0.0.0:5680 \
        -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
        --limit-max-requests 1000 --limit-concurrency 1000
else
    echo "API en modo normal local (uvicorn --reload, sin debugpy)..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
        --limit-max-requests 1000 --limit-concurrency 1000
fi
```

Why `|| echo` on `python -m app.scripts.init`: re-running `init` after the
first boot is a no-op (idempotent seed), so a non-zero exit on "already
seeded" must not crash the container. Logged + swallowed.

The `[ "$DEBUG" = "true" ] || [ "$DEBUG" = "True" ]` toggle exists because
`.env` files quote case-inconsistently across team members. Accept both.

---

## 7. `docker/local/entrypoint.test.sh` — verbatim

```sh
#!/bin/sh
set -e
# Suite usa SQLite (conftest fuerza RUNNING_TESTS=true). Cero deps externas.
exec python -m pytest -q "$@"
```

Single line: the test container is a pytest runner, nothing more. Args pass
through, so `docker compose --profile tests run --rm tests tests/integration/`
works.

---

## 8. `docker/local/docker-compose.local.yml` — verbatim (rename project name)

```yaml
services:
  api:
    build:
      context: ../..
      dockerfile: docker/local/Dockerfile.local
    container_name: vileads-api-local
    ports:
      - "8000:8000"
      - "5680:5680"
    volumes:
      # Live edit: source montado, reload de uvicorn pega los cambios.
      - ../..:/app
    env_file:
      - ../../.env
    environment:
      RUNNING_IN_DOCKER: "true"
      DATABASE_URL: postgresql+asyncpg://vileads:vileads@db:5432/vileads
      RUNNING_TESTS: ""
    depends_on:
      db:
        condition: service_healthy
    networks:
      - vileads-network

  db:
    build:
      context: ../..
      dockerfile: docker/db/Dockerfile.postgres
    container_name: vileads-db-local
    environment:
      POSTGRES_DB: vileads
      POSTGRES_USER: vileads
      POSTGRES_PASSWORD: vileads
    ports:
      - "5432:5432"
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vileads"]
      interval: 5s
      timeout: 5s
      retries: 30
    networks:
      - vileads-network

  adminer:
    image: adminer
    container_name: vileads-adminer-local
    ports:
      - "8090:8080"
    environment:
      ADMINER_DEFAULT_SERVER: db
    depends_on:
      - db
    networks:
      - vileads-network

  tests:
    build:
      context: ../..
      dockerfile: docker/local/Dockerfile.test
    container_name: vileads-tests-local
    volumes:
      - ../..:/app
    environment:
      RUNNING_TESTS: "true"
      # SQLite cae solo a archivo local (conftest fuerza el default).
    networks:
      - vileads-network
    # `docker compose --profile tests up tests` para correrlos a demanda.
    profiles:
      - tests

networks:
  vileads-network:
    driver: bridge

volumes:
  db_data:
    driver: local
```

Notes:

- `volumes: - ../..:/app` is the live-edit mount. **Required** for local —
  removes the need to rebuild on every code change.
- `RUNNING_TESTS: ""` on the `api` service explicitly empties the var so a
  stray export in the host shell doesn't accidentally switch the API to
  SQLite.
- Postgres `5432:5432` exposed on the host so the dev can connect a desktop
  client (DBeaver, TablePlus) without going through adminer.
- `adminer` on `:8090` (not `:8080`) to avoid colliding with other
  dev-server defaults.
- `tests` is under `profiles: ["tests"]` — invisible to `docker compose up`,
  appears with `--profile tests`. Wired by `make test-local`.

---

## 9. `docker/prod/Dockerfile.prod` — verbatim

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Solo runtime deps. No git, no debugpy.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    # Limpia build-essential despues de pip install (los wheels ya estan).
    apt-get purge -y build-essential && \
    apt-get autoremove -y && \
    apt-get clean

COPY . .

# Non-root user. Puerto 80 lo expone el host via port mapping; uvicorn
# corre en 8000 dentro del contenedor, sin necesitar root.
RUN useradd -m -u 1000 vileads && \
    chown -R vileads:vileads /app

USER vileads

EXPOSE 8000

COPY --chmod=755 docker/prod/entrypoint.sh /backend/entrypoint.sh

CMD ["/backend/entrypoint.sh"]
```

Why purge `build-essential` after `pip install`: any package with a C
extension was already wheel-built, so the toolchain is dead weight. Image
size drops materially.

Why non-root: defense in depth. A container escape via a Python RCE shouldn't
hand the attacker root inside the container. Rename `vileads` to your project
slug.

---

## 10. `docker/prod/entrypoint.sh` — verbatim

```sh
#!/bin/sh
set -e

# DATABASE_URL en prod apunta a RDS via .env (no es postgres del compose).
echo "Aplicando migraciones..."
alembic upgrade head

# Seed idempotente (init_terms / init_admin no duplican).
python -m app.scripts.init || echo "(init.py fallo o ya estaba seeded — sigo)"

echo "Iniciando uvicorn en modo produccion..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --limit-max-requests 1000 \
    --limit-concurrency 1000 \
    --proxy-headers \
    --forwarded-allow-ips '*'
```

`--proxy-headers --forwarded-allow-ips '*'` is what lets uvicorn trust the
`X-Forwarded-For` / `X-Forwarded-Proto` headers Cloudflare sets. Without it,
`request.client.host` is the Docker bridge IP and rate-limiting / audit logs
record the wrong source.

`--workers 2` is the conservative default for a t3.small / t3a.small EC2.
Scale up by editing the entrypoint, not by passing env vars — the value is
load-derived and should live in code with a comment.

---

## 11. `docker/prod/docker-compose.prod.yml` — verbatim (rename project name)

```yaml
# Stack de produccion para EC2 START.
#
# Diseno:
#  - api: corre uvicorn en :8000 dentro del contenedor; el host publica 80 -> 8000.
#         Cloudflare proxy llega a la EIP del EC2 en puerto 80. Modo SSL = Flexible
#         para arrancar; cuando se monte cert origen de Cloudflare, agregar
#         sidecar nginx con TLS y cambiar a Full(strict).
#  - DB: NO esta en el compose. Vive en RDS managed (modulo db de Terraform).
#        DATABASE_URL en .env apunta al endpoint de RDS.
#  - Redis + worker: no incluidos. Rate-limit en memoria, background tasks
#        via Starlette BackgroundTask in-process. Cuando se conecte cache
#        distribuido o arq queue, agregar `redis` service + worker.
#
# El .env vive en /opt/app/.env en la EC2. Lo genera el operador la primera vez
# con los outputs de Terraform (database_url, etc.) + secretos (JWT, Stripe, etc.).

services:
  api:
    build:
      context: ../..
      dockerfile: docker/prod/Dockerfile.prod
    container_name: vileads-api-prod
    restart: unless-stopped
    ports:
      - "80:8000"
    env_file:
      - ../../.env
    environment:
      RUNNING_IN_DOCKER: "true"
    networks:
      - vileads-network

networks:
  vileads-network:
    driver: bridge
```

`restart: unless-stopped` is the right policy on EC2 — recover from OOM kills
and Docker daemon restarts, but respect a deliberate `docker compose stop`.

---

## 12. `Makefile` — verbatim (rename project name in `-p` flag)

```makefile
# =============================================================================
# Makefile — atajos para los 3 entornos docker (local / dev / prod)
# =============================================================================
# Default ENV = local (la maquina del developer: live reload, debugpy, adminer).
# Sobrescribir con: `make ENV=dev up`  o  `make ENV=prod logs`.
#
# Stacks:
#   local -> docker/local/docker-compose.local.yml   (la maquina del dev)
#   dev   -> docker/dev/docker-compose.dev.yml       (entorno dev compartido)
#   prod  -> docker/prod/docker-compose.prod.yml     (lo que corre en EC2)

ENV ?= local
COMPOSE_FILE = docker/$(ENV)/docker-compose.$(ENV).yml
DC = docker compose -f $(COMPOSE_FILE) -p vileads-$(ENV)

.PHONY: help format lint up up-d down restart logs ps shell \
        migrate-create migrate-up migrate-down seed test test-local

help:
	@echo "Vileads Events — atajos docker (ENV=$(ENV))"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# -----------------------------------------------------------------------------
# Code quality
# -----------------------------------------------------------------------------
format: ## black + isort
	black --line-length 100 --exclude "alembic|venv" .
	isort --skip alembic --skip venv .

lint: ## flake8
	flake8 --exclude alembic,venv --max-line-length 100 app

# -----------------------------------------------------------------------------
# Container lifecycle (ENV=local|dev|prod)
# -----------------------------------------------------------------------------
up: ## Build + start tailing logs
	$(DC) up --build

up-d: ## Build + start detached
	$(DC) up --build -d

down: ## Stop + remove containers (mantiene volumenes)
	$(DC) down

restart: ## Reinicia el servicio api sin tocar db/redis
	$(DC) restart api

logs: ## Tail logs (todos los servicios)
	$(DC) logs -f

ps: ## Lista containers del stack
	$(DC) ps

shell: ## Shell dentro del contenedor api
	$(DC) exec api /bin/bash

# -----------------------------------------------------------------------------
# Alembic (corre dentro del api del stack activo)
# -----------------------------------------------------------------------------
migrate-create: ## Nueva migracion autogen (pide mensaje)
	@read -p "Migration message: " msg; \
	$(DC) exec api alembic revision --autogenerate -m "$$msg"

migrate-up: ## Aplica migraciones pendientes
	$(DC) exec api alembic upgrade head

migrate-down: ## Rollback de la ultima
	$(DC) exec api alembic downgrade -1

# -----------------------------------------------------------------------------
# Seeders + tests
# -----------------------------------------------------------------------------
seed: ## init_admin + init_terms (idempotente)
	$(DC) exec api python -m app.scripts.init

test: ## Corre pytest dentro del contenedor api del stack activo
	$(DC) exec api pytest -q

test-local: ## Corre pytest en el contenedor `tests` del compose local (profile=tests)
	docker compose -f docker/local/docker-compose.local.yml -p vileads-local \
		--profile tests run --rm tests
```

Usage:

```bash
make up                    # local (default) — full local stack
make ENV=dev up            # shared dev stack
make ENV=prod up           # only on the EC2 host (not your laptop)
make ENV=dev logs          # tail dev
make ENV=prod ps           # inspect prod from inside the EC2
make migrate-create        # autogen migration inside local api
make test-local            # spin up tests profile, run pytest, tear down
```

Critical knobs to rename per project:

- `vileads` in `-p vileads-$(ENV)` → `<your-slug>-$(ENV)`. The `-p` flag is
  the compose project name; collisions across multiple checked-out repos cause
  silent container name reuse.
- Banner text in `help:` (`"Vileads Events — atajos docker"`).

---

## 13. `.env.example` additions

The compose files reference these vars in `env_file` or `environment`. Add to
your `.env.example`:

```dotenv
# Set by docker-compose, do not set locally.
RUNNING_IN_DOCKER=
# Set by the tests container only.
RUNNING_TESTS=

# Local + dev: API connects to the compose `db` service.
# Prod: points to RDS (terraform output).
DATABASE_URL=postgresql+asyncpg://vileads:vileads@db:5432/vileads

# Toggles debugpy listener on :5680 in local. Accept "true"/"True".
DEBUG=false

# Prod-only: Cloudflare sits in front, count it as 1 trusted proxy hop.
TRUSTED_PROXY_COUNT=1
```

---

## 14. Verification checklist

- [ ] `docker/` tree exists with all 11 files listed in §"Layout".
- [ ] `Makefile` at repo root with `ENV ?= local` and the
      `docker/$(ENV)/docker-compose.$(ENV).yml` path.
- [ ] `docker-compose.prod.yml` has **no `db` service** and **no `volumes:`
      block**.
- [ ] `docker-compose.local.yml` has `adminer` and a `tests` service with
      `profiles: ["tests"]`.
- [ ] `docker-compose.local.yml` `api.volumes` mounts `../..:/app`.
      `docker-compose.dev.yml` and `docker-compose.prod.yml` do **not**.
- [ ] `Dockerfile.prod` ends with `USER vileads` (or your slug) and has the
      `apt-get purge -y build-essential` line.
- [ ] `prod/entrypoint.sh` runs uvicorn with
      `--workers 2 --proxy-headers --forwarded-allow-ips '*'`.
- [ ] `local/entrypoint.sh` toggles debugpy via `if [ "$DEBUG" = "true" ]`.
- [ ] `entrypoint.sh` files are `chmod 755` (copied via `COPY --chmod=755`).
- [ ] `make up` boots the full local stack (api + db + adminer).
- [ ] `make ENV=dev up` boots the dev stack on port 8001.
- [ ] `make test-local` runs pytest and exits cleanly.
- [ ] `app/scripts/init.py` exists and is idempotent (or the entrypoint line
      is removed with a documented reason).
- [ ] CI workflow deploy step uses
      `docker compose -f docker/prod/docker-compose.prod.yml` literally.

---

## 15. Common pitfalls

- **Collapsing `local` and `dev` into one compose file.** They look similar
  but differ in volume mounts, debugpy, adminer, tests profile, and intended
  audience. Keep them separate. If you "simplify" by merging, you lose the
  ability to test shared-env behavior on a dev branch.
- **Adding `db` service to `docker-compose.prod.yml`.** Prod uses RDS. A
  containerized Postgres next to the app in prod loses backups, snapshots,
  multi-AZ, and forces you to mount EBS for `/var/lib/postgresql/data`. Don't.
- **Skipping `--proxy-headers` in prod.** `request.client.host` becomes the
  Docker bridge IP. Rate limits, audit logs, and IP-based bans all break
  silently.
- **Running prod as root.** Drop the `USER vileads` and you've handed an
  attacker root inside the container. Cheap, well-understood mitigation.
  Don't remove it.
- **Mounting source in dev compose "for convenience".** Dev is shared — a
  source mount means whoever last shelled in determines the running code.
  Rebuild instead.
- **`make ENV=prod up` from your laptop.** Prod compose is invoked by CI on
  the EC2 host. Locally you build a `prod` image at most to verify the
  Dockerfile compiles; you do not `up` it.
- **Renaming files but not the Makefile path.** The Makefile computes
  `docker/$(ENV)/docker-compose.$(ENV).yml` literally. Renaming a compose
  file silently breaks every Makefile target — and the help output won't
  warn you.
- **Forgetting `restart: unless-stopped` in prod.** The container won't
  recover from OOM kills or daemon restarts. Always include it.
- **Hard-coding the `-p` project name to a stale slug.** Multiple checked-out
  repos with the same `-p` name share container names → silent container
  reuse and confusing logs. Rename to match your slug per project.

---

## 16. When to deviate

Only with a reason that fits one of these:

- **Project uses MongoDB, not Postgres.** Replace `docker/db/Dockerfile.postgres`
  with a Mongo equivalent; drop `pg_isready` for `mongosh --eval`. Adjust
  `DATABASE_URL` format.
- **Project needs Redis + worker.** Add `redis` service to local + dev (and
  prod — typically ElastiCache externally, same as RDS). Add a `worker`
  service that runs `arq` / `celery` / RQ pointing at the same code image.
- **Cloudflare Origin Certificate is wired** → add an `nginx` sidecar to
  prod compose with TLS, change `ports` to `443:443`, flip Cloudflare to
  Full(strict). Update the prod compose comment block.
- **Project genuinely doesn't need a `dev` env** (one-person side project,
  no shared staging). You can drop `docker/dev/` and the `ENV=dev` target —
  but then update the Makefile help and the CLAUDE.md note so the next
  reader doesn't expect it.
- **EC2 is replaced with ECS / Fargate / Fly / Render.** The per-Dockerfile
  guidance still applies; the compose-as-deploy contract becomes an
  ECS task definition / Fly `fly.toml`. Document the swap and keep the prod
  Dockerfile as the source of truth.

Anything else, stop and ask the user before deviating from the verbatim
templates above.
