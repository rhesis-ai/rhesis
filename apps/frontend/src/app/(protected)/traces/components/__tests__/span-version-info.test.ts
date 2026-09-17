import { VERSION_INFO_ATTRIBUTE, parseVersionInfo } from '../SpanDetailsPanel';

describe('VERSION_INFO_ATTRIBUTE', () => {
  it('matches the key the backend writes on the span', () => {
    // Mirrors EndpointAttributes.VERSION_INFO in
    // apps/backend/src/rhesis/backend/app/services/invokers/tracing.py
    expect(VERSION_INFO_ATTRIBUTE).toBe('endpoint.version_info');
  });
});

describe('parseVersionInfo', () => {
  it('parses the serialized JSON span attributes carry', () => {
    expect(parseVersionInfo('{"prompt_version":"v3.2"}')).toEqual({
      prompt_version: 'v3.2',
    });
  });

  it('accepts an already-parsed object', () => {
    expect(parseVersionInfo({ prompt_version: 'v3.2' })).toEqual({
      prompt_version: 'v3.2',
    });
  });

  it('preserves nested values', () => {
    expect(parseVersionInfo('{"cfg":{"temperature":0.2}}')).toEqual({
      cfg: { temperature: 0.2 },
    });
  });

  it.each([
    ['malformed JSON', '{oops'],
    ['a JSON array', '[1,2,3]'],
    ['a JSON scalar', '"v3"'],
    ['an empty object', '{}'],
    ['an empty string', ''],
  ])('returns null for %s', (_label, value) => {
    expect(parseVersionInfo(value)).toBeNull();
  });

  it.each([
    ['undefined', undefined],
    ['null', null],
    ['a number', 42],
  ])('returns null for %s', (_label, value) => {
    expect(parseVersionInfo(value)).toBeNull();
  });
});
