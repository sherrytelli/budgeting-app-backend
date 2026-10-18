# Budgeting App Backend

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-ready **FastAPI** backend for a personal budgeting Android app.

The core philosophy is **hierarchical budgeting**: an overarching monthly budget is
subdivided into daily categorical sub-budgets, and every individual expense is logged
against a category. There is **no daily rollover** — unused category money does not
carry over to the next day; spending is always tracked against the monthly total.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Development Mode](#development-mode)
- [Production Mode](#production-mode)
- [Caddy Setup (Production / TLS)](#caddy-setup-production--tls)
- [Database & Migrations](#database--migrations)
- [Testing](#testing)
- [API Reference](#api-reference)
- [Data Model](#data-model)
- [Logging](#logging)
- [Security Model](#security-model)
- [Dev vs. Production Cheat Sheet](#dev-vs-production-cheat-sheet)
- [Troubleshooting](#troubleshooting)
- [Useful Commands](#useful-commands)

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Runtime | Python 3.13 |
| Framework | FastAPI (`fastapi[standard]`) + Uvicorn |
| Database | PostgreSQL 18 (`pgvector/pgvector:pg18`) |
| ORM | SQLAlchemy 2.0 (strict async, `asyncpg` driver) |
| Migrations | Alembic (async `env.py`) |
| Auth | JWT (PyJWT), Argon2 password hashing (`pwdlib[argon2]`) |
| Validation | Pydantic V2 + `pydantic-settings` |
| Logging | `structlog` (colored console in dev, JSON in production) |
| Reverse proxy | Caddy 2.11 (automatic HTTPS) |
| Packaging | `uv` + `hatchling` |
| Containers | Docker & Docker Compose |

---

## Architecture Overview

```
Android app
    │  HTTPS
    ▼
┌─────────────┐      ┌──────────────────┐      ┌──────────────┐
│   Caddy     │─────▶│  FastAPI (app)   │─────▶│  PostgreSQL  │
│  80/443     │ /api │  internal :8000  │      │  internal    │
└─────────────┘      └──────────────────┘      └──────────────┘
   public TLS           not public              not public
```

In production, **Caddy is the only public entrypoint**. The `app` container listens on
port 8000 but is bound to `127.0.0.1` on the host (loopback only), and the database is
likewise loopback-only. Caddy terminates TLS, adds security headers, and blocks
external access to the API docs, the registration endpoint, and `/health`.

---

## Project Structure

```
├── app/                          # Application package
│   ├── main.py                   # FastAPI app assembly (middleware, handlers, /health)
│   ├── core/
│   │   ├── config.py             # pydantic-settings Settings singleton
│   │   ├── database.py           # Async engine, session maker, get_db dependency
│   │   ├── logging.py            # structlog configuration (dev vs production renderer)
│   │   └── security.py           # Argon2 hashing, JWT encode/decode, current-user dep
│   ├── api/
│   │   ├── deps.py               # Shared dependencies (active user, pagination)
│   │   └── v1/
│   │       ├── api.py            # Aggregates routers under /api/v1
│   │       └── endpoints/
│   │           ├── auth.py       # /auth/register, /auth/login
│   │           ├── budgets.py    # /budgets CRUD
│   │           ├── categories.py # /budgets/{id}/categories, /categories/{id}
│   │           └── expenses.py   # /expenses CRUD + filtering
│   ├── models/                   # SQLAlchemy 2.0 ORM models (Mapped / mapped_column)
│   ├── schemas/                  # Pydantic V2 request/response schemas
│   └── services/                 # Business logic (budget_service)
├── migrations/                   # Alembic migration environment + versions
├── tests/                        # UI-contract test suite (pytest)
├── alembic.ini                   # Alembic configuration
├── docker-compose.yml            # db + app + caddy orchestration
├── Dockerfile                    # Multi-stage production image
├── Caddyfile                     # Reverse proxy + TLS + security headers
├── pyproject.toml                # Dependencies, ruff/mypy/pytest config
├── requirements.txt              # Frozen dependency list
├── .env.example                  # Environment variable template
└── LICENSE                       # MIT License
```

---

## Prerequisites

**For local development:**

- Python **3.13+**
- [`uv`](https://docs.astral.sh/uv/) (package manager)
- Docker & Docker Compose (to run PostgreSQL locally)

**For production:**

- A Linux server with Docker & Docker Compose
- A public domain name pointing at the server (e.g. a free DuckDNS subdomain)
- Inbound TCP **80** and **443**, and UDP **443** open in the firewall

---

## Environment Variables

All configuration is read from `.env` via the `Settings` class
(`app/core/config.py`). Start from the template:

```bash
cp .env.example .env
```

| Variable | Purpose | Dev value | Production value |
| --- | --- | --- | --- |
| `POSTGRES_USER` | Postgres user | `budget_user` | change it |
| `POSTGRES_PASSWORD` | Postgres password | `budget_secure_password` | **strong, unique** |
| `POSTGRES_DB` | Postgres database name | `budget_db` | `budget_db` |
| `DATABASE_URL` | App → DB connection | `...@127.0.0.1:5432/...` (host dev) | `...@db:5432/...` (compose) |
| `ALEMBIC_DATABASE_URL` | Alembic → DB connection | `...@127.0.0.1:5432/...` | `...@127.0.0.1:5432/...` |
| `SECRET_KEY` | JWT signing key | any throwaway string | **64-byte random secret** |
| `ALGORITHM` | JWT algorithm | `HS256` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime | `30` | `30` (or shorter) |
| `CORS_ORIGINS` | Allowed browser origins (JSON array) | `["*"]` | restrict if you have a web client |
| `ENVIRONMENT` | Toggles log renderer | `dev` | `production` |
| `DOMAIN_NAME` | Public hostname (Caddy) | unused | `budget.example.com` |
| `ACME_EMAIL` | Let's Encrypt contact email | unused | `you@example.com` |

### Two connection strings, two contexts

This is the single most confusing part of the setup, so it is worth stating clearly:

- **`DATABASE_URL`** is what the **application** uses.
  - When the app runs **in Docker** (production), it must use the compose service name:
    `postgresql+asyncpg://user:pass@db:5432/budget_db`
  - When the app runs **on the host** (dev, `fastapi dev`), it must use loopback:
    `postgresql+asyncpg://user:pass@127.0.0.1:5432/budget_db`
- **`ALEMBIC_DATABASE_URL`** is what **migrations** use. Alembic is always run from the
  **host** (the container image does not include `migrations/` or `alembic.ini`), so it
  always points at `127.0.0.1:5432` — which is why the `db` service publishes its port
  on loopback.

> The test suite sets `DATABASE_URL` programmatically and never mutates `.env`
> (see `tests/conftest.py`).

---

## Development Mode

Goal: run PostgreSQL in Docker, run the API on the host with **hot reload**.

### 1. Install dependencies

```bash
uv sync
```

### 2. Create and edit `.env`

```bash
cp .env.example .env
```

For host-based development, switch `DATABASE_URL` to loopback and set the environment:

```dotenv
DATABASE_URL=postgresql+asyncpg://budget_user:budget_secure_password@127.0.0.1:5432/budget_db
ALEMBIC_DATABASE_URL=postgresql+asyncpg://budget_user:budget_secure_password@127.0.0.1:5432/budget_db
ENVIRONMENT=dev
SECRET_KEY=dev-only-not-a-real-secret
CORS_ORIGINS=["*"]
```

### 3. Start PostgreSQL

```bash
docker compose up -d db
```

The `db` service already publishes `127.0.0.1:5432` in `docker-compose.yml` — no edits
required. Publishing on the loopback address (not `0.0.0.0`) keeps Postgres
unreachable from other machines while still allowing host-side Alembic and pytest runs.

### 4. Apply migrations

```bash
uv run alembic upgrade head
```

### 5. Run the API with auto-reload

```bash
uv run fastapi dev app/main.py
```

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI schema: <http://localhost:8000/openapi.json>
- Health check: <http://localhost:8000/health>

Docs are reachable in dev because Caddy is not in front of the app.

### What changes in dev mode

| Setting | Dev value | Why |
| --- | --- | --- |
| `ENVIRONMENT` | `dev` | `structlog` uses the colored console renderer |
| `DATABASE_URL` | `...@127.0.0.1:5432/...` | app runs on the host, not in the compose network |
| `SECRET_KEY` | throwaway value | tokens are local; never reuse in production |
| `CORS_ORIGINS` | `["*"]` | lets Expo/React Native dev clients call the API |
| Docs endpoints | enabled | exposed directly on `:8000` |
| Caddy | not started | TLS/domain only matter in production |

---

## Production Mode

Goal: run the full stack (`db` + `app` + `caddy`) behind automatic HTTPS.

### 1. Harden `.env`

```dotenv
POSTGRES_USER=budget_user
POSTGRES_PASSWORD=<strong-unique-password>
POSTGRES_DB=budget_db
DATABASE_URL=postgresql+asyncpg://budget_user:<strong-unique-password>@db:5432/budget_db
ALEMBIC_DATABASE_URL=postgresql+asyncpg://budget_user:<strong-unique-password>@127.0.0.1:5432/budget_db

SECRET_KEY=<64-byte-random-secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

CORS_ORIGINS=["*"]
ENVIRONMENT=production

DOMAIN_NAME=budget.example.com
ACME_EMAIL=you@example.com
```

Generate a strong secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 2. Start the database and apply migrations

```bash
docker compose up -d db
uv run alembic upgrade head
```

### 3. Build and start the full stack

```bash
docker compose up -d --build
```

Compose starts in dependency order using health checks:

1. `db` becomes healthy (`pg_isready`).
2. `app` builds from the `production` stage of the Dockerfile and becomes healthy
   (`/health`).
3. `caddy` starts and obtains a TLS certificate.

### 4. Verify

```bash
docker compose ps
curl -I https://$DOMAIN_NAME/health   # expect 404 (Caddy hides /health)
curl -I https://$DOMAIN_NAME/api/v1/auth/login
```

### What changes in production mode

| Setting | Production value | Why |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | `structlog` emits JSON for log aggregation |
| `DATABASE_URL` | `...@db:5432/...` | app talks to the `db` compose service |
| `SECRET_KEY` | 64-byte random secret | invalidates all tokens if ever rotated |
| `POSTGRES_PASSWORD` | strong, unique | database is a real network service |
| `CORS_ORIGINS` | restricted (if a web client exists) | native apps don't need `*` |
| `DOMAIN_NAME` / `ACME_EMAIL` | set | required by Caddy for certificate issuance |
| Docs endpoints | blocked by Caddy | `/docs`, `/redoc`, `/openapi.json` return 404 externally |
| `/api/v1/auth/register` | blocked by Caddy | prevents public self-registration |
| `/health` | blocked by Caddy | internal-only probe |
| App port | `127.0.0.1:8000` | Caddy must be the only public path in |
| DB port | `127.0.0.1:5432` | host-only tooling (Alembic, pytest) |

> **Do not expose port 8000 publicly.** Publishing it would let clients bypass Caddy's
> blocking rules and reach the docs and registration endpoints directly.

### Restricting `/register` while keeping sign-ups working

Because Caddy returns 404 for `/api/v1/auth/register`, users are provisioned by
creating the account through the internal path (e.g. `docker compose exec` into the
container or calling the API from the server on `127.0.0.1:8000`) until a dedicated
admin flow exists.

---

## Caddy Setup (Production / TLS)

Caddy handles certificate issuance, renewal, HTTP→HTTPS redirects, and security
headers. The bundled `Caddyfile` already contains everything needed:

```caddyfile
{
    email {$ACME_EMAIL}
}

{$DOMAIN_NAME} {
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        -Server
    }

    @local_only {
        path /docs /docs/* /redoc /redoc/* /openapi.json /api/v1/auth/register /health
    }
    respond @local_only 404

    reverse_proxy app:8000 {
        header_up X-Proxied-By "caddy"
    }
}
```

### Step-by-step

1. **Point a domain at the server.**
   - Create an `A` record (and `AAAA` if you have IPv6) for `DOMAIN_NAME` pointing to the
     server's public IP.
   - With DuckDNS: create a subdomain and update it to the server IP, then set
     `DOMAIN_NAME=<subdomain>.duckdns.org` in `.env`.
   - Verify propagation: `dig +short $DOMAIN_NAME` should return the server IP.

2. **Open the firewall.**
   ```bash
   sudo ufw allow 80/tcp     # ACME HTTP challenge + redirect
   sudo ufw allow 443/tcp    # HTTPS
   sudo ufw allow 443/udp    # HTTP/3 (QUIC)
   ```

3. **Set Caddy variables in `.env`.** Both are required — the compose file uses
   `${DOMAIN_NAME:?}` / `${ACME_EMAIL:?}`, so Compose fails fast if either is empty:
   ```dotenv
   DOMAIN_NAME=budget.example.com
   ACME_EMAIL=you@example.com
   ```

4. **Validate the rendered compose config** (catches missing variables before start):
   ```bash
   docker compose config
   ```

5. **Start Caddy with the stack:**
   ```bash
   docker compose up -d --build
   ```

6. **Watch certificate issuance:**
   ```bash
   docker compose logs -f caddy
   ```
   A successful run shows the certificate being obtained and served. The first
   issuance can take up to a minute after DNS is live.

7. **Confirm HTTPS and headers:**
   ```bash
   curl -sI https://$DOMAIN_NAME/api/v1/auth/login | grep -i -E 'strict-transport|x-content-type|x-frame|server'
   ```

8. **Confirm the blocks work:**
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' https://$DOMAIN_NAME/docs            # 404
   curl -s -o /dev/null -w '%{http_code}\n' https://$DOMAIN_NAME/health          # 404
   curl -s -o /dev/null -w '%{http_code}\n' https://$DOMAIN_NAME/api/v1/auth/register # 404
   ```

### Notes

- **Certificate persistence.** `caddy_data` and `caddy_config` are named volumes. Keep
  them — deleting `caddy_data` forces a fresh ACME request and can hit Let's Encrypt
  rate limits.
- **Port 80 is required.** The default Caddy TLS-ALPN/HTTP challenge needs port 80
  reachable. If port 80 is unavailable, switch to a DNS challenge (e.g. the DuckDNS or
  Cloudflare DNS plugin), which requires a custom Caddy image with the plugin built in.
- **Reloading config.** Editing the `Caddyfile` while Caddy runs: apply with
  ```bash
  docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
  ```
  or simply `docker compose restart caddy`.
- **HTTP/3.** UDP 443 is published, so QUIC is enabled automatically by Caddy.

---

## Database & Migrations

Migrations run from the **host** against the loopback-published Postgres port. The
production image intentionally ships only the `app/` package, so `alembic` is not
available inside the container.

```bash
# Apply all migrations
uv run alembic upgrade head

# Create a new migration after editing models
uv run alembic revision --autogenerate -m "add something"

# Inspect current revision
uv run alembic current

# Roll back one revision
uv run alembic downgrade -1
```

Migration files land in `migrations/versions/` with a timestamped name
(`YYYY_MM_DD_HHMM-<rev>_<slug>.py`).

---

## Testing

The contract test suite runs from the host against the loopback Postgres port. It drops
and recreates a dedicated `test_budget_db`, so **start the `db` service first**:

```bash
docker compose up -d db
uv run pytest
```

With coverage / verbose output:

```bash
uv run pytest -v
```

Linting and type checking:

```bash
uv run ruff check .
uv run mypy app
```

The suite refuses to run against any database whose name is not `test_budget_db`.

---

## API Reference

Base path: `/api/v1`. All endpoints except `auth/register` and `auth/login` require a
`Authorization: Bearer <token>` header.

### Authentication

| Method | Path | Status | Description |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | 201 | Register a user (email, password, optional full name) |
| `POST` | `/auth/login` | 200 | OAuth2 password form → `{ access_token, token_type }` |

### Monthly Budgets

| Method | Path | Status | Description |
| --- | --- | --- | --- |
| `POST` | `/budgets` | 201 | Create a named monthly budget |
| `GET` | `/budgets?year=&month=` | 200 | List budgets (with `total_spent`) |
| `GET` | `/budgets/{budget_id}` | 200 | Get a budget with nested categories |
| `PUT` | `/budgets/{budget_id}` | 200 | Partially update a budget |
| `DELETE` | `/budgets/{budget_id}` | 204 | Delete a budget (cascades categories + expenses) |

### Daily Categories

| Method | Path | Status | Description |
| --- | --- | --- | --- |
| `POST` | `/budgets/{budget_id}/categories` | 201 | Create a category inside a budget |
| `PUT` | `/categories/{category_id}` | 200 | Partially update a category |
| `DELETE` | `/categories/{category_id}` | 204 | Delete a category (cascades expenses) |

### Expenses

| Method | Path | Status | Description |
| --- | --- | --- | --- |
| `POST` | `/expenses` | 201 | Create an expense |
| `GET` | `/expenses` | 200 | List with filters (see below) |
| `PUT` | `/expenses/{expense_id}` | 200 | Partially update an expense |
| `DELETE` | `/expenses/{expense_id}` | 204 | Delete an expense |

`GET /expenses` query parameters: `category_id`, `budget_id`, `start_date`, `end_date`,
`month`, `year`, `limit` (1–1000), `offset`.

### Health

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | `{"status": "ok"}` — used by Docker/compose probes; blocked externally by Caddy |

### Business rules worth knowing

- **Money** is validated and stored as `Decimal` (`Numeric(12, 2)`) — never floats.
- **`spent_at`** must be an aware datetime (device wall-clock with UTC offset, e.g.
  `2026-10-12T00:30:00+05:00`). The server derives the timezone-independent
  `spent_date` from it.
- An expense's `spent_date` must fall **inside its budget's month** and must **not be
  in the future** (14-hour tolerance to cover every UTC offset).
- Budget names are unique per `(user, name, month, year)` — duplicates return **409**.
- Emails are stored lowercased with a DB-level `lower(email)` unique index; login is
  case-insensitive.

---

## Data Model

```
users (id, email, hashed_password, full_name, is_active, timestamps)
  │  1
  │  N
monthly_budgets (id, user_id, name, month, year, total_limit, currency, timestamps)
  │  1
  │  N
daily_categories (id, monthly_budget_id, name, daily_limit, reminder_time, icon, timestamps)
  │  1
  │  N
expenses (id, daily_category_id, amount, note, spent_at, spent_date, timestamps)
```

- All primary keys are UUIDs (`uuid4`).
- All timestamps are UTC (`DateTime(timezone=True)`).
- `reminder_time` is a naive local time (`Time(timezone=False)`) representing the
  wall-clock time on the user's device.
- Deletion cascades: deleting a budget removes its categories, and deleting a category
  removes its expenses (`ON DELETE CASCADE`).

---

## Logging

`structlog` is configured at startup (`app/core/logging.py`), keyed off `ENVIRONMENT`:

- **`dev`** → `ConsoleRenderer(colors=True)`: human-readable, colored output.
- **`production`** → `JSONRenderer()`: one JSON object per line for log shippers.

Every request is logged with a generated `request_id`, method, path, status, and
duration, and the same id is returned in the `X-Request-ID` response header (and
propagated by Caddy via `X-Proxied-By: caddy`).

To view container logs:

```bash
docker compose logs -f app      # application
docker compose logs -f caddy    # proxy + ACME
docker compose logs -f db       # database
```

---

## Security Model

- **Passwords:** Argon2 via `pwdlib` (never `passlib`/`bcrypt`).
- **Tokens:** stateless HS256 JWTs; the `sub` claim is the user id as a string. Changing
  `SECRET_KEY` invalidates every issued token.
- **Network isolation:** only Caddy exposes ports 80/443; the app and database are
  loopback-bound on the host.
- **Edge blocking:** `/docs`, `/redoc`, `/openapi.json`, `/api/v1/auth/register`, and
  `/health` return 404 through Caddy.
- **Headers:** HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and the
  `Server` header removed.
- **Ownership checks:** every budget/category/expense operation is scoped by the
  authenticated user id.

**Production hardening checklist**

- [ ] Replace `SECRET_KEY` with a fresh 64-byte random value.
- [ ] Replace `POSTGRES_PASSWORD` with a strong, unique password.
- [ ] Set `ENVIRONMENT=production`.
- [ ] Set `DATABASE_URL` to the `db` service hostname.
- [ ] Restrict `CORS_ORIGINS` if a browser client exists.
- [ ] Set `DOMAIN_NAME` and `ACME_EMAIL`; confirm DNS resolves to the server.
- [ ] Open TCP 80/443 and UDP 443 only.
- [ ] Keep the app and DB bound to `127.0.0.1` in `docker-compose.yml`.
- [ ] Never commit `.env` (already git-ignored).

---

## Dev vs. Production Cheat Sheet

| Concern | Dev | Production |
| --- | --- | --- |
| Run the API | `uv run fastapi dev app/main.py` | `docker compose up -d --build` |
| Environment | host | Docker (`production` image target) |
| `ENVIRONMENT` | `dev` | `production` |
| Log format | colored console | JSON |
| `DATABASE_URL` host | `127.0.0.1:5432` | `db:5432` |
| `SECRET_KEY` | throwaway | 64-byte random |
| CORS | `["*"]` | restricted |
| TLS | none | Caddy + Let's Encrypt |
| Docs | public on `:8000` | blocked by Caddy (404) |
| `/register` | public | blocked by Caddy (404) |
| Health check | `curl localhost:8000/health` | internal Docker probe |
| Migrations | `uv run alembic upgrade head` | `uv run alembic upgrade head` (from host) |

---

## Troubleshooting

**`DATABASE_URL` connection refused when running `fastapi dev`**
The app is trying to reach `db:5432`, which only resolves inside the compose network.
Switch `DATABASE_URL` to `127.0.0.1:5432` for host development.

**`could not translate host name "db"` in production**
`DATABASE_URL` still points at `127.0.0.1`. In production it must use the `db` service
name.

**Caddy refuses to start / `DOMAIN_NAME must be set`**
Compose fails fast when `DOMAIN_NAME` or `ACME_EMAIL` is empty in `.env`. Set both.

**No certificate issued**
Check that DNS resolves to the server (`dig +short $DOMAIN_NAME`), that ports 80 and 443
are open, and read `docker compose logs -f caddy`. First issuance can lag DNS
propagation.

**`alembic: command not found` inside the app container**
Expected — the image does not include `migrations/` or `alembic.ini`. Run Alembic from
the host; it reaches Postgres over the loopback-published port.

**Migrations applied but tables missing**
Confirm `ALEMBIC_DATABASE_URL` points at the same database the app uses, and run
`uv run alembic upgrade head` after the `db` container is healthy.

**Tests fail to connect**
Start the database first: `docker compose up -d db`. The suite expects `test_budget_db`
to be creatable on `127.0.0.1:5432`.

**`409` when creating a budget**
A budget with the same `name` already exists for that `month`/`year`.

**`422` when creating an expense**
`spent_at` is naive (missing an offset), outside the budget's month, or in the future.

---

## Useful Commands

```bash
# ── Development ────────────────────────────────────────────────
uv sync                                   # install dependencies
uv run fastapi dev app/main.py            # run API with reload
uv run pytest                             # run the test suite
uv run ruff check .                       # lint
uv run mypy app                           # type check

# ── Database ───────────────────────────────────────────────────
docker compose up -d db                   # start Postgres
uv run alembic upgrade head               # apply migrations
uv run alembic revision --autogenerate -m "message"
uv run alembic current

# ── Production ─────────────────────────────────────────────────
docker compose config                     # validate rendered config
docker compose up -d --build              # build + start everything
docker compose ps                         # check health
docker compose logs -f app                # app logs
docker compose logs -f caddy              # proxy / TLS logs
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
docker compose down                       # stop (keeps volumes)
docker compose down -v                    # stop and wipe data (careful!)
```

---

## License

Released under the **MIT License**. See [`LICENSE`](LICENSE) for the full text.
