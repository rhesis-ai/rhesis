import { NextRequest, NextResponse } from 'next/server';
import { getServerBackendUrl } from '@/utils/url-resolver';

const DEFAULT_TIMEOUT_MS = 10_000;

const FORWARDED_REQUEST_HEADERS = [
  'authorization',
  'content-type',
  'accept',
  'accept-language',
  'user-agent',
];

const FORWARDED_RESPONSE_HEADERS = [
  'content-type',
  'content-disposition',
  'content-length',
  'location',
];

interface ProxyOptions {
  /**
   * Override the backend path. Defaults to the incoming request path with
   * the leading `/api` prefix stripped (e.g. `/api/files/123` → `/files/123`).
   */
  backendPath?: string;
  /** Upstream fetch timeout in milliseconds (default: 10 000). */
  timeoutMs?: number;
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
  const { backendPath, timeoutMs = DEFAULT_TIMEOUT_MS } = options;

  const pathname =
    backendPath ?? request.nextUrl.pathname.replace(/^\/api/, '');
  const target = new URL(pathname, getServerBackendUrl());

  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value);
  });

  const headers: Record<string, string> = {};
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }

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

    const body =
      upstream.status === 204 || upstream.status === 304
        ? null
        : await upstream.arrayBuffer();

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
