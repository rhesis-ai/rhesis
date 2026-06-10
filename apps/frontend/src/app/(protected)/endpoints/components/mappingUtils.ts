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

export function parseResMapping(
  obj: Record<string, string>
): { api: string; rhesis: string }[] {
  return Object.entries(obj).map(([rhesisKey, apiPath]) => ({
    api: apiPath.replace(/^\$\./, ''),
    rhesis: rhesisKey,
  }));
}
