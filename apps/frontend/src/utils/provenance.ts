/**
 * Tells the backend which client a request came from and, for calls the
 * Next.js server makes on a browser's behalf, which browser. The backend's
 * audit log and rate limits read these.
 */

/** Client channel header; the UI always reports `web`. */
export const CLIENT_HEADER = 'x-rhesis-client';
export const WEB_CLIENT = 'web';

/**
 * The browser's IP. The backend trusts it only on in-cluster calls (no
 * `X-Forwarded-For`), which is how the Next.js server reaches it.
 */
export const CLIENT_IP_HEADER = 'x-rhesis-client-ip';

/** The browser's IP as the ingress reported it, if any. */
export function browserIp(headers: Headers): string | null {
  const realIp = headers.get('x-real-ip')?.trim();
  if (realIp) return realIp;
  const forwardedFor = headers.get('x-forwarded-for')?.split(',')[0]?.trim();
  return forwardedFor || null;
}

/** Headers that identify the UI and the browser it is serving. */
export function webClientHeaders(incoming?: Headers): Record<string, string> {
  const headers: Record<string, string> = { [CLIENT_HEADER]: WEB_CLIENT };
  const ip = incoming ? browserIp(incoming) : null;
  if (ip) headers[CLIENT_IP_HEADER] = ip;
  return headers;
}
