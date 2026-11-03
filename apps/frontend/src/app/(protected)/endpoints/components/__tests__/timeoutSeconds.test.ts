import { parseTimeoutSeconds, timeoutSecondsError } from '../timeoutSeconds';

describe('timeoutSeconds', () => {
  it.each(['', '  ', '1', '120', '3600'])('accepts %j', value => {
    expect(timeoutSecondsError(value)).toBeNull();
  });

  it.each(['0', '-5', '3601', '1.5', 'abc'])('rejects %j', value => {
    expect(timeoutSecondsError(value)).toBe(
      'Enter whole seconds from 1 to 3600.'
    );
  });

  it('parses only a valid value, leaving empty to the default', () => {
    expect(parseTimeoutSeconds('120')).toBe(120);
    expect(parseTimeoutSeconds('')).toBeUndefined();
    expect(parseTimeoutSeconds('3601')).toBeUndefined();
    expect(parseTimeoutSeconds('1.5')).toBeUndefined();
  });
});
