import { sharedPrefix, trimSharedPrefix } from '../shared-prefix';

describe('sharedPrefix', () => {
  it('finds prefix at space boundary', () => {
    expect(sharedPrefix(['Toxicity Score', 'Toxicity Level'])).toBe(
      'Toxicity '
    );
  });

  it('finds prefix at colon boundary', () => {
    expect(sharedPrefix(['LLM: Safety', 'LLM: Quality'])).toBe('LLM: ');
  });

  it('does not trim mid-word', () => {
    expect(sharedPrefix(['Focus', 'Formal'])).toBe('');
  });

  it('enforces min 3 char guard', () => {
    // 'A ' is only 2 chars, below the 3-char minimum
    expect(sharedPrefix(['A X', 'A Y'])).toBe('');
  });

  it('keeps prefix at exactly 3 chars', () => {
    // 'AB ' is exactly 3 chars, passes the guard
    expect(sharedPrefix(['AB X', 'AB Y'])).toBe('AB ');
  });

  it('returns empty for empty input', () => {
    expect(sharedPrefix([])).toBe('');
  });

  it('returns empty for single item', () => {
    expect(sharedPrefix(['Toxicity'])).toBe('');
  });
});

describe('trimSharedPrefix', () => {
  it('trims common prefix from names', () => {
    expect(trimSharedPrefix(['Toxicity Score', 'Toxicity Level'])).toEqual([
      'Score',
      'Level',
    ]);
  });

  it('returns original names when trimming would create duplicates', () => {
    const names = ['Safety Check', 'Safety Check'];
    expect(trimSharedPrefix(names)).toEqual(names);
  });

  it('returns original names when no common prefix', () => {
    const names = ['Alpha', 'Beta'];
    expect(trimSharedPrefix(names)).toEqual(names);
  });

  it('returns empty array for empty input', () => {
    expect(trimSharedPrefix([])).toEqual([]);
  });

  it('returns single item unchanged', () => {
    expect(trimSharedPrefix(['Toxicity'])).toEqual(['Toxicity']);
  });
});
