import { NextResponse } from 'next/server';
import { isAllowedOgMetadataUrl } from '@/app/api/og-metadata/og-metadata-utils';
import { parseCommaSeparatedUrls } from '@/constants/entity-empty-state-env';

// Read per request so the value comes from the container environment;
// changing the URLs is a values change plus a rollout, not a rebuild.
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
