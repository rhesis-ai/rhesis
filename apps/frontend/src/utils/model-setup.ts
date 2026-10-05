/**
 * The one place the frontend reacts to "no usable model". The API client and
 * the WebSocket client report the code here and `ModelSetupGate` listens, so
 * pages do not handle it themselves.
 */

/** Mirrors `MODEL_NOT_CONFIGURED` in the backend's `utils/model_errors.py`. */
export const MODEL_NOT_CONFIGURED_ERROR_CODE = 'model_not_configured';

const MODEL_NOT_CONFIGURED_EVENT = 'rhesis:model-not-configured';

function hasErrorCode(value: unknown): boolean {
  return (
    typeof value === 'object' &&
    value !== null &&
    (value as { error_code?: unknown }).error_code ===
      MODEL_NOT_CONFIGURED_ERROR_CODE
  );
}

/**
 * True when a FastAPI `detail` body or a WebSocket payload carries the code.
 * Also looks one level down into `checks`, where a preflight summary lists
 * its per-check results.
 */
export function isModelNotConfigured(value: unknown): boolean {
  if (hasErrorCode(value)) return true;
  if (typeof value !== 'object' || value === null) return false;
  const checks = (value as { checks?: unknown }).checks;
  return Array.isArray(checks) && checks.some(hasErrorCode);
}

/** Tell the app a model check failed. Does nothing on the server. */
export function reportModelNotConfigured(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(MODEL_NOT_CONFIGURED_EVENT));
}

/** Subscribe to `reportModelNotConfigured()`. Returns the unsubscribe. */
export function onModelNotConfigured(listener: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  window.addEventListener(MODEL_NOT_CONFIGURED_EVENT, listener);
  return () => window.removeEventListener(MODEL_NOT_CONFIGURED_EVENT, listener);
}
