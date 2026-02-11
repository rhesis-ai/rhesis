/**
 * Extract a user-friendly error message from import API errors.
 *
 * Handles various error shapes:
 * - detail as string
 * - detail as { message, errors }
 * - detail as array (422 ValidationError)
 * - err.message from fetch errors
 * - 5xx: always return generic message
 */

const MAX_MESSAGE_LENGTH = 300;
const MAX_ERRORS = 3;
const FALLBACK = 'Import failed. Please try again.';

export function getImportErrorMessage(
  error: unknown,
  fallback: string = FALLBACK
): string {
  const err = error as Error & { status?: number; data?: unknown };
  const status = err?.status;
  const data = err?.data as { detail?: unknown } | undefined;
  const detail = data?.detail;

  // For 5xx, never expose server details
  if (status && status >= 500) {
    return fallback;
  }

  if (detail === undefined || detail === null) {
    const msg = err?.message;
    if (typeof msg === 'string' && msg.trim()) {
      return truncate(msg, MAX_MESSAGE_LENGTH);
    }
    return fallback;
  }

  // detail is string
  if (typeof detail === 'string') {
    return truncate(detail, MAX_MESSAGE_LENGTH);
  }

  // detail is { message, errors }
  if (typeof detail === 'object' && detail !== null && 'message' in detail) {
    const obj = detail as { message?: string; errors?: string[] };
    const msg = obj.message;
    const errors = Array.isArray(obj.errors) ? obj.errors : [];
    const parts: string[] = [];
    if (typeof msg === 'string' && msg.trim()) {
      parts.push(msg);
    }
    if (errors.length > 0) {
      parts.push(errors.slice(0, MAX_ERRORS).join('; '));
    }
    const result = parts.join(' ');
    return result ? truncate(result, MAX_MESSAGE_LENGTH) : fallback;
  }

  // detail is array (422 request validation)
  if (Array.isArray(detail)) {
    const lines = detail
      .slice(0, MAX_ERRORS)
      .map(
        (e: { loc?: unknown[]; msg?: string }) =>
          `${(e.loc || []).join('.') || 'field'}: ${e.msg || 'Invalid value'}`
      );
    const result = lines.join('. ');
    return result ? truncate(result, MAX_MESSAGE_LENGTH) : fallback;
  }

  return fallback;
}

function truncate(s: string, max: number): string {
  const trimmed = s.trim();
  if (trimmed.length <= max) return trimmed;
  return trimmed.slice(0, max) + '…';
}
