import { joinUrl } from '../url';

describe('joinUrl', () => {
  it('joins simple path parts', () => {
    expect(joinUrl('api', 'v1', 'users')).toBe('api/v1/users');
  });

  it('removes leading and trailing slashes from parts', () => {
    expect(joinUrl('/api/', '/v1/', '/users/')).toBe('api/v1/users');
  });

  it('handles single part', () => {
    expect(joinUrl('api')).toBe('api');
  });

  it('filters out empty parts', () => {
    expect(joinUrl('api', '', 'users')).toBe('api/users');
  });

  it('handles whitespace-only parts', () => {
    expect(joinUrl('api', '   ', 'users')).toBe('api/users');
  });

  it('handles base URL with protocol', () => {
    // Note: joinUrl strips leading/trailing slashes, so protocol slashes are removed
    expect(joinUrl('https:', '', 'example.com', 'api')).toBe(
      'https:/example.com/api'
    );
  });

  it('handles multiple consecutive slashes', () => {
    expect(joinUrl('///api///', '///v1///')).toBe('api/v1');
  });

  it('returns empty string for all empty parts', () => {
    expect(joinUrl('', '', '')).toBe('');
  });
});
