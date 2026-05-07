/**
 * Sanctioned bridge from MIT-licensed core to the optional EE frontend.
 *
 * This is the **only** file in `apps/frontend/` that may import from
 * `@rhesis/ee-frontend`. The ESLint rule `no-restricted-imports` enforces
 * this for every other file, and `scripts/check-ee-boundary.mjs` re-checks
 * it in CI. Mirror of `apps/backend/src/rhesis/backend/app/ee_bootstrap.py`
 * on the backend; together those two files are the entire core-to-EE
 * coupling surface.
 *
 * The side-effect import is run once per JS bundle (the module loader
 * memoises it). EE registrations themselves are idempotent inside
 * `bootstrapEE`, so importing this file multiple times across server
 * and client bundles is safe.
 *
 * Removing EE for an MIT-only build
 * ---------------------------------
 * 1. Delete `ee/frontend/`.
 * 2. Replace the body of this file with `export {};` (no-op).
 * 3. Remove the `@rhesis/ee-frontend` dep from `package.json` and the
 *    `transpilePackages` entry from `next.config.mjs`.
 */

import { bootstrapEE } from '@rhesis/ee-frontend';

bootstrapEE();

export {};
