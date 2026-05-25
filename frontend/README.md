# SealGate Frontend

Vue 3 dashboard for SealGate administration.

The frontend provides login, dashboard, face records, settings, access-log
views, and shared UI components. It consumes a generated TypeScript client from
the backend OpenAPI schema.

For repository-wide setup, pre-commit hooks, CI behavior, and generated API
client workflow, see [../DEVELOPMENT.md](../DEVELOPMENT.md). This file focuses
on frontend-specific structure and operating notes.

## Setup

Requirements: Node.js `^20.19.0 || >=22.12.0` and pnpm 10.x.

Install dependencies from the `frontend/` directory:

```bash
pnpm install
```

Start the development server:

```bash
pnpm dev
```

The Vite dev server runs at `http://localhost:5173`. Requests to `/api/*` are
proxied to `http://localhost:8000`, so start the backend before using API-backed
views.

## Project Structure

```text
frontend/
├── src/
│   ├── api/              # Generated OpenAPI TypeScript client
│   ├── layouts/          # Authenticated and unauthenticated page shells
│   ├── lib/components/   # Shared UI components, tests, and Histoire stories
│   ├── router/           # Vue Router configuration
│   ├── stores/           # Pinia stores
│   └── views/            # Route-level dashboard views
├── public/               # Static assets
├── openapi-ts.config.ts  # API client generator config
├── vite.config.ts        # Vite plugins, aliases, and dev proxy
└── package.json          # Scripts, dependencies, and engine constraints
```

## Generated API Client

`src/api/` is generated from `../openapi.json` through `@hey-api/openapi-ts`.
Do not hand-edit generated files.

When backend API contracts change, run this from the repository root:

```bash
bash scripts/generate-api.sh
```

Commit backend contract or generator configuration changes, and regenerate the
client locally when needed.

## Development Commands

```bash
pnpm dev            # start Vite at http://localhost:5173
pnpm build          # type-check and build production assets
pnpm test:unit      # run Vitest unit tests
pnpm lint
pnpm format
pnpm type-check
pnpm story:dev      # launch Histoire component stories
```

## Tooling Notes

Use [Vue - Official](https://marketplace.visualstudio.com/items?itemName=Vue.volar)
for editor support. Type checking uses `vue-tsc` because TypeScript does not
understand `.vue` files by itself.

Shared components should keep colocated `*.spec.ts` tests and `*.story.vue`
stories when practical. The generated API directory is ignored by frontend
linting because it is machine-produced.

## Troubleshooting

If API calls fail in local development, confirm the backend is running at
`http://localhost:8000` and that the request path starts with `/api`.

If generated API imports are missing, run `bash scripts/generate-api.sh` from
the repository root.

If TypeScript cannot resolve `.vue` imports in the editor, use the Vue Official
extension and disable older Vetur-based Vue tooling.
