/**
 * Registry of extension sections rendered on the Organization Settings page.
 *
 * Core renders a fixed set of built-in sections (Basic Information, Contact
 * Information, Danger Zone). Any additional section -- typically owned by an
 * EE feature like SSO -- registers itself here at startup. The settings page
 * then iterates the registry and renders each entry.
 *
 * Contract design
 * ---------------
 * Sections are stored as `ComponentType` only -- no props. Per-render data
 * (the current organization, session token, refresh callback) is published
 * by the settings page through `OrgSettingsContext`; sections call
 * `useOrgSettings()` to reach it. Likewise, license gating is the section's
 * own responsibility -- EE wraps its component in `<FeatureGate>` before
 * registering rather than the registry having a `feature` field. Both
 * choices keep the registry contract minimal so future sections do not
 * force contract changes on existing ones.
 *
 * Usage from EE
 * -------------
 * ```ts
 * // In ee/frontend/src/<feature>/register.ts
 * import { FeatureGate } from '@/contexts/FeaturesContext';
 * import { FeatureName } from '@/constants/features';
 * import { registerOrgSettingsSection } from '@/lib/extension-registries';
 * import MyFeatureForm from './components/MyFeatureForm';
 *
 * registerOrgSettingsSection({
 *   id: 'my-feature',
 *   title: 'My Feature',
 *   order: 100,
 *   component: () => (
 *     <FeatureGate feature={FeatureName.MY_FEATURE}>
 *       <MyFeatureForm />
 *     </FeatureGate>
 *   ),
 * });
 * ```
 */

import type { ComponentType } from 'react';

export interface OrgSettingsSection {
  /** Unique identifier (used for de-duplication and React keys). */
  id: string;
  /** Heading displayed at the top of the section's card. */
  title: string;
  /**
   * The React component that renders the section body. Receives no
   * props -- read from `useOrgSettings()` and apply your own
   * `<FeatureGate>` wrapping inside the component.
   */
  component: ComponentType;
  /**
   * Sort order. Lower numbers render earlier. Sections without an order
   * fall to the end in registration order.
   */
  order?: number;
}

const _sections: OrgSettingsSection[] = [];
let _cache: readonly OrgSettingsSection[] | null = null;

/**
 * Register a settings section. Idempotent: re-registering the same `id`
 * is a no-op so EE bootstrap can run safely under React Strict Mode and
 * Next.js fast refresh without producing duplicates.
 */
export function registerOrgSettingsSection(section: OrgSettingsSection): void {
  if (_sections.some(s => s.id === section.id)) return;
  _sections.push(section);
  _cache = null;
}

/**
 * Read the current set of registered sections, sorted by `order`.
 * Returns a frozen, cached array so referential identity is stable
 * across calls until a new registration happens. Stable identity means
 * consumers can safely depend on the result inside `useEffect`,
 * `useMemo`, etc. without infinite re-renders.
 */
export function getOrgSettingsSections(): readonly OrgSettingsSection[] {
  if (_cache === null) {
    _cache = Object.freeze(
      [..._sections].sort((a, b) => {
        const ao = a.order ?? Number.MAX_SAFE_INTEGER;
        const bo = b.order ?? Number.MAX_SAFE_INTEGER;
        return ao - bo;
      })
    );
  }
  return _cache;
}

/** Reset the registry. Intended for tests only. */
export function resetOrgSettingsSections(): void {
  _sections.length = 0;
  _cache = null;
}
