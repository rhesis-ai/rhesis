/**
 * Parse a YouTube watch/short/embed URL into an embeddable iframe src.
 */
export function getOnboardingVideoEmbedUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  try {
    const url = new URL(trimmed);

    if (url.hostname.includes('youtube.com')) {
      const videoId =
        url.searchParams.get('v') ??
        (url.pathname.startsWith('/embed/')
          ? url.pathname.split('/embed/')[1]?.split('/')[0]
          : null);
      if (videoId) {
        return `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0`;
      }
    }

    if (url.hostname === 'youtu.be') {
      const videoId = url.pathname.slice(1).split('/')[0];
      if (videoId) {
        return `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0`;
      }
    }

    if (url.hostname.includes('vimeo.com')) {
      const parts = url.pathname.split('/').filter(Boolean);
      const videoId = parts[parts.length - 1];
      if (videoId && /^\d+$/.test(videoId)) {
        return `https://player.vimeo.com/video/${videoId}?autoplay=1`;
      }
    }

    // Already an embed URL or other iframe-compatible URL
    if (
      url.pathname.includes('/embed/') ||
      url.hostname.includes('player.vimeo.com')
    ) {
      const separator = url.search ? '&' : '?';
      return `${trimmed}${separator}autoplay=1`;
    }
  } catch {
    return null;
  }

  return null;
}

/**
 * YouTube thumbnail for a watch/short URL (maxresdefault with hqdefault fallback).
 */
export function getYouTubeThumbnailUrl(raw: string): string | null {
  const embedUrl = getOnboardingVideoEmbedUrl(raw);
  if (!embedUrl) return null;

  const match = embedUrl.match(/\/embed\/([^?&/]+)/);
  if (!match?.[1]) return null;

  return `https://img.youtube.com/vi/${match[1]}/hqdefault.jpg`;
}

export function getOnboardingVideoUrl(): string | undefined {
  return process.env.NEXT_PUBLIC_ONBOARDING_VIDEO_URL?.trim() || undefined;
}
