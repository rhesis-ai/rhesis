import { NextRequest, NextResponse } from 'next/server';
import {
  fetchAllowedPage,
  isAllowedOgMetadataUrl,
} from '@/app/api/og-metadata/og-metadata-utils';

function extractMetaContent(
  html: string,
  attr: 'property' | 'name',
  key: string
) {
  const patterns = [
    new RegExp(
      `<meta[^>]+${attr}=["']${key}["'][^>]+content=["']([^"']+)["']`,
      'i'
    ),
    new RegExp(
      `<meta[^>]+content=["']([^"']+)["'][^>]+${attr}=["']${key}["']`,
      'i'
    ),
  ];

  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (match?.[1]) {
      return match[1].trim();
    }
  }

  return null;
}

function extractTitle(html: string): string | null {
  const match = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  return match?.[1]?.trim() ?? null;
}

export async function GET(req: NextRequest) {
  const rawUrl = req.nextUrl.searchParams.get('url')?.trim();
  if (!rawUrl) {
    return NextResponse.json({ error: 'url is required' }, { status: 400 });
  }

  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return NextResponse.json({ error: 'invalid url' }, { status: 400 });
  }

  if (!isAllowedOgMetadataUrl(parsed)) {
    return NextResponse.json({ error: 'host not allowed' }, { status: 403 });
  }

  try {
    const response = await fetchAllowedPage(parsed);

    if (!response?.ok) {
      return NextResponse.json(
        { error: 'failed to fetch page' },
        { status: 502 }
      );
    }

    const html = await response.text();
    const title =
      extractMetaContent(html, 'property', 'og:title') ?? extractTitle(html);
    const description =
      extractMetaContent(html, 'property', 'og:description') ??
      extractMetaContent(html, 'name', 'description');
    const imageUrl = extractMetaContent(html, 'property', 'og:image');

    return NextResponse.json(
      { title, description, imageUrl },
      {
        headers: {
          'Cache-Control': 'public, max-age=86400, stale-while-revalidate=3600',
        },
      }
    );
  } catch {
    return NextResponse.json({ error: 'fetch failed' }, { status: 502 });
  }
}
