/**
 * Paths (no leading `$.`) a response mapping can point at: every key, with
 * arrays offered whole and, when they hold objects, through their first item.
 */
export function responsePaths(value: unknown): string[] {
  const out: string[] = [];
  const walk = (node: unknown, path: string) => {
    if (Array.isArray(node)) {
      if (path) out.push(path);
      const first: unknown = node[0];
      if (first && typeof first === 'object' && !Array.isArray(first)) {
        walkObject(first as Record<string, unknown>, `${path}[0]`);
      }
      return;
    }
    if (node && typeof node === 'object') {
      if (path) out.push(path);
      walkObject(node as Record<string, unknown>, path);
      return;
    }
    if (path) out.push(path);
  };
  const walkObject = (obj: Record<string, unknown>, path: string) => {
    for (const [key, child] of Object.entries(obj)) {
      walk(child, path ? `${path}.${key}` : key);
    }
  };
  walk(value, '');
  return out;
}

/** The API's own response inside a test result, which wraps it in `raw_response`. */
export function mappingTarget(response: unknown): unknown {
  if (!response || typeof response !== 'object') return response;
  const r = response as Record<string, unknown>;
  return r.raw_response != null ? r.raw_response : response;
}
