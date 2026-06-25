import { NextRequest } from 'next/server';
import { proxyToBackend } from '@/utils/backend-proxy';

export const dynamic = 'force-dynamic';

/**
 * Catch-all runtime proxy for `/api/*` requests that don't have a more
 * specific Route Handler (e.g. `/api/auth-config`, `/api/feedback`).
 *
 * Replaces the build-time `next.config.mjs` rewrite that baked
 * `BACKEND_URL` into `routes-manifest.json`. Because this handler runs
 * per request, `BACKEND_URL` is resolved from the runtime environment
 * and one Docker image works across all deployments.
 */

export function GET(req: NextRequest) {
  return proxyToBackend(req);
}
export function POST(req: NextRequest) {
  return proxyToBackend(req);
}
export function PUT(req: NextRequest) {
  return proxyToBackend(req);
}
export function PATCH(req: NextRequest) {
  return proxyToBackend(req);
}
export function DELETE(req: NextRequest) {
  return proxyToBackend(req);
}
