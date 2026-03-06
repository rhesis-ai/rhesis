import { getApiErrorMessage } from '../error-utils';

describe('getApiErrorMessage', () => {
  it('strips the "API error: {status} - " prefix', () => {
    const error = new Error('API error: 400 - Invalid input');
    expect(getApiErrorMessage(error, 'fallback')).toBe('Invalid input');
  });

  it('strips prefix with various HTTP status codes', () => {
    expect(
      getApiErrorMessage(new Error('API error: 404 - Not found'), 'fb')
    ).toBe('Not found');
    expect(
      getApiErrorMessage(new Error('API error: 422 - Validation error'), 'fb')
    ).toBe('Validation error');
    expect(
      getApiErrorMessage(
        new Error('API error: 503 - Service unavailable'),
        'fb'
      )
    ).toBe('Service unavailable');
  });

  it('returns the raw message for non-API errors', () => {
    const error = new Error('Connection refused');
    expect(getApiErrorMessage(error, 'fallback')).toBe('Connection refused');
  });

  it('returns fallback when the detail portion after the prefix is empty', () => {
    const error = new Error('API error: 500 - ');
    expect(getApiErrorMessage(error, 'fallback')).toBe('fallback');
  });

  it('returns fallback when error is a plain string', () => {
    expect(getApiErrorMessage('some string', 'fallback')).toBe('fallback');
  });

  it('returns fallback when error is null', () => {
    expect(getApiErrorMessage(null, 'fallback')).toBe('fallback');
  });

  it('returns fallback when error is undefined', () => {
    expect(getApiErrorMessage(undefined, 'fallback')).toBe('fallback');
  });

  it('returns fallback when error is a number', () => {
    expect(getApiErrorMessage(42, 'fallback')).toBe('fallback');
  });

  it('returns fallback when error is a plain object', () => {
    expect(getApiErrorMessage({ message: 'oops' }, 'fallback')).toBe(
      'fallback'
    );
  });

  it('uses the provided fallback string in each case', () => {
    expect(getApiErrorMessage(null, 'custom fallback message')).toBe(
      'custom fallback message'
    );
  });
});
