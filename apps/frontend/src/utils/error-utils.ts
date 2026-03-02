/**
 * Extract a user-facing message from API or other errors.
 *
 * API errors thrown by BaseApiClient have the shape:
 *   message: "API error: 400 - Cannot execute tests due to ..."
 *   data:    { detail: "Cannot execute tests due to ..." }
 *
 * This helper strips the "API error: {status} - " prefix and
 * returns the clean detail string.
 */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    const msg = error.message;
    if (msg.startsWith('API error: ')) {
      const detail = msg.replace(/^API error: \d+ - /, '');
      return detail || fallback;
    }
    return msg;
  }
  return fallback;
}
