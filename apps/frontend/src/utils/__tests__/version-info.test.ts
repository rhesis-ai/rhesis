import {
  asVersionInfo,
  summarizeVersionInfo,
  validateVersionInfoDraft,
  versionInfoSourceLabel,
} from '../version-info';
import { VERSION_INFO_MAX_BYTES } from '@/constants/version-info';

describe('asVersionInfo', () => {
  it('accepts a non-empty object', () => {
    expect(asVersionInfo({ prompt_version: 'v3' })).toEqual({
      prompt_version: 'v3',
    });
  });

  it.each([
    ['null', null],
    ['undefined', undefined],
    ['an array', ['v3']],
    ['a string', 'v3'],
    ['a number', 42],
    ['an empty object', {}],
  ])('returns null for %s', (_label, value) => {
    expect(asVersionInfo(value)).toBeNull();
  });
});

describe('versionInfoSourceLabel', () => {
  it('labels each known source', () => {
    expect(versionInfoSourceLabel('endpoint')).toMatch(
      /endpoint configuration/i
    );
    expect(versionInfoSourceLabel('response')).toMatch(/reported/i);
    expect(versionInfoSourceLabel('rescore')).toMatch(/original run/i);
  });

  it('falls back to the endpoint label for anything unknown', () => {
    expect(versionInfoSourceLabel(undefined)).toMatch(
      /endpoint configuration/i
    );
    expect(versionInfoSourceLabel('nonsense')).toMatch(
      /endpoint configuration/i
    );
  });
});

describe('summarizeVersionInfo', () => {
  it('keeps scalars and preserves key order', () => {
    expect(summarizeVersionInfo({ b: 'two', a: 1 })).toEqual([
      { key: 'b', display: 'two' },
      { key: 'a', display: '1' },
    ]);
  });

  it('collapses nested values instead of dumping them', () => {
    expect(summarizeVersionInfo({ cfg: { t: 0.2 }, tags: [1, 2, 3] })).toEqual([
      { key: 'cfg', display: '{…}' },
      { key: 'tags', display: '[3]' },
    ]);
  });

  it('truncates a long scalar so a grid row cannot grow', () => {
    const [entry] = summarizeVersionInfo({ sha: 'a'.repeat(80) });
    expect(entry.display).toHaveLength(17); // 16 chars + ellipsis
    expect(entry.display.endsWith('…')).toBe(true);
  });
});

describe('validateVersionInfoDraft', () => {
  it('accepts a valid object', () => {
    expect(validateVersionInfoDraft('{"prompt_version":"v3"}')).toBeNull();
  });

  it('accepts empty text', () => {
    expect(validateVersionInfoDraft('   ')).toBeNull();
  });

  it('rejects malformed JSON', () => {
    expect(validateVersionInfoDraft('{oops')).toMatch(/invalid json/i);
  });

  it.each([
    ['an array', '[1,2,3]'],
    ['a string', '"v3"'],
    ['a number', '42'],
  ])('rejects %s', (_label, raw) => {
    expect(validateVersionInfoDraft(raw)).toMatch(/must be a JSON object/);
  });

  it('rejects a value nested too deeply', () => {
    const tooDeep = JSON.stringify({
      a: { b: { c: { d: { e: { f: { g: { h: { i: 1 } } } } } } } },
    });
    expect(validateVersionInfoDraft(tooDeep)).toMatch(/nest more than/);
  });

  it('accepts a value exactly at the depth limit', () => {
    const atLimit = JSON.stringify({
      a: { b: { c: { d: { e: { f: { g: 1 } } } } } },
    });
    expect(validateVersionInfoDraft(atLimit)).toBeNull();
  });

  it('rejects a value over the size limit', () => {
    const oversize = JSON.stringify({
      blob: 'x'.repeat(VERSION_INFO_MAX_BYTES),
    });
    expect(validateVersionInfoDraft(oversize)).toMatch(/at most/);
  });
});
