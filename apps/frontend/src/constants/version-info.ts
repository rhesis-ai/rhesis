/**
 * Limits on the free-form `version_info` object clients attach to an endpoint.
 *
 * Mirrored from `apps/backend/src/rhesis/backend/app/schemas/validators.py` — keep the two
 * in lockstep. The backend is authoritative; these exist so the editor can reject a bad
 * value immediately instead of after a round trip.
 */
export const VERSION_INFO_MAX_BYTES = 16 * 1024;
export const VERSION_INFO_MAX_DEPTH = 8;

/** Where a run's recorded version came from. Mirrors the backend's SOURCE_* constants. */
export type VersionInfoSource = 'endpoint' | 'response' | 'rescore';
