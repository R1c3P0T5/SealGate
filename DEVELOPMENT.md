# Development Guide

This guide covers cross-project contributor workflows: environment variables, command references, generated API client updates, pre-commit hooks, and CI/CD internals. For project overview and architecture, see [README.md](./README.md). For runtime-specific notes, see [backend/README.md](./backend/README.md) and [frontend/README.md](./frontend/README.md).

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in the required values.

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `SECRET_KEY` | **yes** | — | JWT signing key, minimum 32 characters. Generate with `openssl rand -hex 32`. |
| `DATABASE_URL` | no | `sqlite+aiosqlite:///./sealgate.db` | SQLAlchemy async database URL. |
| `DEBUG` | no | `False` | Enable FastAPI debug mode and auto-reload. |
| `JWT_ALGORITHM` | no | `HS256` | JWT signing algorithm. |
| `JWT_EXPIRATION_HOURS` | no | `24` | Access token lifetime in hours. |
| `DEFAULT_ADMIN_USERNAME` | no | — | Seed an admin account on first startup. Must be set together with `DEFAULT_ADMIN_PASSWORD`. |
| `DEFAULT_ADMIN_PASSWORD` | no | — | Password for the seeded admin account. |
| `DEFAULT_ADMIN_FULL_NAME` | no | — | Display name for the seeded admin account. |
| `DEFAULT_ADMIN_EMAIL` | no | — | Email for the seeded admin account. |

## Backend Commands

```bash
uv run fastapi dev main.py              # start dev server at http://localhost:8000
uv run python scripts/download_models.py  # download YuNet/SFace ONNX files
uv run pytest tests -v                  # run tests
uv run pytest tests --cov               # run tests with coverage report
uv run pyright main.py src tests alembic  # type-check all entry points
uv run alembic upgrade head             # apply pending migrations
uv run alembic revision --autogenerate -m "describe change"  # generate a new migration
uv run alembic downgrade -1             # roll back one migration
```

## Frontend Commands

```bash
pnpm dev            # start Vite dev server at http://localhost:5173
pnpm build          # production build (includes vue-tsc type check)
pnpm test:unit      # run Vitest unit tests
pnpm lint           # run ESLint + oxlint
pnpm format         # format source files with oxfmt
pnpm type-check     # run vue-tsc standalone
pnpm story:dev      # launch Histoire component story browser
pnpm generate:api   # regenerate frontend/src/api/ from openapi.json
```

API requests to `/api/*` are proxied to `http://localhost:8000` by the Vite dev server config. Start the backend before running the frontend.

## API Client Workflow

The frontend API client is generated from the backend OpenAPI schema into
`frontend/src/api/`. This directory is intentionally ignored by Git.

When backend routes, request models, response models, or authentication
contracts change, regenerate the client locally before running frontend checks:

```bash
bash scripts/generate-api.sh
```

The script exports the current backend OpenAPI schema to `openapi.json`, then runs the frontend generator to update `frontend/src/api/`.

Commit backend contract changes and any OpenAPI schema or generator
configuration updates, not the generated `frontend/src/api/` files.

## Pre-commit Hooks

Install hooks once per clone before making your first commit:

```bash
uvx pre-commit install --install-hooks
```

This installs both the `pre-commit` and `commit-msg` hooks. Run all hooks manually with:

```bash
uvx pre-commit run --all-files   # check everything
uvx pre-commit run               # check staged files only
```

| Hook | Applies to | What it checks |
| ---- | ---------- | -------------- |
| `ruff-check` | `backend/` | Python linting (auto-fixes safe issues) |
| `ruff-format` | `backend/` | Python formatting |
| `pyright` | `backend/` | Python type checking |
| `oxfmt` | `frontend/` | TypeScript/Vue formatting |
| `eslint` + `oxlint` | `frontend/` | TypeScript/Vue linting |
| `vue-tsc` | `frontend/` | TypeScript type checking for Vue components |
| `commit-message-check` | commit message | Header format: `type(scope): subject` |
| General | all files | Trailing whitespace, large files, JSON/YAML syntax |

## CI/CD

Two GitHub Actions workflows run on every push and pull request.

### `pre-commit.yml`

Sets up Python + uv + Node.js + pnpm, regenerates the API client with `scripts/generate-api.sh`, then runs all pre-commit hooks against every file.

This workflow fails if:

- Any linter, formatter, or type checker reports an error.
- API generation fails, leaving frontend checks without the generated `frontend/src/api/` client.

If you see this failure locally, run `bash scripts/generate-api.sh`, verify the frontend checks pass, and commit only the source files that define the API contract or generator behavior.

### `commit-message.yml`

Validates every commit message in the push against the header format. Fails if any message does not match `type(scope): subject` or `type: subject`.

See [docs/commit-msg.md](./docs/commit-msg.md) for the full type list, scope conventions, and body writing guide.
