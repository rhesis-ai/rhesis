export interface ValidationStatus {
  isValid: boolean;
  isValidating: boolean;
  errorMessage?: string;
}

/**
 * Human-readable copy for the `availability_reason` slugs the backend sends on
 * unavailable models. Unknown slugs fall back to {@link GENERIC_UNAVAILABLE_COPY}.
 */
export const AVAILABILITY_REASON_COPY: Record<string, string> = {
  rhesis_key_missing: 'Set a Rhesis API key to enable this model.',
  rhesis_key_invalid:
    'This Rhesis API key is invalid. Update it to enable this model.',
  polyphemus_not_authorized:
    'This Rhesis API key is not authorized for Polyphemus.',
};

export const GENERIC_UNAVAILABLE_COPY = 'This model is currently unavailable.';

/** Maps an `availability_reason` slug to its user-facing message. */
export function getAvailabilityReasonCopy(
  reason?: string | null
): string {
  if (reason && reason in AVAILABILITY_REASON_COPY) {
    return AVAILABILITY_REASON_COPY[reason];
  }
  return GENERIC_UNAVAILABLE_COPY;
}
