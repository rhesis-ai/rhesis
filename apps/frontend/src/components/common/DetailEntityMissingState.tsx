'use client';

import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { DeletedEntityAlert } from '@/components/common/DeletedEntityAlert';
import DetailNotFoundState from '@/components/common/DetailNotFoundState';
import {
  getDeletedEntityData,
  isDeletedEntityError,
} from '@/utils/entity-error-handler';
import { is404ApiError } from '@/utils/api-client/is-not-found-error';

interface Breadcrumb {
  label: string;
  href?: string;
}

interface DetailEntityMissingStateProps {
  error: unknown;
  entityLabel: string;
  entityId: string;
  entityTableName: string;
  breadcrumbs: Breadcrumb[];
  listUrl?: string;
  onBack: () => void;
  onRetry?: () => void;
  isRetrying?: boolean;
}

/**
 * Routes client-side entity fetch failures to restore UI (410) or cross-project
 * not-found handling (404).
 */
export default function DetailEntityMissingState({
  error,
  entityLabel,
  entityId,
  entityTableName,
  breadcrumbs,
  listUrl,
  onBack,
  onRetry,
  isRetrying,
}: DetailEntityMissingStateProps) {
  const { data: session } = useSession();

  if (isDeletedEntityError(error)) {
    const deletedData = getDeletedEntityData(error);
    if (deletedData) {
      const displayName =
        deletedData.model_name_display || deletedData.model_name || entityLabel;
      const pageTitle = deletedData.item_name
        ? `${deletedData.item_name} (Deleted)`
        : `${displayName} Deleted`;

      return (
        <PageLayout title={pageTitle} breadcrumbs={breadcrumbs}>
          <DeletedEntityAlert
            entityData={deletedData}
            sessionToken={session?.session_token}
            backUrl={listUrl}
            backLabel={
              listUrl ? `Back to ${entityLabel}s` : `Back to ${entityLabel}`
            }
            onRestoreSuccess={() => window.location.reload()}
          />
        </PageLayout>
      );
    }
  }

  if (is404ApiError(error)) {
    return (
      <DetailNotFoundState
        entityLabel={entityLabel}
        entityId={entityId}
        entityTableName={entityTableName}
        breadcrumbs={breadcrumbs}
        listUrl={listUrl}
        onBack={onBack}
        onRetry={onRetry}
        isRetrying={isRetrying}
      />
    );
  }

  return null;
}
