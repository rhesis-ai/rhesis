/** Week or list view of the Schedules tab, remembered per viewer. */
export type SchedulesView = 'week' | 'list';

export const SCHEDULES_VIEW_KEY = 'rhesis.schedules.view';

/** The remembered view, or null when none is saved or storage is blocked. */
export function readRememberedView(): SchedulesView | null {
  try {
    const saved = window.localStorage.getItem(SCHEDULES_VIEW_KEY);
    return saved === 'week' || saved === 'list' ? saved : null;
  } catch {
    // Private mode or blocked storage.
    return null;
  }
}
