import { NextRequest, NextResponse } from 'next/server';
import { getServerBackendUrl } from '@/utils/url-resolver';

const DEFAULT_TIMEOUT_MS = 10_000;

/**
 * Path prefixes (relative to the backend, i.e. after stripping `/api` or
 * `/api/backend`) whose upstream calls are synchronous but slow — the
 * backend doesn't send response headers until the whole operation (LLM
 * generation, file import, Garak scan) completes. These need a much longer
 * budget than the default 10s, which is sized for ordinary CRUD calls.
 */
const LONG_RUNNING_PATH_PREFIXES = [
  '/services/generate',
  '/import',
  '/garak/import',
  '/garak/generate',
  '/garak/sync',
];

const LONG_RUNNING_TIMEOUT_MS = 300_000;

/** Pick the timeout budget for a given backend-relative pathname. */
export function resolveTimeoutMs(pathname: string): number {
  return LONG_RUNNING_PATH_PREFIXES.some(prefix => pathname.startsWith(prefix))
    ? LONG_RUNNING_TIMEOUT_MS
    : DEFAULT_TIMEOUT_MS;
}

const FORWARDED_REQUEST_HEADERS = [
  'authorization',
  'content-type',
  'accept',
  'accept-language',
  'user-agent',
  // Active project scope — must be forwarded so requests routed through the
  // proxy stay project-isolated instead of falling back to org-wide access.
  'x-project-id',
];

const FORWARDED_RESPONSE_HEADERS = [
  'content-type',
  'content-disposition',
  'content-length',
  'location',
  // Pagination / listing metadata read directly by client grids.
  'x-total-count',
  'access-control-expose-headers',
];

interface ProxyOptions {
  /**
   * Override the backend path. Defaults to the incoming request path with
   * the leading `/api` prefix stripped (e.g. `/api/files/123` → `/files/123`).
   */
  backendPath?: string;
  /**
   * Upstream fetch timeout in milliseconds. Defaults to `resolveTimeoutMs`
   * based on the resolved backend path, so long-running operations
   * (generation, import, Garak) automatically get a longer budget without
   * every call site having to know about it.
   */
  timeoutMs?: number;
  /**
   * Headers to set on the upstream request in addition to (and overriding)
   * whatever was forwarded from the incoming request. Used by the
   * `/api/backend` BFF route to inject a server-resolved `Authorization`
   * header without the client ever supplying one.
   */
  overrideHeaders?: Record<string, string>;
}

/**
 * Runtime proxy to the backend.
 *
 * Reads `BACKEND_URL` via `getServerBackendUrl()` on every request so the
 * same Docker image works across local / dev / stg / prd without build args.
 * All query parameters, relevant request headers, and response headers are
 * forwarded. Redirects are passed through (not followed server-side) so the
 * browser can follow presigned-URL 302s directly.
 */
export async function proxyToBackend(
  request: NextRequest,
  options: ProxyOptions = {}
): Promise<NextResponse> {
  const { backendPath, overrideHeaders } = options;

  const pathname =
    backendPath ?? request.nextUrl.pathname.replace(/^\/api/, '');
  const timeoutMs = options.timeoutMs ?? resolveTimeoutMs(pathname);
  const target = new URL(pathname, getServerBackendUrl());

  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value);
  });

  const headers: Record<string, string> = {};
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  Object.assign(headers, overrideHeaders);

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: 'no-store',
      signal: controller.signal,
      redirect: 'manual',
    });

    const responseHeaders: Record<string, string> = {
      'cache-control': 'no-store',
    };
    for (const name of FORWARDED_RESPONSE_HEADERS) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders[name] = value;
    }

    // Stream the upstream body straight through instead of buffering it.
    // This is required for NDJSON/SSE endpoints (test generation) that the
    // client reads incrementally via `response.body.getReader()` — buffering
    // here would defeat live streaming and hold the whole payload in memory.
    // It's also what lets `clearTimeout` below bound only "time to first
    // byte" rather than the full body transfer for long-running responses.
    const body =
      upstream.status === 204 || upstream.status === 304
        ? null
        : upstream.body;

    return new NextResponse(body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (error) {
    const isTimeout =
      error instanceof DOMException && error.name === 'AbortError';
    console.error(
      `[backend-proxy] ${request.method} ${target.toString()} ` +
        `${isTimeout ? 'timed out' : 'failed'}:`,
      error
    );
    return NextResponse.json(
      {
        error: isTimeout ? 'Backend request timed out' : 'Backend unreachable',
      },
      { status: isTimeout ? 504 : 502 }
    );
  } finally {
    clearTimeout(timeout);
  }
}
