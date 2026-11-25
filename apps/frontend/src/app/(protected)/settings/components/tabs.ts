// Kept apart from SettingsTabs so the route's loading view can draw the same
// tabs without pulling the page in.

/** The page header, shared with the loading view. */
export const SETTINGS_HEADER = {
  title: 'Settings',
  description: 'Manage your profile, account and notifications.',
  breadcrumbs: [{ label: 'Settings', href: '/settings' }],
};

export const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'preferences', label: 'Preferences' },
  { id: 'notifications', label: 'Notifications' },
] as const;

const TAB_IDS = TABS.map(t => t.id);

/** Index of the tab `?tab=` selects; the first tab when it names none. */
export function activeTabIndex(param: string | null): number {
  const idx = param ? TAB_IDS.indexOf(param as (typeof TAB_IDS)[number]) : -1;
  return idx >= 0 ? idx : 0;
}

/** Card headings the tabs open with, shared with the loading view. */
export const CARD_HEADINGS = {
  currency: {
    title: 'Currency',
    subtitle:
      "The currency costs are shown in, across traces and test runs. This applies to you only, and overrides the organization's default.",
  },
  emails: {
    title: 'Email notifications',
    subtitle:
      'Choose which emails to receive. The matching in-app notifications keep coming either way.',
  },
  accessibility: {
    title: 'Accessibility',
    subtitle: "Applies to you only, on top of your organization's setting.",
  },
} as const;
