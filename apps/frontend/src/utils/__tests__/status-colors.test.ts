import { getStatusColor, getStatusThemeColor } from '../status-colors';

describe('getStatusColor', () => {
  it.each([
    ['active', 'success'],
    ['completed', 'success'],
    ['success', 'success'],
  ])('maps "%s" to success', (status, expected) => {
    expect(getStatusColor(status)).toBe(expected);
  });

  it.each([
    ['error', 'error'],
    ['failed', 'error'],
    ['failure', 'error'],
  ])('maps "%s" to error', (status, expected) => {
    expect(getStatusColor(status)).toBe(expected);
  });

  it.each([
    ['pending', 'warning'],
    ['in progress', 'warning'],
    ['progress', 'warning'],
    ['partial', 'warning'],
  ])('maps "%s" to warning', (status, expected) => {
    expect(getStatusColor(status)).toBe(expected);
  });

  it.each([
    ['info', 'info'],
    ['running', 'info'],
  ])('maps "%s" to info', (status, expected) => {
    expect(getStatusColor(status)).toBe(expected);
  });

  it('returns default for unknown statuses', () => {
    expect(getStatusColor('unknown')).toBe('default');
    expect(getStatusColor('custom-status')).toBe('default');
  });

  it('is case-insensitive', () => {
    expect(getStatusColor('Active')).toBe('success');
    expect(getStatusColor('FAILED')).toBe('error');
    expect(getStatusColor('Pending')).toBe('warning');
    expect(getStatusColor('INFO')).toBe('info');
  });
});

describe('getStatusThemeColor', () => {
  it('maps success to success.main', () => {
    expect(getStatusThemeColor('active')).toBe('success.main');
  });

  it('maps error to error.main', () => {
    expect(getStatusThemeColor('failed')).toBe('error.main');
  });

  it('maps warning to warning.main', () => {
    expect(getStatusThemeColor('pending')).toBe('warning.main');
  });

  it('maps info to info.main', () => {
    expect(getStatusThemeColor('running')).toBe('info.main');
  });

  it('maps unknown to text.secondary', () => {
    expect(getStatusThemeColor('unknown')).toBe('text.secondary');
  });
});
