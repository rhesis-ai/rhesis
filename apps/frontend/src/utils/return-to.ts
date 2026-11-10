import { DEFAULT_AUTHENTICATED_PATH } from '@/constants/paths';

/** Query parameter that carries the post-login destination. */
export const RETURN_TO_PARAM = 'return_to';

// Placeholder origin used only to parse the value; never navigated to.
const PARSE_BASE = 'https://return-to.invalid';

// Browsers read "\" as "/" and drop tab/newline, so "/\host" or "/<TAB>/host"
// would leave the origin. Reject them instead of normalising.
const UNSAFE_CHARS = /[\u0000-\u001F\u007F\\]/;

/**
 * Returns `value` when it is a same-origin relative path, otherwise
 * `fallback`. Use for every post-login redirect target taken from the URL.
 */
export function safeReturnTo(
  value: string | null | undefined,
  fallback: string = DEFAULT_AUTHENTICATED_PATH
): string {
  if (typeof value !== 'string') return fallback;
  if (!value.startsWith('/') || value.startsWith('//')) return fallback;
  if (UNSAFE_CHARS.test(value)) return fallback;

  try {
    const url = new URL(value, PARSE_BASE);
    if (url.origin !== PARSE_BASE) return fallback;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return fallback;
  }
}
