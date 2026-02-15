import { getImportErrorMessage } from '../import-error-utils';

describe('getImportErrorMessage', () => {
  it('returns fallback for 5xx errors', () => {
    const error = { status: 502, message: 'Bad Gateway' };
    expect(getImportErrorMessage(error)).toBe(
      'Import failed. Please try again.'
    );
  });

  it('returns err.message when no detail is present', () => {
    const error = { message: 'Network error' };
    expect(getImportErrorMessage(error)).toBe('Network error');
  });

  it('returns fallback when error has no message or detail', () => {
    expect(getImportErrorMessage({})).toBe('Import failed. Please try again.');
  });

  it('returns custom fallback', () => {
    expect(getImportErrorMessage({}, 'Custom fallback')).toBe(
      'Custom fallback'
    );
  });

  it('handles detail as string', () => {
    const error = { data: { detail: 'File too large' } };
    expect(getImportErrorMessage(error)).toBe('File too large');
  });

  it('handles detail as { message, errors }', () => {
    const error = {
      data: {
        detail: {
          message: 'Validation failed',
          errors: ['Field A is required', 'Field B is invalid'],
        },
      },
    };
    expect(getImportErrorMessage(error)).toBe(
      'Validation failed Field A is required; Field B is invalid'
    );
  });

  it('handles detail as array (422 validation)', () => {
    const error = {
      data: {
        detail: [
          { loc: ['body', 'name'], msg: 'field required' },
          { loc: ['body', 'url'], msg: 'invalid url' },
        ],
      },
    };
    expect(getImportErrorMessage(error)).toBe(
      'body.name: field required. body.url: invalid url'
    );
  });

  it('truncates long messages', () => {
    const longMessage = 'a'.repeat(400);
    const error = { data: { detail: longMessage } };
    const result = getImportErrorMessage(error);
    expect(result.length).toBeLessThanOrEqual(301); // 300 + ellipsis char
  });

  it('returns fallback for null/undefined detail', () => {
    const error = { data: { detail: null } };
    expect(getImportErrorMessage(error)).toBe(
      'Import failed. Please try again.'
    );
  });
});
