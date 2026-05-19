# Jetson Facelock Backend

FastAPI service handling user authentication, admin user management,
image-based face verification, audit logging, and MQTT door-control publishing
for the Jetson Facelock system.

The backend receives face images, extracts face embeddings internally, matches
them against stored user face vectors, writes an audit log entry, and publishes
the door command on a granted match. See [`../README.md`](../README.md) for the
system-level architecture.

For repository-wide setup, pre-commit hooks, CI behavior, and generated API
client workflow, see [../DEVELOPMENT.md](../DEVELOPMENT.md). This file focuses
on backend-specific structure and operating notes.

## Setup

Use [../DEVELOPMENT.md](../DEVELOPMENT.md) for the canonical local setup and
command reference.

Install development dependencies from the `backend/` directory:

```bash
uv sync --dev
```

Create a local environment file:

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Set the generated value as `SECRET_KEY` in `.env`. See
[../DEVELOPMENT.md](../DEVELOPMENT.md) for the complete environment reference.

Download the YuNet and SFace ONNX models used by the image-based face
endpoints:

```bash
uv run python scripts/download_models.py
```

The files are saved in `backend/models/` and are intentionally ignored by Git.

Initialize or migrate the database:

```bash
uv run alembic upgrade head
```

Start the development server:

```bash
uv run fastapi dev main.py
```

The API is available at `http://localhost:8000`.

Equivalent uvicorn command, useful when debugging server startup directly:

```bash
uv run uvicorn main:app --reload
```

## Environment

See [`.env.example`](./.env.example) for all variables and
[`../DEVELOPMENT.md`](../DEVELOPMENT.md) for the complete reference.

Setting `DEFAULT_ADMIN_USERNAME` and `DEFAULT_ADMIN_PASSWORD` together seeds an
admin user at startup; existing users are not overwritten.

## Project Structure

```text
backend/
├── main.py              # FastAPI app factory and lifespan integration
├── src/
│   ├── auth/            # Registration, login, JWT utilities, auth dependencies
│   ├── users/           # User model, schemas, service layer, CRUD routes
│   ├── faces/           # Face image endpoints, engine, and cosine matching
│   ├── audit/           # Audit log model, routes, and query service
│   └── core/            # Settings, database session setup, exceptions, security
├── tests/               # Unit and integration tests
├── alembic/             # Database migrations
├── .env.example         # Environment template
└── pyproject.toml       # Dependencies and tool configuration
```

## API Documentation

Run the development server and open the generated API documentation:

```text
http://localhost:8000/docs
```

FastAPI also exposes ReDoc at:

```text
http://localhost:8000/redoc
```

The OpenAPI schema is generated from the active application code, so use these
pages as the source of truth for available endpoints, request bodies, response
schemas, and authentication requirements.

## Development

Add dependencies:

```bash
uv add package-name
```

Create a migration after model changes:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Run the full test suite:

```bash
uv run pytest tests -v
```

Run type checking:

```bash
uv run pyright main.py src tests alembic
```

Run coverage:

```bash
uv run pytest tests --cov
```

## Tech Stack

- FastAPI with the standard extras
- SQLModel and SQLAlchemy async sessions
- SQLite with `aiosqlite` for local development
- Alembic migrations
- Argon2id password hashing through `argon2-cffi`
- JWT authentication through `python-jose`
- NumPy for face vector storage and cosine similarity
- aiomqtt for async MQTT publishing to HiveMQ Cloud
- pytest, pytest-asyncio, pytest-cov, httpx, pyright, and ruff

## Troubleshooting

If settings fail with `SECRET_KEY not set or too short`, create `backend/.env`
from `.env.example` and set a generated secret value.

If tests create database files in the project directory, check that tests are
running through the provided `tests/conftest.py` fixtures. The default test
fixtures set `DATABASE_URL` to a per-test temporary database path.

If the server cannot import `main`, run commands from the `backend/` directory.
The app object is `main:app`.

If a database schema looks stale, run:

```bash
uv run alembic upgrade head
```
