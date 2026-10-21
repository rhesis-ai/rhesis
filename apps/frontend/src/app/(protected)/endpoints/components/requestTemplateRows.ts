import { REQUEST_FIELDS, SYSTEM_PROMPT_KEY } from './mapping-variables';

/**
 * Variable name → the API body field it is sent as. `filter` is the one read
 * from the template; unset means a new row, which gets the variable's default.
 */
export type RequestFieldMap = Record<
  string,
  { field: string; filter?: string }
>;

export interface RequestTemplateRows {
  fields: RequestFieldMap;
  systemPrompt: string;
}

const KNOWN_VARS = new Set(REQUEST_FIELDS.map(f => f.name));
const WHOLE_VAR_RE = /^\{\{\s*(\w+)((?:\s*\|\s*[\w]+)*)\s*\}\}$/;

/**
 * Reads a request template that easy input can show: a flat JSON object whose
 * values are each exactly one known variable, used once, plus the optional
 * `system_prompt` text. Anything else (nesting, literals, Jinja blocks)
 * returns null and stays in the JSON editor.
 */
export function parseRequestTemplate(
  template: string
): RequestTemplateRows | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(template || '{}');
  } catch {
    return null;
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return null;
  }
  const fields: RequestFieldMap = {};
  let systemPrompt = '';
  for (const [field, value] of Object.entries(parsed)) {
    if (typeof value !== 'string') return null;
    if (field === SYSTEM_PROMPT_KEY) {
      systemPrompt = value;
      continue;
    }
    const m = value.match(WHOLE_VAR_RE);
    if (!m || !KNOWN_VARS.has(m[1]) || m[1] in fields) return null;
    fields[m[1]] = { field, filter: m[2].trim() ? ` ${m[2].trim()}` : '' };
  }
  return { fields, systemPrompt };
}

export function buildRequestTemplate({
  fields,
  systemPrompt,
}: RequestTemplateRows): string {
  const body: Record<string, string> = {};
  for (const { name, defaultFilter } of REQUEST_FIELDS) {
    const entry = fields[name];
    const field = entry?.field.trim();
    if (!field || field === SYSTEM_PROMPT_KEY) continue;
    const filter = entry.filter ?? defaultFilter;
    body[field] = `{{ ${name}${filter} }}`;
  }
  if (systemPrompt.trim()) body[SYSTEM_PROMPT_KEY] = systemPrompt;
  return JSON.stringify(body, null, 2);
}
