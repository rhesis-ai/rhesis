/**
 * Headers that server-side backend calls add for the request being served.
 *
 * Server Components call the backend directly, not through the BFF proxy that
 * normally passes on the browser's IP. `server-factory.ts` (server only)
 * registers a per-request source here, so this module stays free of
 * server-only imports and safe in the client bundle.
 */
let source: (() => Record<string, string>) | null = null;

export function provideServerRequestHeaders(
  provider: () => Record<string, string>
): void {
  source = provider;
}

export function serverRequestHeaders(): Record<string, string> {
  return source?.() ?? {};
}
