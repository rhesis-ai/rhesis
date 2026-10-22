export interface HeaderRow {
  id: string;
  key: string;
  value: string;
}

const AUTH_TOKEN_RE = /\{\{\s*auth_token\s*\}\}/;
export const DEFAULT_REQUEST_HEADERS = JSON.stringify(
  { 'Content-Type': 'application/json' },
  null,
  2
);

let rowSeq = 0;
export function newHeaderRow(key = '', value = ''): HeaderRow {
  rowSeq += 1;
  return { id: `header-${rowSeq}`, key, value };
}

/** Rows for a flat `{ string: string }` object, or null when the JSON can't be shown as rows. */
export function parseHeaderRows(json: string): HeaderRow[] | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(json || '{}');
  } catch {
    return null;
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return null;
  }
  const entries = Object.entries(parsed as Record<string, unknown>);
  if (entries.some(([, v]) => typeof v !== 'string')) return null;
  return entries.map(([k, v]) => newHeaderRow(k, v as string));
}

export function headerRowsToJson(rows: HeaderRow[]): string {
  const obj: Record<string, string> = {};
  for (const row of rows) {
    if (row.key.trim()) obj[row.key.trim()] = row.value;
  }
  return JSON.stringify(obj, null, 2);
}

/**
 * Adds `Authorization: Bearer {{ auth_token }}` once a token is set and nothing
 * references it yet, and drops it again when the token is cleared — the same
 * rule HeadersEditor applies to its JSON. Returns the input unchanged otherwise.
 */
export function syncAuthorizationHeader(
  json: string,
  authToken: string
): string {
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(json || '{}') as Record<string, unknown>;
  } catch {
    return json;
  }
  const referencesToken = Object.values(parsed).some(
    v => typeof v === 'string' && AUTH_TOKEN_RE.test(v)
  );
  if (authToken && !referencesToken && !('Authorization' in parsed)) {
    return JSON.stringify(
      { Authorization: 'Bearer {{ auth_token }}', ...parsed },
      null,
      2
    );
  }
  if (!authToken && 'Authorization' in parsed) {
    const { Authorization: _drop, ...rest } = parsed;
    return JSON.stringify(rest, null, 2);
  }
  return json;
}
