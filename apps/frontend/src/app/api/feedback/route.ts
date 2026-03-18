import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/auth';
import { getServerBackendUrl } from '@/utils/url-resolver';

export async function POST(req: NextRequest) {
  try {
    const { feedback, email, rating } = await req.json();

    if (!feedback || feedback.trim() === '') {
      return NextResponse.json(
        { error: 'Feedback content is required' },
        { status: 400 }
      );
    }

    const session = await auth();
    const userEmail = session?.user?.email || email || undefined;
    const userName = session?.user?.name || undefined;

    const backendUrl = `${getServerBackendUrl()}/feedback/`;

    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        feedback,
        user_name: userName,
        user_email: userEmail,
        rating,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        { error: data.message || 'Failed to send feedback' },
        { status: response.status }
      );
    }

    return NextResponse.json({
      success: data.success,
      message: data.message,
    });
  } catch (error) {
    console.error('Error in feedback route:', error);
    return NextResponse.json(
      { error: 'Failed to send feedback' },
      { status: 500 }
    );
  }
}
