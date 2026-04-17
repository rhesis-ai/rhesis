# Rhesis Frontend

Next.js app for the Rhesis web UI (TypeScript, Material UI, NextAuth). Dependencies are listed in `package.json` and installed with **npm**. The production **Dockerfile** uses **Node 24**; use a compatible Node locally.

## Setup

From `apps/frontend`:

```bash
npm install
```

For a clean install matching CI-style lockfile installs, use `make install` (runs `npm ci --legacy-peer-deps` per `Makefile`).

From the repository root, `./rh dev init` creates `apps/frontend/.env.local` (see `create_frontend_env` in `rh`). Adjust that file for OAuth and other settings.

## Run

- **Repository root:** `./rh dev frontend` — runs `apps/frontend/start.sh`, which starts the dev server (`npm run dev` in development).
- **This directory:** `npm run dev` (or `./start.sh`).

The dev server binds to port **3000** (see `package.json` `dev` script: `next dev … -p 3000`).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for linting, formatting, type checking, and tests.
