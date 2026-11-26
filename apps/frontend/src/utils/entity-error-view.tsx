import type * as React from 'react';
import EntityErrorState from '@/components/common/EntityErrorState';
import { getApiErrorStatus } from '@/utils/api-client/is-not-found-error';
import { getDeletedEntityData } from '@/utils/entity-error-handler';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';

/**
 * Server-component helper for a detail page whose record fetch failed: a
 * missing record goes to the not-found page, and a forbidden (403) or deleted
 * (410) one comes back as the page to render. Anything else returns null for
 * the caller to rethrow.
 *
 * Rendered rather than thrown because production builds strip a server
 * error's message and data before the error boundary sees them, so the
 * boundary could only show a generic error.
 */
export function entityErrorView(error: unknown): React.ReactElement | null {
  notFoundIfEntityMissing(error);
  const status = getApiErrorStatus(error);
  if (status === 403) {
    return <EntityErrorState kind="forbidden" />;
  }
  if (status === 410) {
    const deletedEntity = getDeletedEntityData(error);
    if (deletedEntity) {
      return <EntityErrorState kind="deleted" deletedEntity={deletedEntity} />;
    }
  }
  return null;
}
