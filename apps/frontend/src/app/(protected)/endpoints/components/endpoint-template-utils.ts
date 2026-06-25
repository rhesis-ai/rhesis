export function extractVars(template: string): string[] {
  const vars = new Set<string>();
  for (const m of template.matchAll(/\{\{\s*([\w.]+)(?:\s*\|[^}]*)?\s*\}\}/g)) {
    vars.add(m[1].split('.')[0]);
  }
  return [...vars];
}

export function applyJsonPath(obj: unknown, path: string): unknown {
  const cleaned = path.replace(/^\$\.?/, '');
  if (!cleaned) return obj;
  const parts: string[] = [];
  const re = /([^.[]+)|\[(\d+)\]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(cleaned)) !== null) parts.push(m[1] ?? m[2]);
  let cur: unknown = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object') return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return cur;
}

const SENSITIVE_HEADERS = new Set(['authorization', 'x-api-key', 'api-key']);

export function maskHeaders(
  headers: Record<string, string>
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(headers).map(([k, v]) => {
      if (!SENSITIVE_HEADERS.has(k.toLowerCase())) return [k, v];
      const prefix = v.match(/^(Bearer\s+)/i)?.[1] ?? '';
      return [k, `${prefix}[hidden]`];
    })
  );
}

function cleanUnresolved(val: unknown): unknown {
  if (Array.isArray(val)) {
    return val.map(cleanUnresolved).filter(v => v !== null);
  }
  if (val && typeof val === 'object') {
    return Object.fromEntries(
      Object.entries(val as Record<string, unknown>)
        .map(([k, v]) => [k, cleanUnresolved(v)])
        .filter(([, v]) => v !== null)
    );
  }
  return val;
}

export function substituteVars(
  template: string,
  values: Record<string, string>
): string {
  // Quoted template vars: "{{ ... }}" → value or null (so JSON stays valid)
  let result = template.replace(
    /"(\{\{\s*[\w.]+(?:\s*\|[^}]*)?\s*\}\})"/g,
    match => {
      const nameMatch = match.match(/\{\{\s*([\w.]+)/);
      if (!nameMatch) return 'null';
      const base = nameMatch[1].split('.')[0];
      return values[base] !== undefined ? JSON.stringify(values[base]) : 'null';
    }
  );
  // Unquoted template vars: {{ ... }} → value or null (so JSON stays valid)
  result = result.replace(
    /\{\{\s*([\w.]+)(?:\s*\|[^}]*)?\s*\}\}/g,
    (_match, name) => {
      const base = name.split('.')[0];
      return values[base] !== undefined ? String(values[base]) : 'null';
    }
  );
  // Strip nulls left by unresolved vars; preserve intentional empty strings
  try {
    return JSON.stringify(cleanUnresolved(JSON.parse(result)), null, 2);
  } catch {
    return result;
  }
}

export function buildCurl(
  method: string,
  url: string,
  headers: Record<string, string>,
  body: string
): string {
  const lines: string[] = [`curl -X ${method} '${url}'`];
  for (const [k, v] of Object.entries(maskHeaders(headers))) {
    lines.push(`  -H '${k}: ${v}'`);
  }
  const trimmed = body.trim();
  if (trimmed && trimmed !== '{}') {
    const pretty = (() => {
      try {
        return JSON.stringify(JSON.parse(trimmed), null, 2);
      } catch {
        return trimmed;
      }
    })();
    lines.push(`  -d '${pretty.replace(/'/g, "\\'")}'`);
  }
  return lines.join(' \\\n');
}
