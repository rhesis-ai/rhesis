import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/auth';
import { getServerBackendUrl } from '@/utils/url-resolver';

export async function POST(req: NextRequest) {
  try {
    // Get session to verify user is authenticated
    const session = await auth();

    if (!session?.session_token) {
      return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 });
    }

    // Get request data from body
    const body = await req.json();

    // Forward to backend API
    const backendUrl = `${getServerBackendUrl()}/users/request-polyphemus-access`;

    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${session.session_token}`,
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Error in request-polyphemus-access route:', error);
    return NextResponse.json(
      { detail: 'Failed to submit access request' },
      { status: 500 }
    );
  }
}
