// Kept apart from OrganizationSettingsTabs so the route's loading view can
// draw the same tabs without pulling the page in.

import type { ComponentType } from 'react';
import type { OrgSettingsTab } from '@/lib/extension-registries';

export const ORG_SETTINGS_TITLE = 'Organization Settings';
export const ORG_SETTINGS_DESCRIPTION =
  "Manage your organization's profile, contact details, and security settings.";

/** The trail after the organization's own crumb. */
export const ORG_SETTINGS_CRUMB = {
  label: ORG_SETTINGS_TITLE,
  href: '/organizations/settings',
};

export interface BuiltInTab {
  id: string;
  label: string;
  order: number;
  dynamic: false;
}

export interface DynamicTab {
  id: string;
  label: string;
  order: number;
  dynamic: true;
  component: ComponentType;
}

export type MergedTab = BuiltInTab | DynamicTab;

const BUILT_IN_TABS: BuiltInTab[] = [
  { id: 'information', label: 'Information', order: 0, dynamic: false },
  { id: 'branding', label: 'Branding', order: 1, dynamic: false },
  { id: 'preferences', label: 'Preferences', order: 2, dynamic: false },
  { id: 'danger', label: 'Danger zone', order: 999, dynamic: false },
];

const LEGACY_TAB_MAP: Record<string, string> = {
  'sso-api': 'sso',
  // The Preferences tab was called Display until the currency settings were
  // given the same words as the personal ones. Links to ?tab=display are out
  // there, in the docs among other places.
  display: 'preferences',
};

/** Built-in tabs plus the registered ones, sorted by `order`. */
export function mergeOrgSettingsTabs(
  dynamicTabs: readonly OrgSettingsTab[]
): MergedTab[] {
  const merged: MergedTab[] = [
    ...BUILT_IN_TABS,
    ...dynamicTabs.map(
      (t): DynamicTab => ({
        id: t.id,
        label: t.title,
        order: t.order,
        dynamic: true,
        component: t.component,
      })
    ),
  ];
  return merged.sort((a, b) => a.order - b.order);
}

export function resolveTabParam(
  param: string | null,
  validIds: readonly string[]
): string {
  if (param && param in LEGACY_TAB_MAP) {
    return LEGACY_TAB_MAP[param];
  }
  if (param && validIds.includes(param)) {
    return param;
  }
  return 'information';
}

/** Index of the tab `?tab=` selects; the first tab when it names none. */
export function activeTabIndex(
  param: string | null,
  tabIds: readonly string[]
): number {
  const idx = tabIds.indexOf(resolveTabParam(param, tabIds));
  return idx >= 0 ? idx : 0;
}
