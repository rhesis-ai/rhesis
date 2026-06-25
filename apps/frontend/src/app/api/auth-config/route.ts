import { NextRequest } from 'next/server';
import { proxyToBackend } from '@/utils/backend-proxy';

export const dynamic = 'force-dynamic';

/**
 * Same-origin proxy for `GET /auth/providers` on the backend.
 *
 * Maps `/api/auth-config` → backend `/auth/providers` so the browser
 * makes a same-origin request, avoiding CORS when the frontend and
 * backend run on different origins.
 */
export function GET(request: NextRequest) {
  return proxyToBackend(request, {
    backendPath: '/auth/providers',
    timeoutMs: 15_000,
  });
}
