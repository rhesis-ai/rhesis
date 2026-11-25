// Kept apart from SettingsTabs so the route's loading view can draw the same
// tabs without pulling the page in.

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
