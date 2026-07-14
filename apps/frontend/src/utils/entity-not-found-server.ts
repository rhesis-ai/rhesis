import { notFound } from 'next/navigation';
import { is404ApiError } from '@/utils/api-client/is-not-found-error';

/**
 * Server-component helper: route entity 404 responses to the shared not-found
 * page instead of the error boundary. Soft-deleted entities (410) are left to
 * propagate so ``error.tsx`` can render restore UI.
 */
export function notFoundIfEntityMissing(error: unknown): void {
  if (is404ApiError(error)) {
    notFound();
  }
}
