/** Parse a string as JSON object/array; returns null when not valid JSON. */
export function parseJsonString(
  text: string
): Record<string, unknown> | unknown[] | null {
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
  return MARKDOWN_PATTERN.test(text);
}
