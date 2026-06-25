/**
 * Single source of truth for frontend extension registries.
 *
 * Each file in this directory publishes one named seam where EE (or any
 * future plugin package) can register UI elements without core importing
 * from `@ee/*`. To discover available seams, run `ls` on this directory.
 *
 * Adding a new seam
 * -----------------
 * 1. Create `<seam-name>.ts` in this directory exposing
 *    `register<SeamName>Item`, `get<SeamName>Items`, and an internal
 *    module-level array.
 * 2. Re-export the public API from this file.
 * 3. Modify the core component that renders the seam's UI surface to
 *    iterate `get<SeamName>Items()` and render each item.
 * 4. Document the seam in `ee/frontend/README.md` so EE authors find it.
 *
 * Each seam follows the same shape (id, idempotent registration, sorted
 * read, test-only reset) so the playbook stays mechanical.
 */

export {
  registerOrgSettingsSection,
  getOrgSettingsSections,
  resetOrgSettingsSections,
} from './organization-settings';
export type { OrgSettingsSection } from './organization-settings';

export {
  registerAdminNavItem,
  getAdminNavItems,
  resetAdminNavItems,
} from './admin-nav';
export type { AdminNavItem } from './admin-nav';
