import { notFound } from 'next/navigation';
import {
  getApiErrorStatus,
  is404ApiError,
} from '@/utils/api-client/is-not-found-error';

/**
 * Server-component helper: route entity 404 responses to the shared not-found
 * page instead of the error boundary. A 422 on a get-by-id means the path id
 * is not a UUID, so it is treated as not found too. Soft-deleted entities
 * (410) are left to propagate so ``error.tsx`` can render restore UI.
 */
export function notFoundIfEntityMissing(error: unknown): void {
  if (is404ApiError(error) || getApiErrorStatus(error) === 422) {
    notFound();
  }
}
