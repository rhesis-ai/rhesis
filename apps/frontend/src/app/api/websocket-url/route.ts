import { NextResponse } from 'next/server';
import { getServerBackendUrl } from '@/utils/url-resolver';
import { deriveWebSocketUrl } from '@/utils/websocket-url';

export function GET() {
  return NextResponse.json(
    {
      url: deriveWebSocketUrl(getServerBackendUrl()),
    },
    {
      headers: {
        'Cache-Control': 'no-store',
      },
    }
  );
}
