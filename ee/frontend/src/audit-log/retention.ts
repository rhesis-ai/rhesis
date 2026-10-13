/** Retention choices. Bounds mirror `AuditLogSettingsUpdate.retention_days`. */

export const MIN_RETENTION_DAYS = 90;
export const MAX_RETENTION_DAYS = 3650;
const DAYS_PER_YEAR = 365;

export const RETENTION_PRESETS = [
  { days: 90, label: '90 days' },
  { days: 365, label: '1 year' },
  { days: 1095, label: '3 years' },
] as const;

/** "1 year", "3 years", "90 days", "400 days". */
export function retentionLabel(days: number): string {
  if (days % DAYS_PER_YEAR === 0) {
    const years = days / DAYS_PER_YEAR;
    return years === 1 ? '1 year' : `${years} years`;
  }
  return days === 1 ? '1 day' : `${days} days`;
}

export function isPresetRetention(days: number): boolean {
  return RETENTION_PRESETS.some(preset => preset.days === days);
}

/** A whole number of days in the API's range, or null. */
export function parseRetentionDays(value: string): number | null {
  if (!/^\d+$/.test(value.trim())) return null;
  const days = Number(value);
  return days >= MIN_RETENTION_DAYS && days <= MAX_RETENTION_DAYS ? days : null;
}
