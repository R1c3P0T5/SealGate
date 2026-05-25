<div align="center">

# SealGate

[![Stars]][Stars-url]
[![CI]][CI-url]
[![Python]][Python-url]
[![Node]][Node-url]
[![Last Commit]][Last-Commit-url]

</div>

SealGate is a face recognition and hand-gesture access control system — named after the concept of hand seals (結印) as authentication and gate as the controlled entry point. It spans an NVIDIA Jetson device, a FastAPI service, a Vue 3 dashboard, and Raspberry Pi Pico W firmware.

This repository is intended for collaborators building the system, improving the recognition pipeline, extending the API, and maintaining the hardware-facing firmware. It is not packaged as a turnkey consumer door-lock product.

## Project Goals

- Provide a maintainable full-stack codebase for face-based access control research and prototyping.
- Keep backend, frontend, firmware, and face-recognition utilities in one repository so API and device contracts can evolve together.
- Make local development predictable through documented setup, generated API clients, pre-commit checks, and CI.
- Separate authentication, user management, face data, and hardware control concerns clearly enough for contributors to work in parallel.

## Architecture

```text
┌────────────────────────┐
│   Camera / Jetson      │
│   face capture &       │
│   recognition          │
└───────────┬────────────┘
            │
            ▼
┌─────────────────────────────┐      ┌────────────────────────┐
│       FastAPI backend       │◄────►│    Vue 3 dashboard     │
│  auth · face · logs · mqtt  │      │    admin interface     │
└───────────┬─────────────────┘      └────────────────────────┘
            │
            ▼
┌───────────────────────┐
│   Pico W firmware     │
└───────────┬───────────┘
            │
            ▼
       Lock hardware
```

The backend owns authentication, user records, role checks, image-based face verification, access logging, MQTT door-control publishing, and the OpenAPI contract. The frontend consumes the generated TypeScript client and provides the administrative dashboard. The firmware target is the networked lock-controller surface for the Pico W. The scripts directory contains face-registration, recognition, and training utilities used for local testing around the Jetson runtime.

## Features

- **Face enrollment and recognition workflow** - video-based registration and local recognition/training utilities.
- **FastAPI authentication service** - JWT login, Argon2id password hashing, role-based access, and async SQLModel persistence.
- **Admin dashboard** - Vue 3 interface for user management, face records, settings, and access-log views.
- **Generated API client** - OpenAPI output from the backend is used to generate typed frontend API calls.
- **Pico W firmware target** - C/CMake firmware project for the Wi-Fi lock-controller side of the system.
- **Contributor checks** - Ruff, pyright, ESLint, oxlint, oxfmt, vue-tsc, Vitest, pytest, commit-message validation, and pre-commit integration.

## Technology Stack

