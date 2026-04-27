import { NextResponse } from 'next/server';
import { deriveWebSocketUrl } from '@/utils/websocket-url';

export function GET() {
  const backendUrl = process.env.BACKEND_URL || 'http://backend:8080';

  return NextResponse.json(
    {
      url: deriveWebSocketUrl(backendUrl),
    },
    {
      headers: {
        'Cache-Control': 'no-store',
      },
    }
  );
}
