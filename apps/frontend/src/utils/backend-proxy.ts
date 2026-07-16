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

const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);

/**
 * Max backend-origin redirects to follow server-side before giving up. A
 * trailing-slash normalization is a single hop; anything beyond a couple
 * indicates a misconfigured loop, so cap low.
 */
const MAX_BACKEND_REDIRECTS = 5;

/**
 * Resolve a `Location` header against the current URL and return it only if
 * it points back at the backend itself. Same-origin redirects are followed
 * server-side (see `proxyToBackend`); cross-origin ones (e.g. an S3 presigned
 * URL) return `null` here so they pass through to the browser untouched.
 */
function resolveSameOriginRedirect(
  location: string | null,
  currentUrl: URL,
  backendOrigin: string
): URL | null {
  if (!location) return null;
  let locationUrl: URL;
  try {
    locationUrl = new URL(location, currentUrl);
  } catch {
    return null;
  }
  return locationUrl.origin === backendOrigin ? locationUrl : null;
}

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
 * forwarded.
 *
 * Redirects that point back at the backend (e.g. FastAPI's trailing-slash
 * enforcement) are followed here, server-side, so the injected
 * `Authorization` header is reapplied on each hop and the browser never has
 * to follow them. Returning such a redirect to the browser instead would
 * both drop the auth header on the follow-up request and ping-pong forever
 * between Next.js (strips the trailing slash) and FastAPI (adds it back).
 * Cross-origin redirects (e.g. an S3 presigned URL) are NOT followed — they
 * pass through so the browser can follow them directly.
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

  // `append`, not `set`: repeated query keys (e.g. `?id=a&id=b`) must survive
  // the copy — `set` would collapse them to the last value.
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.append(key, value);
  });

  const headers: Record<string, string> = {};
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  Object.assign(headers, overrideHeaders);

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  // Buffer the body once so it can be replayed if we follow a 307/308 (which,
  // unlike 303, preserve method and body) to a backend-origin redirect target.
  const bodyBuffer = hasBody ? await request.arrayBuffer() : undefined;
  const backendOrigin = new URL(getServerBackendUrl()).origin;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    let currentUrl = target;
    let upstream = await fetch(currentUrl, {
      method: request.method,
      headers,
      body: bodyBuffer,
      cache: 'no-store',
      signal: controller.signal,
      redirect: 'manual',
    });

    // Follow backend-origin redirects here rather than handing them to the
    // browser (see the function-level comment for why).
    for (let hop = 0; hop < MAX_BACKEND_REDIRECTS; hop++) {
      if (!REDIRECT_STATUSES.has(upstream.status)) break;
      const next = resolveSameOriginRedirect(
        upstream.headers.get('location'),
        currentUrl,
        backendOrigin
      );
      if (!next) break;
      // Cancel the redirect body so the connection can be reused.
      await upstream.body?.cancel();
      currentUrl = next;
      upstream = await fetch(currentUrl, {
        method: request.method,
        headers,
        body: bodyBuffer,
        cache: 'no-store',
        signal: controller.signal,
        redirect: 'manual',
      });
    }

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
