import {
  looksLikeMarkdown,
  parseJsonString,
  stringifyMessageContent,
} from '../message-content';

describe('message-content', () => {
  describe('parseJsonString', () => {
    it('parses JSON objects and arrays', () => {
      expect(parseJsonString('{"a":1}')).toEqual({ a: 1 });
      expect(parseJsonString('[1, 2]')).toEqual([1, 2]);
    });

    it('parses JSON primitives', () => {
      expect(parseJsonString('true')).toBe(true);
      expect(parseJsonString('false')).toBe(false);
      expect(parseJsonString('null')).toBe(null);
      expect(parseJsonString('42')).toBe(42);
      expect(parseJsonString('-3.14')).toBe(-3.14);
      expect(parseJsonString('"ok"')).toBe('ok');
    });

    it('rejects plain text that is not JSON', () => {
      expect(parseJsonString('hello')).toBeNull();
      expect(parseJsonString('The answer is 42')).toBeNull();
      expect(parseJsonString('true story')).toBeNull();
      expect(parseJsonString('')).toBeNull();
    });
  });

  describe('looksLikeMarkdown', () => {
    it('detects common markdown syntax', () => {
      expect(looksLikeMarkdown('# Heading')).toBe(true);
      expect(looksLikeMarkdown('- item')).toBe(true);
      expect(looksLikeMarkdown('**bold**')).toBe(true);
      expect(looksLikeMarkdown('[link](https://example.com)')).toBe(true);
      expect(looksLikeMarkdown('```code```')).toBe(true);
    });

    it('detects inline code', () => {
      expect(looksLikeMarkdown('Run `curl` to test')).toBe(true);
      expect(looksLikeMarkdown('Use `foo_bar` here')).toBe(true);
    });

    it('returns false for plain text', () => {
      expect(looksLikeMarkdown('hello world')).toBe(false);
      expect(looksLikeMarkdown('line one\nline two')).toBe(false);
    });
  });

  describe('stringifyMessageContent', () => {
    it('returns strings unchanged', () => {
      expect(stringifyMessageContent('hello')).toBe('hello');
    });

    it('stringifies structured values', () => {
      expect(stringifyMessageContent({ a: 1 })).toBe('{\n  "a": 1\n}');
    });
  });
});
