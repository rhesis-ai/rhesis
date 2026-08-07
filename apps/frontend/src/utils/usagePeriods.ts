export interface UsagePeriodOption {
  /** First-of-month `YYYY-MM-DD`, or `null` for the current billing period. */
  value: string | null;
  label: string;
}

const TRAILING_MONTHS = 12;

/**
 * Selectable billing periods for the Usage overview filter: the current
 * period plus the trailing 12 completed months, newest first. Matches the
 * backend backfill's own trailing-12-month range (see
 * `9550c62e80a5_extend_usage_backfill_to_trailing_12_.py`), so every
 * option here can actually have data behind it.
 */
export function getUsagePeriodOptions(
  today: Date = new Date()
): UsagePeriodOption[] {
  const options: UsagePeriodOption[] = [
    { value: null, label: 'Current period' },
  ];

  let year = today.getUTCFullYear();
  let month = today.getUTCMonth() + 1;

  for (let i = 0; i < TRAILING_MONTHS; i++) {
    month -= 1;
    if (month === 0) {
      month = 12;
      year -= 1;
    }
    const value = `${year}-${String(month).padStart(2, '0')}-01`;
    const label = new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString(
      'en-US',
      { month: 'long', year: 'numeric', timeZone: 'UTC' }
    );
    options.push({ value, label });
  }

  return options;
}
