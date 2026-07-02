/**
 * Registry of extension tabs rendered on the Organization Settings page.
 *
 * Core renders two built-in tabs (Information, Danger zone). Every
 * other tab — SSO, API, Roles, and any future EE feature — registers
 * itself here at startup. The settings page merges dynamic tabs into
 * the built-in list by `order`.
 *
 * Usage from EE
 * -------------
 * ```ts
 * import { registerOrgSettingsTab } from '@/lib/extension-registries';
 *
 * registerOrgSettingsTab({
 *   id: 'roles',
 *   title: 'Roles',
 *   order: 150,
 *   component: RolesTabGated,
 * });
 * ```
 */

import type { ComponentType } from 'react';

export interface OrgSettingsTab {
  /** Unique identifier (used for de-duplication, React keys, and URL `?tab=` param). */
  id: string;
  /** Tab label displayed in the tab navigation. */
  title: string;
  /**
   * The React component that renders the tab body. Receives no
   * props — read from `useOrgSettings()` and apply your own
   * `<FeatureGate>` wrapping inside the component.
   */
  component: ComponentType;
  /**
   * Sort order relative to other tabs. Built-in orders:
   * Information=0, Danger zone=999. Current EE tabs:
   * SSO=50, API=60, Roles=150.
   */
  order: number;
}

const _tabs: OrgSettingsTab[] = [];
let _cache: readonly OrgSettingsTab[] | null = null;

/**
 * Register a settings tab. Idempotent: re-registering the same `id`
 * is a no-op so EE bootstrap can run safely under React Strict Mode
 * and Next.js fast refresh without producing duplicates.
 */
export function registerOrgSettingsTab(tab: OrgSettingsTab): void {
  if (_tabs.some(t => t.id === tab.id)) return;
  _tabs.push(tab);
  _cache = null;
}

/**
 * Read the current set of registered tabs, sorted by `order`.
 * Returns a frozen, cached array so referential identity is stable
 * across calls until a new registration happens.
 */
export function getOrgSettingsTabs(): readonly OrgSettingsTab[] {
  if (_cache === null) {
    _cache = Object.freeze([..._tabs].sort((a, b) => a.order - b.order));
  }
  return _cache;
}

/** Reset the registry. Intended for tests only. */
export function resetOrgSettingsTabs(): void {
  _tabs.length = 0;
  _cache = null;
}
