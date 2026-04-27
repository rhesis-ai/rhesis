import { NextResponse } from 'next/server';

export function GET() {
  return NextResponse.json(
    {
      enabled: process.env.QUICK_START === 'true',
    },
    {
      headers: {
        'Cache-Control': 'no-store',
      },
    }
  );
}
