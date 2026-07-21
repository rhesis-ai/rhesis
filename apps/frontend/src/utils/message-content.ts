/** Parse a string as JSON object/array; returns null when not valid JSON. */
export function parseJsonString(
  text: string
): Record<string, unknown> | unknown[] | null {
  if (typeof text !== 'string') {
    return null;
  }
  const trimmed = text.trim();
  if (
    !(trimmed.startsWith('{') && trimmed.endsWith('}')) &&
    !(trimmed.startsWith('[') && trimmed.endsWith(']'))
  ) {
    return null;
  }
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (parsed !== null && typeof parsed === 'object') {
      return parsed as Record<string, unknown> | unknown[];
    }
  } catch {
    return null;
  }
  return null;
}

const MARKDOWN_PATTERN =
  /(^|\n)(#{1,6}\s|[-*+]\s|\d+\.\s|>\s|```)|(\*\*.+\*\*|__.+__)|(\[.+\]\(.+\))/;

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
