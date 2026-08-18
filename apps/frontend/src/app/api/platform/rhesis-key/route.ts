import { NextRequest, NextResponse } from 'next/server';
import { applyRefreshedSessionCookie, getFreshAccessToken } from '@/auth';
import { getServerBackendUrl } from '@/utils/url-resolver';

export const dynamic = 'force-dynamic';

/**
 * BFF proxy for the deployment-wide Rhesis platform API key.
 *
 * These endpoints only exist when ENABLE_RHESIS_KEY is set on the backend;
 * otherwise the backend returns 404, which we pass through cleanly so the
 * frontend can hide the key-settings UI. Mirrors the
 * `users/request-polyphemus-access` BFF pattern: inject `Authorization`
 * server-side from the httpOnly session cookie, never exposing the access
 * token to the browser.
 */

const BACKEND_PATH = '/platform/rhesis-key';

async function parseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }
  const text = await response.text();
  return text ? { detail: text } : {};
}

async function proxy(
  req: NextRequest,
  method: 'GET' | 'PUT' | 'DELETE'
): Promise<NextResponse> {
  try {
    const { accessToken, refreshedCookie } = await getFreshAccessToken({
      headers: req.headers,
    });

    if (!accessToken) {
      return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 });
    }

    const init: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
    };

    if (method === 'PUT') {
      const body = await req.json();
      init.body = JSON.stringify(body);
    }

    const response = await fetch(
      `${getServerBackendUrl()}${BACKEND_PATH}`,
      init
    );
    const data = await parseBody(response);

    // Pass the backend status through unchanged — including 404 in non-local
    // deployments, which the frontend treats as "feature unavailable".
    const proxied = NextResponse.json(data, { status: response.status });
    applyRefreshedSessionCookie(proxied, refreshedCookie);
    return proxied;
  } catch (error) {
    console.error(`Error in platform/rhesis-key ${method} route:`, error);
    return NextResponse.json(
      { detail: 'Failed to reach platform key service' },
      { status: 500 }
    );
  }
}

export function GET(req: NextRequest) {
  return proxy(req, 'GET');
}

export function PUT(req: NextRequest) {
  return proxy(req, 'PUT');
}

export function DELETE(req: NextRequest) {
  return proxy(req, 'DELETE');
}
