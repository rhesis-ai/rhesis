# Rhesis Frontend

Next.js app for the Rhesis web UI (TypeScript, Material UI, NextAuth). Dependencies are listed in `package.json` and installed with **npm**. The production **Dockerfile** uses **Node 24**; use a compatible Node locally.

## Design System (UI Revamp — 2026-05)

The UI was migrated to a Figma-aligned design system in `feat/frontend-ui-revamp`. Key changes:

- **Tokens** — `src/styles/theme.ts` now includes a `greyscale` palette ramp (`title`, `body`, `subtitle`, `border`, `surface1/2`), Figma typography variants (`bodyLReg`, `bodyMReg`, `bodyMBold`, `bodySReg`, `captionBold`), and full elevation scale (`ELEVATION.xs/s/m/l/xl`). See `src/styles/rhesis-theme-usage.md` for usage examples.
- **Layout shell** — Toolpad `DashboardLayout` replaced by `AppShell` + `Sidebar` (CSS-grid, 240px collapsible sidebar, `NavigationItemsContext`). No more `@toolpad/core` dependency.
- **Shared components** — `Fab`, `Toolbar`, `PageLayout` are new. `BaseTable`, `BaseDataGrid`, `BaseDrawer`, `SearchAndFilterBar`, `StatusChip` updated for Figma spec.
- **Pages** — All 45 protected pages migrated from `PageContainer` to `PageLayout`. Typography tokens applied throughout.
- **Figma audit** — `docs/ui-revamp/figma-audit.md` documents all foundation tokens, component mappings, and screen references.

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
