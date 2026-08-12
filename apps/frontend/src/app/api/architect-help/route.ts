import { NextResponse } from 'next/server';
import { isAllowedOgMetadataUrl } from '@/app/api/og-metadata/og-metadata-utils';
import { parseCommaSeparatedUrls } from '@/constants/entity-empty-state-env';

// Read per request so the value comes from the container environment. The
// NEXT_PUBLIC_* empty-state vars are inlined into the browser bundle at build
// time, which the GCP Secret Manager → ESO pipeline cannot feed; this one is
// deliberately unprefixed and served from the server instead, so changing the
// URLs is a secret update plus a rollout restart rather than a rebuild.
export const dynamic = 'force-dynamic';

/**
 * Docs articles offered on the Architect welcome screen when the active project
 * has no endpoint yet. Cards render titles/descriptions/images from each page's
 * OG tags via /api/og-metadata.
 */
export function GET() {
  const configured = parseCommaSeparatedUrls(
    process.env.ARCHITECT_HELP_ARTICLE_URLS?.trim()
  );

  // Same allowlist /api/og-metadata enforces — drop misconfigured hosts here so
  // they never become cards whose metadata fetch is guaranteed to 403.
  const articleUrls = configured.filter(url => {
    try {
      return isAllowedOgMetadataUrl(new URL(url));
    } catch {
      return false;
    }
  });

  return NextResponse.json({ articleUrls });
}
