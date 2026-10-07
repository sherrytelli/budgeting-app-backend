# AI Agent Instructions for Personal Budgeting Backend

## 📚 Active Local Skills (CRITICAL)
This project has hyper-specific AI skills installed locally (typically in the `.agents/skills` directory or tracked via `skills.json`). **You MUST read and strictly adhere to the corresponding skill files before generating code for the following domains:**

1. **Project Architecture:** Consult the `python-project-structure` skill when creating new files to ensure they are placed in the correct `app/api`, `app/core`, `app/models`, or `app/schemas` directories.
2. **FastAPI & Routing:** Consult the official `fastapi` skill to ensure you are following the creator's best practices for `Depends`, dependency injection, and async route handlers.
3. **Data Validation:** Consult the `pydantic` skill. You are strictly forbidden from using Pydantic V1 syntax. You must use Pydantic V2 (`model_validate`, `model_dump`, etc.).
4. **Database & ORM:** Consult the `sqlalchemy` skill. You must use modern SQLAlchemy 2.0 `Mapped` and `mapped_column` syntax, and strict `AsyncSession` with `asyncpg`.
5. **Infrastructure:** Consult the `docker` skill when modifying the `Dockerfile` or `docker-compose.yml` to ensure proper multi-stage builds and PostgreSQL health checks.

---

## Project Overview
You are an expert backend engineer specializing in high-performance Python architectures. You are building the API and database layer for a custom, personal Android budgeting application. The app relies on a centralized, self-hosted backend. The core philosophy of this system is **hierarchical budgeting** (monthly overall budgets divided into daily categorical sub-budgets) and **granular expense logging** rather than daily rollovers.

## Technology Stack
- **Runtime & Framework:** Python 3.12+, FastAPI (`fastapi[standard]`), Uvicorn.
- **Database:** PostgreSQL 18, SQLAlchemy 2.0 (Strict Async via `asyncpg`), Alembic for migrations.
- **Authentication:** JWT tokens using `pyjwt`, Password hashing using `pwdlib[argon2]`.
- **Configuration:** `pydantic-settings` reading from `.env`.
- **Deployment:** Docker & Docker Compose.

---

## 🤖 General AI Behavior Rules
1. **No Placeholders:** Never use `# TODO`, `pass`, or `// placeholder` comments. Write complete, production-ready code with full imports.
2. **Type Safety First:** Use strict Python type hinting. Leverage Pydantic V2 for all request/response schemas.
3. **Handle Errors Gracefully:** Always wrap database queries and operations in `try/except` blocks where appropriate. Return standard HTTP 400/404/500 JSON error structures using FastAPI's `HTTPException`.
4. **Environment Variables:** Never hardcode secrets, database URLs, or configurations. Always read from the Pydantic `Settings` class.

---

## 🐍 Python & FastAPI Rules

### 1. API Design & Pydantic
- **Pydantic V2 Syntax:** Strictly use Pydantic V2 features (`model_validate`, `model_dump`, `@model_validator`).
- **RESTful Endpoints:** Group endpoints logically by resource using `APIRouter` (e.g., `/api/v1/budgets`, `/api/v1/expenses`).
- **Dependency Injection:** Use FastAPI `Depends` for extracting database sessions (`get_db`) and JWT authentication (`get_current_user`). Do not instantiate database sessions manually inside route functions.
- **CORS:** Ensure CORS middleware is configured to allow requests from `*` (or the specific local network IPs) since React Native / Expo mobile apps don't always send standard origin headers.

### 2. Authentication & Security
- **Stateless JWT:** Use PyJWT to encode/decode tokens. Ensure the `sub` claim contains the user ID as a string.
- **Password Hashing:** Strictly use `pwdlib` with Argon2. Do not use legacy `passlib` or `bcrypt` as they are deprecated or slower for modern Python standards.

---

## 🐘 Database & SQLAlchemy 2.0 Rules

### 1. Strict Async Setup
- **Async Only:** Use `AsyncSession`, `create_async_engine`, and `asyncpg` driver. **Never** use synchronous `Session` or `psycopg2`.
- **Queries:** Execute all queries using `await session.execute(select(...))` and `await session.commit()`.

### 2. Schema & Models
- **Declarative Models:** Use SQLAlchemy 2.0 `Mapped` and `mapped_column` syntax exclusively. Do not use the old `Column(...)` syntax.
- **Primary Keys:** Use `UUID` (specifically `uuid.uuid4`) as the primary key for all tables.
- **Cascades:** Use `ON DELETE CASCADE` for relationships (e.g., deleting a `MonthlyBudget` must automatically delete its `DailyCategories` and their associated `Expenses`).

### 3. Data Types & Precision (CRITICAL)
- **Money Handling:** ALWAYS use `Numeric(12, 2)` in SQLAlchemy models and strict `Decimal` in Pydantic schemas. **Never use floats for currency** to avoid precision errors.
- **Timezones:** Store all timestamps as UTC `DateTime(timezone=True)`. 
- **Reminders:** Daily category reminder times should be stored as `Time(timezone=False)` representing the local time on the user's device (e.g., `16:00:00` for 4:00 PM).

---

## ⚙️ Core Business & Analytics Logic

When building the `analytics_service.py` or calculating statistics, strictly adhere to these rules:
1. **Monthly Tracking, No Daily Rollover:** The system tracks granular daily spending *against* the overarching monthly budget. If the user spends 0 PKR on a category today, do NOT add that unused amount to tomorrow's category limit.
2. **Current Standing Validation:** Calculate the total month's spending across all categories and subtract it from the `monthly_budgets.total_limit` to determine if the user is `UNDER_BUDGET` or `OVER_BUDGET`.
3. **Dynamic Burn Rate (Pacing):** The analytics engine must calculate the "safe daily allowance" for the remainder of the month: `(Remaining Monthly Budget) / (Remaining Days in Month)`.