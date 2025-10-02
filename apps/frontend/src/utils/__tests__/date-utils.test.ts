import { formatDate } from '../date-utils';

describe('date-utils', () => {
  describe('formatDate', () => {
    it('formats ISO date string correctly', () => {
      const dateString = '2024-01-15T14:30:00Z';
      const result = formatDate(dateString);

      // Check that it returns a formatted string
      expect(typeof result).toBe('string');
      // The exact format may vary by locale, so we check for common patterns
      expect(result).toMatch(/January.*2024/); // Should contain month and year
      expect(result).toMatch(/15/); // Should contain day
    });

    it('formats Date object correctly', () => {
      const date = new Date('2024-01-15T14:30:00Z');
      const result = formatDate(date);

      expect(typeof result).toBe('string');
      expect(result).toMatch(/January.*2024/);
      expect(result).toMatch(/15/);
    });

    it('handles date with different timezone', () => {
      const dateString = '2024-06-15T09:15:30-05:00'; // EST timezone
      const result = formatDate(dateString);

      expect(typeof result).toBe('string');
      expect(result).toMatch(/June.*2024/);
      expect(result).toMatch(/15/);
    });

    it('formats date with milliseconds', () => {
      const dateString = '2024-03-20T12:45:30.123Z';
      const result = formatDate(dateString);

      expect(typeof result).toBe('string');
      expect(result).toMatch(/March.*2024/);
      expect(result).toMatch(/20/);
    });

    it('handles edge case dates', () => {
      const newYear = '2024-01-01T00:00:00Z';
      const christmas = '2024-12-25T23:59:59Z';

      const newYearResult = formatDate(newYear);
      const christmasResult = formatDate(christmas);

      expect(newYearResult).toMatch(/January.*2024/);
      expect(christmasResult).toMatch(/December.*2024/);
    });

    it('maintains consistent formatting', () => {
      const date1 = '2024-01-15T08:30:00Z';
      const date2 = '2024-01-15T08:30:00Z';

      const result1 = formatDate(date1);
      const result2 = formatDate(date2);

      expect(result1).toBe(result2);
    });

    it('returns consistent length for different dates', () => {
      const date1 = '2024-01-01T00:00:00Z';
      const date2 = '2024-12-31T23:59:59Z';

      const result1 = formatDate(date1);
      const result2 = formatDate(date2);

      // Both should be formatted strings of reasonable length
      expect(result1.length).toBeGreaterThan(10);
      expect(result2.length).toBeGreaterThan(10);
      // They should be similar length (both January and December are long month names)
      expect(Math.abs(result1.length - result2.length)).toBeLessThan(5);
    });
  });
});
