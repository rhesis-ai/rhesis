import { NextRequest, NextResponse } from 'next/server';
import { applyRefreshedSessionCookie, getFreshAccessToken } from '@/auth';
import { getServerBackendUrl } from '@/utils/url-resolver';

export async function POST(req: NextRequest) {
  try {
    const { accessToken, refreshedCookie } = await getFreshAccessToken({
      headers: req.headers,
    });

    if (!accessToken) {
      return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 });
    }

    const body = await req.json();

    const backendUrl = `${getServerBackendUrl()}/users/request-polyphemus-access`;

    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      const errorResponse = NextResponse.json(data, {
        status: response.status,
      });
      applyRefreshedSessionCookie(errorResponse, refreshedCookie);
      return errorResponse;
    }

    const successResponse = NextResponse.json(data);
    applyRefreshedSessionCookie(successResponse, refreshedCookie);
    return successResponse;
  } catch (error) {
    console.error('Error in request-polyphemus-access route:', error);
    return NextResponse.json(
      { detail: 'Failed to submit access request' },
      { status: 500 }
    );
  }
}
