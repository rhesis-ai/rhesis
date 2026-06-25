/**
 * EE frontend bootstrap.
 *
 * Called once from `apps/frontend/src/ee_bootstrap.ts` at module load.
 * Each EE feature exposes a sibling `register*` function; this file
 * just calls them in order. Adding a new feature is a self-contained
 * two-line edit (one import, one call) and keeps cross-feature noise
 * out of the bootstrap.
 *
 * Idempotency
 * -----------
 * Each registry helper in `@/lib/extension-registries` deduplicates
 * by `id`, so running this bootstrap multiple times (server bundle,
 * client bundle, fast refresh, React Strict Mode) does not produce
 * duplicate sections or nav items.
 */

import { registerApiClients } from './api-clients/register';
import { registerSSO } from './sso/register';

export function bootstrapEE(): void {
  registerSSO();
  registerApiClients();
}
