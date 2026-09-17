'use client';

import React from 'react';
import Image from 'next/image';
import { DEFAULT_FAVICON_URL, isBrandAssetUrl } from '@/config/branding';

interface BrandMarkProps {
  /** The resolved brand favicon — an organisation upload, `BRAND_FAVICON_URL`,
   *  or the Rhesis icon. */
  src?: string;
  /** Rendered size in px — the mark is always square. */
  size: number;
  alt: string;
  priority?: boolean;
}

/**
 * The square brand mark in the app chrome, honouring the organisation's own
 * favicon and `BRAND_FAVICON_URL` so a rebranded deployment shows its own icon
 * next to the organisation name instead of the Rhesis platypus.
 *
 * Two kinds of source bypass `next/image` and render as a plain `<img>`:
 *
 * - A remote URL, because the optimizer refuses any host absent from
 *   `images.remotePatterns`, and the host here is whatever a deployment put in
 *   its values file — unknowable at build time. Widening `remotePatterns` to
 *   `**` to work around that would turn the optimizer into an open image proxy.
 * - An organisation upload under `/brand-assets/`, because the optimizer
 *   fetches the URL server-side, and that request carries no session cookie —
 *   the very thing the route needs to know which organisation is asking. It
 *   would get a 401 and the mark would never render. (It would also reject an
 *   SVG outright, since `dangerouslyAllowSVG` is off.)
 *
 * Favicons are a few KB, so there is nothing to optimise in either case. Only
 * shipped local paths keep `next/image`.
 */
export default function BrandMark({
  src,
  size,
  alt,
  priority = false,
}: BrandMarkProps) {
  const resolved = src || DEFAULT_FAVICON_URL;
  const bypassOptimizer =
    /^https?:\/\//i.test(resolved) || isBrandAssetUrl(resolved);

  if (bypassOptimizer) {
    return (
      <img
        src={resolved}
        alt={alt}
        width={size}
        height={size}
        // Keeps a non-square source from stretching, and stops a broken or
        // slow remote icon from shifting the sidebar layout.
        style={{ width: size, height: size, objectFit: 'contain' }}
        {...(priority ? { fetchPriority: 'high' as const } : {})}
      />
    );
  }

  return (
    <Image
      src={resolved}
      alt={alt}
      width={size}
      height={size}
      priority={priority}
    />
  );
}
