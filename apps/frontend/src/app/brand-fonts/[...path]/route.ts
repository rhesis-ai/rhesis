import { NextRequest, NextResponse } from 'next/server';
import { normalizeBaseUrl } from '@/config/branding';

const FONT_TIMEOUT_MS = 10_000;

const FONT_CONTENT_TYPES: Record<string, string> = {
  '.ttf': 'font/ttf',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
};

/**
 * Proxies `/brand-fonts/{file}` to the validated `BRAND_FONT_BASE_URL` at
 * request time. This replaces the earlier `rewrites()` approach whose
 * destination was baked at build time and couldn't change per deployment.
 *
 * The proxy also solves CORS: self-hosted font servers (Gitea, S3, etc.)
 * often don't set `Access-Control-Allow-Origin`, and `@font-face` requests
 * are CORS-restricted. Proxying through the same origin sidesteps this.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const fontBase = normalizeBaseUrl(process.env.BRAND_FONT_BASE_URL);
  if (!fontBase) {
    return NextResponse.json(
      { error: 'Font proxy not configured' },
      { status: 404 }
    );
  }

  const fontFamily = process.env.BRAND_FONT_FAMILY?.trim();
  if (!fontFamily) {
    return NextResponse.json(
      { error: 'Font proxy not configured' },
      { status: 404 }
    );
  }

  const { path } = await params;
  const filePath = path.join('/');

  // Only allow .ttf/.woff/.woff2 files to prevent open-proxy abuse.
  if (!/\.(ttf|woff2?)$/i.test(filePath)) {
    return NextResponse.json({ error: 'Not a font file' }, { status: 400 });
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

    const body = response.body;
    return new NextResponse(body, {
      status: 200,
      headers: {
        'Content-Type':
          response.headers.get('content-type') ??
          FONT_CONTENT_TYPES[
            filePath.slice(filePath.lastIndexOf('.')).toLowerCase()
          ] ??
          'application/octet-stream',
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
