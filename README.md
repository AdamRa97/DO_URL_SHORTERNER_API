# URL Shortener API

A production-ready REST API that accepts long URLs and generates shortened aliases, with redirection, metadata retrieval, authentication, and click analytics.

## Features

- **Create** shortened URLs with auto-generated or custom aliases
- **Redirect** via `GET /{alias}` (302) with Redis cache-aside for fast lookups
- **Metadata** retrieval and management (update, delete)
- **Click analytics** per link (total clicks, unique IPs)
- **JWT authentication** (access + refresh tokens)
- **RBAC** — `user` and `admin` roles
- **Rate limiting** — Fixed Window algorithm via slowapi
- **Async** throughout — FastAPI + SQLAlchemy asyncio + asyncpg

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 |
| Cache / Broker | Redis 7 |
| Task Queue | Celery |
| Migrations | Alembic |
| Auth | python-jose (JWT), passlib (bcrypt) |
| Rate Limiting | slowapi (Fixed Window) |
| Testing | pytest, pytest-asyncio, httpx |

## Prerequisites

- Docker + Docker Compose (or [OrbStack](https://orbstack.dev) on macOS — uses the same `docker compose` commands)
- Python 3.12+ (for local dev without Docker)

## Quick Start (Docker Compose)

```bash
# 1. Clone the repo and enter the project directory
git clone <repo-url>
cd url-shortener

# 2. Create your .env file
cp .env.example .env
# Edit .env and set a strong SECRET_KEY

# 3. Start all services
docker compose up --build

# 4. The API is now available at http://localhost:8000
# Interactive docs: http://localhost:8000/docs
```

## Local Development (without Docker)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Copy and configure environment
cp .env.example .env
# Edit DATABASE_URL and REDIS_URL to point to your local instances

# 4. Run database migrations
alembic upgrade head

# 5. Start the API server
uvicorn app.main:app --reload

# 6. Start a Celery worker (separate terminal)
celery -A app.tasks.celery_app worker --loglevel=info
```

## Running Tests

Unit tests run without any external services — all database and Redis calls are mocked. Integration tests require a live PostgreSQL and Redis instance.

```bash
# Unit tests only (no DB or Redis required — fully mocked)
pytest tests/unit/ -v

# Integration tests (requires running Postgres + Redis)
# Ensure the test DB exists first: createdb urlshortener_test
pytest tests/integration/ -v

# All tests with coverage report
pytest tests/ --cov=app --cov-report=term-missing
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://urluser:urlpass@localhost:5432/urlshortener` | PostgreSQL async DSN |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `SECRET_KEY` | *(required)* | JWT signing secret (min 32 chars) |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `SHORT_CODE_LENGTH` | `7` | Auto-generated alias length (base62) |
| `ALIAS_MAX_LENGTH` | `50` | Maximum length for custom aliases |
| `RATE_LIMIT_LINKS_CREATE` | `20/minute` | Rate limit for POST /api/v1/links |
| `RATE_LIMIT_REDIRECT` | `200/minute` | Rate limit for GET /{alias} |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Reference

### Auth (Tokens)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/tokens` | Login — returns access + refresh tokens | Public |
| PUT | `/api/v1/tokens` | Refresh access token | — |
| DELETE | `/api/v1/tokens` | Logout — revoke refresh token | Bearer |

### Users

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/users` | Register a new user | Public |
| GET | `/api/v1/users` | List all users (paginated) | Admin |
| GET | `/api/v1/users/{id}` | Get user details | Admin |
| DELETE | `/api/v1/users/{id}` | Delete user + their links | Admin |

### Links

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/links` | Create a shortened URL | Bearer |
| GET | `/api/v1/links` | List own links (admin sees all) | Bearer |
| GET | `/api/v1/links/{alias}` | Get link metadata | Bearer (owner or admin) |
| PUT | `/api/v1/links/{alias}` | Update link | Bearer (owner or admin) |
| DELETE | `/api/v1/links/{alias}` | Delete link | Bearer (owner or admin) |

### Analytics

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/api/v1/links/{alias}/stats` | Click stats for a link | Bearer (owner or admin) |

### Redirect & Health

| Method | Path | Description |
|---|---|---|
| GET | `/{alias}` | Redirect to original URL (302) |
| GET | `/api/v1/health` | Service health check |

Full interactive documentation is available at `/docs` when the server is running.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the request lifecycle diagrams and data model.

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push and pull request:
1. **Lint** — ruff
2. **Type check** — mypy
3. **Tests** — pytest with PostgreSQL and Redis service containers
4. **Docker build** — verifies the image builds successfully (runs only after tests pass)
