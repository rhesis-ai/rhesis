/**
 * Parse a YouTube watch/short/embed URL into an embeddable iframe src.
 * Only allowlisted YouTube/Vimeo hostnames are accepted.
 */
export function getOnboardingVideoEmbedUrl(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  try {
    const url = new URL(trimmed);
    const { hostname } = url;

    if (isYouTubeHost(hostname)) {
      const videoId =
        url.searchParams.get('v') ??
        (url.pathname.startsWith('/embed/')
          ? url.pathname.split('/embed/')[1]?.split('/')[0]
          : null);
      if (videoId && isValidVideoId(videoId)) {
        return `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0`;
      }
    }

    if (hostname === 'youtu.be') {
      const videoId = url.pathname.slice(1).split('/')[0];
      if (videoId && isValidVideoId(videoId)) {
        return `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0`;
      }
    }

    if (hostname === 'vimeo.com' || hostname === 'www.vimeo.com') {
      const parts = url.pathname.split('/').filter(Boolean);
      const videoId = parts[parts.length - 1];
      if (videoId && /^\d+$/.test(videoId)) {
        return `https://player.vimeo.com/video/${videoId}?autoplay=1`;
      }
    }

    if (hostname === 'player.vimeo.com') {
      const match = url.pathname.match(/^\/video\/(\d+)/);
      if (match?.[1]) {
        return `https://player.vimeo.com/video/${match[1]}?autoplay=1`;
      }
    }
  } catch {
    return null;
  }

  return null;
}

function isYouTubeHost(hostname: string): boolean {
  return (
    hostname === 'youtube.com' ||
    hostname === 'www.youtube.com' ||
    hostname === 'm.youtube.com' ||
    hostname.endsWith('.youtube.com')
  );
}

function isValidVideoId(videoId: string): boolean {
  return /^[\w-]{11}$/.test(videoId);
}

/** Extract a YouTube video ID from a raw ID or watch/short/embed URL. */
export function parseYouTubeVideoId(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  if (isValidVideoId(trimmed)) return trimmed;

  const embedUrl = getOnboardingVideoEmbedUrl(trimmed);
  if (!embedUrl) return null;

  const match = embedUrl.match(/\/embed\/([^?&/]+)/);
  return match?.[1] ?? null;
}

/**
 * YouTube thumbnail for a watch/short URL or raw video ID.
 * Defaults to maxresdefault; use hqdefault as fallback in the UI on error.
 */
export function getYouTubeThumbnailUrl(
  raw: string,
  quality: 'maxresdefault' | 'hqdefault' = 'maxresdefault'
): string | null {
  const videoId = parseYouTubeVideoId(raw);
  if (!videoId) return null;

  return `https://img.youtube.com/vi/${videoId}/${quality}.jpg`;
}

export function getYouTubeWatchUrl(raw: string): string | null {
  const videoId = parseYouTubeVideoId(raw);
  if (!videoId) return null;
  return `https://www.youtube.com/watch?v=${videoId}`;
}

export function getOnboardingVideoUrl(): string | undefined {
  return (
    process.env.ONBOARDING_VIDEO_URL?.trim() ||
    process.env.NEXT_PUBLIC_ONBOARDING_VIDEO_URL?.trim() ||
    undefined
  );
}