| Layer | Technologies |
| ----- | ------------ |
| Backend | [FastAPI](https://fastapi.tiangolo.com/), [SQLModel](https://sqlmodel.tiangolo.com/), SQLAlchemy async, SQLite, Alembic, JWT, Argon2id, NumPy, aiomqtt |
| Frontend | [Vue 3](https://vuejs.org/), [Vite](https://vite.dev/), Pinia, Vue Router, TypeScript, Tailwind CSS, Histoire |
| Firmware | C/C++, [Pico SDK](https://github.com/raspberrypi/pico-sdk), lwIP, CMake |
| Face tools | Python scripts for capture, recognition, SVM training, and model/data preparation |
| Tooling | uv, pnpm, Ruff, pyright, pytest, Vitest, ESLint, oxlint, oxfmt, vue-tsc, pre-commit, GitHub Actions |

## Repository Layout

```text
sealgate/
├── backend/       # FastAPI app, domain modules, Alembic migrations, pytest suite
├── frontend/      # Vue 3 app, component library, generated API client, Vitest tests
├── firmware/      # Raspberry Pi Pico W firmware built with CMake and Pico SDK
├── scripts/       # Face registration, recognition, training, and validation helpers
├── docs/          # Commit and pre-commit contributor documentation
├── DEVELOPMENT.md # Local setup, API generation, hooks, and CI guide
└── README.md      # Project overview for contributors
```

## Development Entry Points

Start with [DEVELOPMENT.md](./DEVELOPMENT.md) for the full contributor workflow, including environment variables, command references, generated API client updates, pre-commit hooks, and CI behavior.

Use the subproject READMEs when working inside one runtime target:

- [backend/README.md](./backend/README.md) - FastAPI app structure, local backend setup, migrations, tests, API docs, and backend troubleshooting.
- [frontend/README.md](./frontend/README.md) - Vue app structure, Vite proxy behavior, generated API client usage, component stories, tests, linting, and frontend troubleshooting.
- [jetson/README.md](./jetson/README.md) - Jetson worker setup, environment configuration, model download, and camera troubleshooting.

The shortest local path is:

```bash
cd backend
uv sync --dev
cp .env.example .env
uv run alembic upgrade head
uv run fastapi dev main.py
```

```bash
cd frontend
pnpm install
pnpm dev
```

Run focused checks while developing, then run `uvx pre-commit run --all-files` before review.

## Contributing

Please read [DEVELOPMENT.md](./DEVELOPMENT.md), [docs/pre-commit.md](./docs/pre-commit.md), and [docs/commit-msg.md](./docs/commit-msg.md) before opening a pull request.

Before submitting changes:

1. Create a focused branch from `main`.
2. Keep changes scoped to one behavior, workflow, or documentation topic.
3. Add or update tests when backend, frontend, or firmware behavior changes.
4. Regenerate the frontend API client when backend API contracts change.
5. Run focused checks while developing, then run `uvx pre-commit run --all-files` before review.
6. Use the commit format `type(scope): subject` or `type: subject`, with a lowercase imperative subject.

Pull request descriptions should summarize the behavior change, list verification commands, link related issues, and include screenshots for UI changes.

## Notes for Hardware and Security Work

This project touches physical access control concepts. Treat hardware control, authentication logic, face data, and logs as sensitive areas.

- Do not commit secrets, local databases, captured face data, generated firmware outputs, or environment files.
- Keep `SECRET_KEY` at least 32 characters and set it only in local or deployment environment files.
- Prefer explicit test coverage for authorization, role checks, migrations, generated API changes, and firmware/backend protocol changes.
- Document hardware assumptions when changing firmware behavior or lock-controller APIs.

## Star History

<a href="https://www.star-history.com/?repos=R1c3P0T5%2Fsealgate&type=date&legend=bottom-right">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=R1c3P0T5/sealgate&type=date&theme=dark&legend=bottom-right" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=R1c3P0T5/sealgate&type=date&legend=bottom-right" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=R1c3P0T5/sealgate&type=date&legend=bottom-right" />
 </picture>
</a>

[Stars]: https://img.shields.io/github/stars/R1c3P0T5/sealgate?color=fafafa&logo=github&logoColor=fff&style=for-the-badge
[Stars-url]: https://github.com/R1c3P0T5/sealgate/stargazers
[CI]: https://img.shields.io/github/actions/workflow/status/R1c3P0T5/sealgate/pre-commit.yml?label=ci&style=for-the-badge&logo=githubactions&logoColor=fff
[CI-url]: https://github.com/R1c3P0T5/sealgate/actions/workflows/pre-commit.yml
[Python]: https://img.shields.io/badge/python-3.10+-3776ab?style=for-the-badge&logo=python&logoColor=fff
[Python-url]: https://www.python.org/
[Node]: https://img.shields.io/badge/node-20+-5fa04e?style=for-the-badge&logo=nodedotjs&logoColor=fff
[Node-url]: https://nodejs.org/
[Last Commit]: https://img.shields.io/github/last-commit/R1c3P0T5/sealgate?style=for-the-badge&logo=git&logoColor=fff
[Last-Commit-url]: https://github.com/R1c3P0T5/sealgate/commits/main
