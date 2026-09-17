import { NextRequest, NextResponse } from 'next/server';
import { normalizeBaseUrl, slugifyFont } from '@/config/branding';
import { getFreshAccessToken } from '@/auth';
import { getServerBackendUrl } from '@/utils/url-resolver';

const FONT_TIMEOUT_MS = 10_000;

const FONT_CONTENT_TYPES: Record<string, string> = {
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

/** `inria-sans-400.ttf` → `{ slug: 'inria-sans', weight: '400' }`. */
function parseFontFile(
  filePath: string
): { slug: string; weight: string } | null {
  const match = /^([a-z0-9-]+)-(\d{3})\.(?:ttf|otf|woff2?)$/i.exec(filePath);
  if (!match) return null;
  return { slug: match[1].toLowerCase(), weight: match[2] };
}

function fontHeaders(contentType: string, etag: string | null) {
  return {
    'Content-Type': contentType,
    'X-Content-Type-Options': 'nosniff',
    ...(etag ? { ETag: etag } : {}),
  };
}

/**
 * Tries the caller's organisation font first, via the backend asset endpoint.
 *
 * Returns null when the caller has no session, no org font, or asked for a
 * slug that isn't the org's current one — all of which mean "fall through to
 * the deployment-wide `BRAND_FONT_BASE_URL`".
 */
async function serveOrganizationFont(
  request: NextRequest,
  filePath: string,
  deploymentSlug?: string
): Promise<NextResponse | null> {
  const parsed = parseFontFile(filePath);
  if (!parsed) return null;

  // The @font-face rules name the family that is actually in effect, so a
  // request for the deployment's own family cannot be for an org upload.
  // Skipping here spares an env-branded deployment a token refresh and a
  // backend round trip per font file on every page load.
  if (deploymentSlug && parsed.slug === deploymentSlug) return null;

  const { accessToken } = await getFreshAccessToken({
    headers: request.headers,
  });
  if (!accessToken) return null;

  const upstream =
    `${getServerBackendUrl()}/organizations/settings/branding/assets/` +
    `font-${parsed.weight}?slug=${encodeURIComponent(parsed.slug)}`;

  let response: Response;
  try {
    response = await fetch(upstream, {
      signal: AbortSignal.timeout(FONT_TIMEOUT_MS),
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  } catch {
    return null;
  }

  // 404 is the ordinary "this org has no such font" answer, not a failure.
  if (!response.ok) return null;

  return new NextResponse(response.body, {
    status: 200,
    headers: {
      ...fontHeaders(
        response.headers.get('content-type') ??
          FONT_CONTENT_TYPES[
            filePath.slice(filePath.lastIndexOf('.')).toLowerCase()
          ] ??
          'application/octet-stream',
        response.headers.get('etag')
      ),
      // `private` because the file is resolved from the caller's session. The
      // @font-face rule carries `?v=<content hash>`, so a replaced file is a
      // different URL; without that parameter the filename alone would pin the
      // old bytes, hence the short TTL on that path.
      'Cache-Control': request.nextUrl.searchParams.has('v')
        ? 'private, max-age=31536000, immutable'
        : 'private, max-age=60, must-revalidate',
    },
  });
}

/**
 * Proxies `/brand-fonts/{file}` to whichever font source applies.
 *
 * Organisation-uploaded fonts win; otherwise the validated
 * `BRAND_FONT_BASE_URL` is used, resolved at request time. (That replaced an
 * earlier `rewrites()` approach whose destination was baked at build time and
 * couldn't change per deployment.)
 *
 * The proxy also solves CORS: self-hosted font servers (Gitea, S3, etc.) often
 * don't set `Access-Control-Allow-Origin`, and `@font-face` requests are
 * CORS-restricted. Proxying through the same origin sidesteps this.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const filePath = path.join('/');

  // Only allow font files to prevent open-proxy abuse.
  if (!/\.(ttf|otf|woff2?)$/i.test(filePath)) {
    return NextResponse.json({ error: 'Not a font file' }, { status: 400 });
  }

  const fontBase = normalizeBaseUrl(process.env.BRAND_FONT_BASE_URL);
  const fontFamily = process.env.BRAND_FONT_FAMILY?.trim();

  const organizationFont = await serveOrganizationFont(
    request,
    filePath,
    fontBase && fontFamily ? slugifyFont(fontFamily) : undefined
  );
  if (organizationFont) return organizationFont;

  if (!fontBase || !fontFamily) {
    return NextResponse.json(
      { error: 'Font proxy not configured' },
      { status: 404 }
    );
  }

  const upstream = new URL(
    `${fontBase}/${filePath}`,
    request.nextUrl.origin
  ).toString();

  try {
    const response = await fetch(upstream, {
      signal: AbortSignal.timeout(FONT_TIMEOUT_MS),
      headers: {
        'User-Agent': request.headers.get('user-agent') ?? 'Next.js font proxy',
      },
    });

    if (!response.ok) {
      return new NextResponse(null, { status: response.status });
    }

    return new NextResponse(response.body, {
      status: 200,
      headers: {
        ...fontHeaders(
          response.headers.get('content-type') ??
            FONT_CONTENT_TYPES[
              filePath.slice(filePath.lastIndexOf('.')).toLowerCase()
            ] ??
            'application/octet-stream',
          response.headers.get('etag')
        ),
        // Deployment-wide fonts only change when the values file does, and a
        // changed file gets a new deployment, so this one can be immutable.
        'Cache-Control': 'public, max-age=31536000, immutable',
      },
    });
  } catch {
    return NextResponse.json(
      { error: 'Failed to fetch font' },
      { status: 502 }
    );
  }
}
