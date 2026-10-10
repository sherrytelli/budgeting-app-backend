# Budgeting App Backend

A production-ready FastAPI backend for a personal budgeting Android app with hierarchical budgeting (monthly budgets → daily categories → granular expenses), JWT authentication, and PostgreSQL.

## Tech Stack

- **Runtime:** Python 3.13, FastAPI
- **Database:** PostgreSQL 18, SQLAlchemy 2.0 (Async), Alembic migrations
- **Auth:** JWT (PyJWT), Argon2 password hashing (pwdlib)
- **Config:** pydantic-settings
- **Logging:** structlog (JSON)
- **Deployment:** Docker & Docker Compose

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.13+ (for local development)
- uv (package manager)

### Local Development

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your preferred values
   ```

3. **Start PostgreSQL:**
   ```bash
   docker compose up -d db
   ```
   Uncomment **ports** of **db** section in the **docker-compose.yml** file for local development with the postgres server

4. **Run migrations:**
   ```bash
   uv run alembic upgrade head
   ```

5. **Start the API server:**
   ```bash
   uv run fastapi dev app/main.py
   ```

### Docker Deployment

```bash
docker compose up -d --build
```

## API Documentation

Once running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

## Project Structure

```
├── app/                    # Application package
│   ├── __init__.py
│   ├── main.py             # FastAPI application entrypoint
│   ├── core/               # Configuration, database, security
│   ├── models/             # SQLAlchemy 2.0 ORM models
│   ├── schemas/            # Pydantic V2 request/response schemas
│   ├── api/                # API routers and endpoints
│   └── services/           # Business logic services
├── migrations/             # Database migrations
├── docker-compose.yml      # Multi-service orchestration
├── Dockerfile              # Multi-stage Docker build
├── pyproject.toml          # Project metadata & dependencies
└── .env.example            # Environment variable template
```

## License

Private — Personal project
