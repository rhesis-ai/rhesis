/**
 * Registry of admin-area navigation items.
 *
 * Core builds the sidebar from a fixed list in `app/layout.tsx`. EE features
 * that ship a dedicated admin page (audit log, compliance reports, etc.)
 * register a nav item here at startup. Core's layout reads the registry and
 * appends the items, optionally `<FeatureGate>`-aware via the consuming
 * component.
 *
 * This registry is **preemptive** -- there is no consumer in core today.
 * It exists so the next EE feature that needs a top-level page (likely the
 * audit log) drops in with a single registration call rather than requiring
 * a fresh extension seam to be designed in core.
 *
 * Usage from EE
 * -------------
 * ```ts
 * registerAdminNavItem({
 *   id: 'audit-log',
 *   title: 'Audit Log',
 *   path: '/audit-log',
 *   icon: 'AssessmentIcon',
 *   feature: FeatureName.AUDIT_LOG,
 *   order: 50,
 * });
 * ```
 *
 * The corresponding page lives at
 * `apps/frontend/src/app/(protected)/audit-log/page.tsx` -- a thin
 * re-export of the EE-owned component, which is the only sanctioned way
 * to add EE-owned routes given Next.js' file-based routing.
 */

import type { FeatureName } from '@/constants/features';

export interface AdminNavItem {
  /** Unique identifier (used for de-duplication and React keys). */
  id: string;
  /** Display title. */
  title: string;
  /** App-relative URL path the item links to (e.g. `/audit-log`). */
  path: string;
  /**
   * Icon name (string key, looked up in core's icon registry to avoid
   * shipping MUI icon imports across the boundary). Optional.
   */
  icon?: string;
  /** Optional feature flag that gates visibility. */
  feature?: FeatureName;
  /** Sort order. Lower numbers render earlier. */
  order?: number;
  /** Whether the item requires superuser. Default false. */
  requireSuperuser?: boolean;
}

const _items: AdminNavItem[] = [];
let _cache: readonly AdminNavItem[] | null = null;

export function registerAdminNavItem(item: AdminNavItem): void {
  if (_items.some(i => i.id === item.id)) return;
  _items.push(item);
  _cache = null;
}

/**
 * Read all registered admin nav items, sorted by `order`. Returns a
 * frozen, cached array so referential identity is stable across calls
 * until a new registration happens (safe inside `useEffect` deps etc.).
 *
 * Note: items declare a `feature?: FeatureName` because nav items are
 * pure data -- the consumer (sidebar) filters by feature itself rather
 * than wrapping in `<FeatureGate>` (there is no component to wrap).
 */
export function getAdminNavItems(): readonly AdminNavItem[] {
  if (_cache === null) {
    _cache = Object.freeze(
      [..._items].sort((a, b) => {
        const ao = a.order ?? Number.MAX_SAFE_INTEGER;
        const bo = b.order ?? Number.MAX_SAFE_INTEGER;
        return ao - bo;
      })
    );
  }
  return _cache;
}

export function resetAdminNavItems(): void {
  _items.length = 0;
  _cache = null;
}
