import { formatDate } from '../date';

describe('formatDate', () => {
  it('returns "N/A" for undefined', () => {
    expect(formatDate(undefined)).toBe('N/A');
  });

  it('returns "N/A" for empty string', () => {
    expect(formatDate('')).toBe('N/A');
  });

  it('formats a Date object', () => {
    const date = new Date('2024-06-15T14:30:00Z');
    const result = formatDate(date);
    // Should contain the date parts (exact format depends on locale)
    expect(result).toContain('2024');
    expect(result).toContain('Jun');
    expect(result).toContain('15');
  });

  it('formats a date string', () => {
    const result = formatDate('2024-01-01T00:00:00Z');
    expect(result).toContain('2024');
    expect(result).toContain('Jan');
  });
});
