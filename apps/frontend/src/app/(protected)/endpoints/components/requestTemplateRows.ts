import { REQUEST_FIELDS, SYSTEM_PROMPT_KEY } from './mapping-variables';

/**
 * Variable name → where it goes in the API's request body, as a dotted path
 * (`payload.query`). `filter` is the one read from the template; unset means a
 * new row, which gets the variable's default.
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

const isPlainObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/**
 * Reads a request template that easy input can show: a JSON object, nested
 * objects allowed, whose values are each exactly one known variable, used
 * once, plus the optional top-level `system_prompt` text. Anything else
 * (arrays, literals, Jinja blocks) returns null and stays in the JSON editor.
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
  if (!isPlainObject(parsed)) return null;

  const fields: RequestFieldMap = {};
  let systemPrompt = '';
  const walk = (obj: Record<string, unknown>, prefix: string): boolean => {
    for (const [key, value] of Object.entries(obj)) {
      const path = prefix ? `${prefix}.${key}` : key;
      if (!prefix && key === SYSTEM_PROMPT_KEY && typeof value === 'string') {
        systemPrompt = value;
        continue;
      }
      if (isPlainObject(value)) {
        if (!walk(value, path)) return false;
        continue;
      }
      if (typeof value !== 'string') return false;
      const m = value.match(WHOLE_VAR_RE);
      if (!m || !KNOWN_VARS.has(m[1]) || m[1] in fields) return false;
      fields[m[1]] = {
        field: path,
        filter: m[2].trim() ? ` ${m[2].trim()}` : '',
      };
    }
    return true;
  };
  return walk(parsed, '') ? { fields, systemPrompt } : null;
}

/** Variables whose path repeats another's, or sits inside it (`a` and `a.b`). */
export function conflictingFields(fields: RequestFieldMap): Set<string> {
  const entries = Object.entries(fields)
    .map(([name, { field }]) => [name, field.trim()] as const)
    .filter(([, path]) => path);
  const out = new Set<string>();
  for (const [name, path] of entries) {
    for (const [other, otherPath] of entries) {
      if (other === name) continue;
      if (
        path === otherPath ||
        path.startsWith(`${otherPath}.`) ||
        otherPath.startsWith(`${path}.`)
      ) {
        out.add(name);
      }
    }
  }
  return out;
}

export function buildRequestTemplate({
  fields,
  systemPrompt,
}: RequestTemplateRows): string {
  const body: Record<string, unknown> = {};
  const conflicts = conflictingFields(fields);
  for (const { name, defaultFilter } of REQUEST_FIELDS) {
    const entry = fields[name];
    const path = entry?.field.trim();
    // A clashing path would overwrite another variable; leave it out until fixed.
    if (!path || path === SYSTEM_PROMPT_KEY || conflicts.has(name)) continue;
    const keys = path.split('.').filter(Boolean);
    if (keys.length === 0) continue;
    let node = body;
    for (const key of keys.slice(0, -1)) {
      if (!isPlainObject(node[key])) node[key] = {};
      node = node[key] as Record<string, unknown>;
    }
    node[keys[keys.length - 1]] =
      `{{ ${name}${entry.filter ?? defaultFilter} }}`;
  }
  if (systemPrompt.trim()) body[SYSTEM_PROMPT_KEY] = systemPrompt;
  return JSON.stringify(body, null, 2);
}
