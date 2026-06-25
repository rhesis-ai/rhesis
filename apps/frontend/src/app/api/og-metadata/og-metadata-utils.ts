const ALLOWED_HOSTS = new Set(['docs.rhesis.ai', 'www.docs.rhesis.ai']);
const MAX_REDIRECTS = 3;

export function isAllowedOgMetadataUrl(url: URL): boolean {
  return (
    (url.protocol === 'https:' || url.protocol === 'http:') &&
    ALLOWED_HOSTS.has(url.hostname)
  );
}

export function resolveRedirectUrl(location: string, baseUrl: URL): URL | null {
  try {
    const nextUrl = new URL(location, baseUrl);
    return isAllowedOgMetadataUrl(nextUrl) ? nextUrl : null;
  } catch {
    return null;
  }
}

export async function fetchAllowedPage(
  startUrl: URL
): Promise<Response | null> {
  let currentUrl = startUrl;

  for (let hop = 0; hop <= MAX_REDIRECTS; hop += 1) {
    if (!isAllowedOgMetadataUrl(currentUrl)) {
      return null;
    }

    const response = await fetch(currentUrl.toString(), {
      headers: { 'User-Agent': 'RhesisOgMetadata/1.0' },
      redirect: 'manual',
      next: { revalidate: 86400 },
    });

    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get('location');
      if (!location) {
        return null;
      }

      const nextUrl = resolveRedirectUrl(location, currentUrl);
      if (!nextUrl) {
        return null;
      }

      currentUrl = nextUrl;
      continue;
    }

    return response;
  }

  return null;
}
