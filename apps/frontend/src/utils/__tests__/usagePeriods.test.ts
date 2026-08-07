import { getUsagePeriodOptions } from '../usagePeriods';

describe('getUsagePeriodOptions', () => {
  it('leads with a null-valued "Current period" option', () => {
    const options = getUsagePeriodOptions(new Date('2026-08-15T00:00:00Z'));

    expect(options[0]).toEqual({ value: null, label: 'Current period' });
  });

  it('lists the trailing 12 completed months, newest first', () => {
    const options = getUsagePeriodOptions(new Date('2026-08-15T00:00:00Z'));

    const months = options.slice(1);
    expect(months).toHaveLength(12);
    expect(months[0]).toEqual({ value: '2026-07-01', label: 'July 2026' });
    expect(months[months.length - 1]).toEqual({
      value: '2025-08-01',
      label: 'August 2025',
    });
  });

  it('crosses a year boundary correctly', () => {
    const options = getUsagePeriodOptions(new Date('2026-02-10T00:00:00Z'));

    const months = options.slice(1);
    expect(months[0]).toEqual({ value: '2026-01-01', label: 'January 2026' });
    expect(months[1]).toEqual({
      value: '2025-12-01',
      label: 'December 2025',
    });
  });
});
