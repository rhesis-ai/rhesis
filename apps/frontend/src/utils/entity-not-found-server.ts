import { notFound } from 'next/navigation';
import { isNotFoundApiError } from '@/utils/api-client/is-not-found-error';

/**
 * Server-component helper: route entity 404/410 responses to the shared
 * not-found page instead of the error boundary.
 */
export function notFoundIfEntityMissing(error: unknown): void {
  if (isNotFoundApiError(error)) {
    notFound();
  }
}
