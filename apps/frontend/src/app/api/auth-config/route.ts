import { NextRequest, NextResponse } from 'next/server';
import { getServerBackendUrl } from '@/utils/url-resolver';

// Per-request handler (must NOT be cached / pre-rendered): the backend
// provider list depends on the org query param and on backend configuration
// that can change without a frontend redeploy.
export const dynamic = 'force-dynamic';

/**
 * Same-origin proxy for `GET /auth/providers` on the backend.
 *
 * The browser hits `/api/auth-config` (same origin as `dev-app.rhesis.ai`),
 * which keeps us out of CORS territory when the frontend runs against a
 * different-origin backend (localhost dev, dev-api, stg, prd). The earlier
 * implementation used a `next.config.mjs` external rewrite, but that
 * evaluates `process.env.BACKEND_URL` at *build* time and freezes the
 * destination into `.next/routes-manifest.json` — meaning runtime env
 * vars on Cloud Run can't override it. A Route Handler is evaluated per
 * request, so `getServerBackendUrl()` correctly reads `BACKEND_URL` at
 * request time and the same image works across every deployment.
 */
export async function GET(request: NextRequest) {
  const target = new URL('/auth/providers', getServerBackendUrl());
  const org = request.nextUrl.searchParams.get('org');
  if (org) {
    target.searchParams.set('org', org);
  }

  try {
    const upstream = await fetch(target, { cache: 'no-store' });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: {
        'content-type':
          upstream.headers.get('content-type') ?? 'application/json',
      },
    });
  } catch (error) {
    console.error(
      `[/api/auth-config] failed to reach ${target.toString()}:`,
      error
    );
    return NextResponse.json(
      { error: 'Failed to load authentication options' },
      { status: 502 }
    );
  }
}
