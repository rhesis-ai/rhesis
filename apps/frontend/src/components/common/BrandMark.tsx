'use client';

import React from 'react';
import Image from 'next/image';
import { DEFAULT_FAVICON_URL } from '@/config/branding';

interface BrandMarkProps {
  /** `BRAND_FAVICON_URL` when configured; falls back to the Rhesis icon. */
  src?: string;
  /** Rendered size in px — the mark is always square. */
  size: number;
  alt: string;
  priority?: boolean;
}

/**
 * The square brand mark in the app chrome, honouring `BRAND_FAVICON_URL` so a
 * rebranded deployment shows its own icon next to the organisation name instead
 * of the Rhesis platypus.
 *
 * A remote URL renders as a plain `<img>`, not `next/image`: the optimizer
 * refuses any host absent from `images.remotePatterns`, and the host here is
 * whatever a deployment put in its values file — unknowable at build time.
 * Widening `remotePatterns` to `**` to work around that would turn the
 * optimizer into an open image proxy. Favicons are a few KB, so there is
 * nothing to optimise anyway. Local paths keep `next/image`.
 */
export default function BrandMark({
  src,
  size,
  alt,
  priority = false,
}: BrandMarkProps) {
  const resolved = src || DEFAULT_FAVICON_URL;
  const isRemote = /^https?:\/\//i.test(resolved);

  if (isRemote) {
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
