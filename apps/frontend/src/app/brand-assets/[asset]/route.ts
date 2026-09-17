import { NextRequest, NextResponse } from 'next/server';
import { getFreshAccessToken } from '@/auth';
import { getServerBackendUrl } from '@/utils/url-resolver';

export const dynamic = 'force-dynamic';

const ASSET_TIMEOUT_MS = 10_000;

/** Assets this route will proxy. Anything else 404s rather than reaching the backend. */
const ALLOWED_ASSETS = new Set(['favicon']);

/**
 * Response headers we set ourselves rather than forward.
 *
 * The backend sends the same set, but these are the headers that make an
 * uploaded SVG favicon safe to serve from our own origin, so they are
 * re-asserted here instead of depending on an upstream that could change.
 */
const SECURITY_HEADERS: Record<string, string> = {
  'Content-Disposition': 'inline',
  'X-Content-Type-Options': 'nosniff',
  'Content-Security-Policy':
    "default-src 'none'; style-src 'unsafe-inline'; sandbox",
};

/**
 * Serves the calling user's organisation branding assets from object storage.
 *
 * A proxy rather than a direct link because the storage bucket is private and
 * the `file://` backend used in local development cannot presign URLs at all.
 * Going through the app also means the browser's own favicon request — which
 * carries no `Authorization` header, only the same-origin session cookie —
 * resolves the organisation server-side, so one URL serves every org its own
 * icon.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ asset: string }> }
) {
  const { asset } = await params;
  if (!ALLOWED_ASSETS.has(asset)) {
    return NextResponse.json({ error: 'Unknown asset' }, { status: 404 });
  }

  const { accessToken } = await getFreshAccessToken({
    headers: request.headers,
  });
  if (!accessToken) {
    // Not an error worth surfacing: a signed-out visitor has no organisation,
    // so there is no org favicon to serve and the default applies.
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const upstream = `${getServerBackendUrl()}/organizations/settings/branding/assets/${asset}`;

  let response: Response;
  try {
    response = await fetch(upstream, {
      signal: AbortSignal.timeout(ASSET_TIMEOUT_MS),
      headers: {
        Authorization: `Bearer ${accessToken}`,
        // Lets the backend answer 304 when the browser already has the asset.
        ...forwardIfPresent(request, 'if-none-match'),
      },
    });
  } catch {
    return NextResponse.json(
      { error: 'Failed to fetch branding asset' },
      { status: 502 }
    );
  }

  if (response.status === 304) {
    return new NextResponse(null, {
      status: 304,
      headers: cacheHeaders(request, response),
    });
  }

  if (!response.ok) {
    return new NextResponse(null, { status: response.status });
  }

  return new NextResponse(response.body, {
    status: 200,
    headers: {
      'Content-Type':
        response.headers.get('content-type') ?? 'application/octet-stream',
      ...SECURITY_HEADERS,
      ...cacheHeaders(request, response),
    },
  });
}

function forwardIfPresent(
  request: NextRequest,
  header: string
): Record<string, string> {
  const value = request.headers.get(header);
  return value ? { [header]: value } : {};
}

function cacheHeaders(
  request: NextRequest,
  response: Response
): Record<string, string> {
  const etag = response.headers.get('etag');
  // `resolveBranding` appends `?v=<content hash>`, so a replaced favicon is a
  // different URL and this entry can never go stale. Without that parameter —
  // an old page still in a tab, or a direct hit — fall back to revalidating,
  // since the same URL would otherwise pin the previous icon.
  const versioned = request.nextUrl.searchParams.has('v');
  return {
    // `private` because the asset is resolved from the caller's session: a
    // shared cache must never hand one organisation's favicon to another.
    'Cache-Control': versioned
      ? 'private, max-age=31536000, immutable'
      : 'private, max-age=60, must-revalidate',
    ...(etag ? { ETag: etag } : {}),
  };
}
