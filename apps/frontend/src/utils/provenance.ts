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

/**
 * The browser's IP as the proxy in front of this server saw it, if any.
 *
 * Sign-in reaches the backend only through here, so this IP keys the sign-in
 * rate limits and the audit log. Only the right-most X-Forwarded-For entry is
 * trustworthy: the nearest proxy appended it, and everything to its left is
 * whatever the client sent. ingress-nginx and AWS ALB both append the client
 * address there. X-Real-IP is the fallback only, because a proxy that doesn't
 * set it (an ALB) passes a client's own value through.
 */
export function browserIp(headers: Headers): string | null {
  const forwardedFor = headers
    .get('x-forwarded-for')
    ?.split(',')
    .at(-1)
    ?.trim();
  if (forwardedFor) return forwardedFor;
  return headers.get('x-real-ip')?.trim() || null;
}

/** Headers that identify the UI and the browser it is serving. */
export function webClientHeaders(incoming?: Headers): Record<string, string> {
  const headers: Record<string, string> = { [CLIENT_HEADER]: WEB_CLIENT };
  const ip = incoming ? browserIp(incoming) : null;
  if (ip) headers[CLIENT_IP_HEADER] = ip;
  return headers;
}
