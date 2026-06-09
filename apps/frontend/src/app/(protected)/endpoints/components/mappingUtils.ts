import { MappingRow } from './MappingTable';

export function bodyToRequestMapping(body: string): Record<string, unknown> {
  try {
    return JSON.parse(body);
  } catch {
    // Template contains Jinja syntax that makes it invalid JSON — store as raw string
    // for the backend to render before parsing.
    return { __body__: body };
  }
}

export function parseBodyMapping(obj: Record<string, unknown>): string {
  if ('__body__' in obj && typeof obj.__body__ === 'string')
    return obj.__body__;
  return JSON.stringify(obj, null, 2);
}

export function withDefault(rhesis: string, def: string) {
  if (!def.trim()) return rhesis;
  return rhesis.replace('}}', `| default('${def}') }}`);
}

export function rowsToRequestMapping(
  rows: MappingRow[]
): Record<string, string> {
  return rows.reduce(
    (acc, row) => {
      if (!row.api.trim()) return acc;
      return { ...acc, [row.api]: withDefault(row.rhesis, row.def || '') };
    },
    {} as Record<string, string>
  );
}

export function rowsToResponseMapping(
  rows: MappingRow[]
): Record<string, string> {
  return rows.reduce(
    (acc, row) => {
      if (!row.api.trim() || !row.rhesis) return acc;
      const key = row.rhesis;
      const val = row.api.trim().startsWith('$')
        ? row.api.trim()
        : `$.${row.api.trim()}`;
      return { ...acc, [key]: val };
    },
    {} as Record<string, string>
  );
}

export function parseReqMapping(obj: Record<string, string>): MappingRow[] {
  return Object.entries(obj).map(([api, rhesis]) => {
    const defMatch = rhesis.match(/\|\s*default\('([^']+)'\)/);
    const def = defMatch ? defMatch[1] : '';
    const cleanRhesis = defMatch
      ? rhesis
          .replace(/\s*\|\s*default\('[^']+'\)\s*/, ' ')
          .replace(/\s+}}/, ' }}')
          .trim()
      : rhesis;
    return { api, rhesis: cleanRhesis, def };
  });
}

export function parseResMapping(obj: Record<string, string>): MappingRow[] {
  return Object.entries(obj).map(([rhesisKey, apiPath]) => ({
    api: apiPath.replace(/^\$\./, ''),
    rhesis: rhesisKey,
  }));
}
