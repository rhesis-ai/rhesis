import { formatDuration } from '../format-duration';

describe('formatDuration', () => {
  it('formats sub-millisecond values as microseconds', () => {
    expect(formatDuration(0.5)).toBe('500μs');
    expect(formatDuration(0.001)).toBe('1μs');
    expect(formatDuration(0.999)).toBe('999μs');
  });

  it('formats millisecond values', () => {
    expect(formatDuration(1)).toBe('1.00ms');
    expect(formatDuration(150)).toBe('150.00ms');
    expect(formatDuration(999.99)).toBe('999.99ms');
  });

  it('formats second values', () => {
    expect(formatDuration(1000)).toBe('1.00s');
    expect(formatDuration(2500)).toBe('2.50s');
    expect(formatDuration(59999)).toBe('60.00s');
  });

  it('formats minute values', () => {
    expect(formatDuration(60000)).toBe('1.00min');
    expect(formatDuration(150000)).toBe('2.50min');
    expect(formatDuration(3600000)).toBe('60.00min');
  });

  it('handles zero', () => {
    expect(formatDuration(0)).toBe('0μs');
  });

  it('handles boundary values', () => {
    // Just under 1ms
    expect(formatDuration(0.9999)).toBe('1000μs');
    // Exactly 1ms
    expect(formatDuration(1)).toBe('1.00ms');
    // Just under 1s
    expect(formatDuration(999)).toBe('999.00ms');
    // Exactly 1s
    expect(formatDuration(1000)).toBe('1.00s');
    // Exactly 1min
    expect(formatDuration(60000)).toBe('1.00min');
  });
});
