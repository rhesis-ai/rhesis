/** Parse a string as JSON; returns null when not valid JSON. */
export function parseJsonString(text: string): unknown | null {
  if (typeof text !== 'string') {
    return null;
  }
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }

  const looksLikeJson =
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']')) ||
    trimmed === 'true' ||
    trimmed === 'false' ||
    trimmed === 'null' ||
    (trimmed.startsWith('"') && trimmed.endsWith('"') && trimmed.length >= 2) ||
    /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(trimmed);

  if (!looksLikeJson) {
    return null;
  }

  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

const MARKDOWN_PATTERN =
  /(^|\n)(#{1,6}\s|[-*+]\s|\d+\.\s|>\s|```)|(\*\*.+\*\*|__.+__)|(\[.+\]\(.+\))|(`[^`\n]+`)/;

/** True when the text contains common markdown syntax (not just plain text). */
export function looksLikeMarkdown(text: string): boolean {
  if (typeof text !== 'string' || !text) {
    return false;
  }
  return MARKDOWN_PATTERN.test(text);
}

/** Normalize message content to a display/API string. */
export function stringifyMessageContent(content: unknown): string {
  if (typeof content === 'string') {
    return content;
  }
  if (content == null) {
    return '';
  }
  return JSON.stringify(content, null, 2);
}
