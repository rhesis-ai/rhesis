import { NextRequest, NextResponse } from 'next/server';
import { getFreshAccessToken } from '@/auth';
import { proxyToBackend } from '@/utils/backend-proxy';

export const dynamic = 'force-dynamic';

/**
 * BFF proxy for all authenticated client API calls.
 *
 * The browser never holds a backend access token — client `BaseApiClient`
 * instances point at `/api/backend/*` (same origin) instead of the backend
 * directly, and this route injects `Authorization` server-side from the
 * httpOnly session cookie, refreshing it first if it's stale. This is what
 * makes the access token structurally invisible to browser JS: there is
 * nothing for a component's dependency array or query key to depend on.
 *
 * Fails closed (401) when there's no valid session rather than forwarding an
 * unauthenticated request to the backend.
 */
async function handle(req: NextRequest): Promise<NextResponse> {
  const accessToken = await getFreshAccessToken({ headers: req.headers });
  if (!accessToken) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  return proxyToBackend(req, {
    backendPath: req.nextUrl.pathname.replace(/^\/api\/backend/, ''),
    overrideHeaders: { authorization: `Bearer ${accessToken}` },
  });
}

export function GET(req: NextRequest) {
  return handle(req);
}
export function POST(req: NextRequest) {
  return handle(req);
}
export function PUT(req: NextRequest) {
  return handle(req);
}
export function PATCH(req: NextRequest) {
  return handle(req);
}
export function DELETE(req: NextRequest) {
  return handle(req);
}
