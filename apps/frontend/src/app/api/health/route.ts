import { NextResponse } from 'next/server';

// Static so probes never render a page or fetch anything — they used to hit `/` every 10s.
export const dynamic = 'force-static';

export function GET() {
  return NextResponse.json({ status: 'ok' });
}
