'use client';

import { useMemo } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Typography,
} from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import { CrossProjectAlert } from '@/components/common/CrossProjectAlert';
import { useCrossProjectResolve } from '@/hooks/useCrossProjectResolve';
import {
  buildNotFoundEntityData,
  NotFoundEntityData,
} from '@/utils/entity-error-handler';

interface Breadcrumb {
  label: string;
  href?: string;
}

interface DetailNotFoundStateProps {
  entityLabel: string;
  entityId: string;
  /** Database table name for the /resolve endpoint (e.g. "endpoint", "task"). */
  entityTableName: string;
  /** Structured data from a 404 API response, when available. */
  entityData?: NotFoundEntityData;
  breadcrumbs: Breadcrumb[];
  listUrl?: string;
  onBack: () => void;
  onRetry?: () => void;
  isRetrying?: boolean;
}

/**
 * Shared not-found UI for entity detail pages.
 * Attempts cross-project resolution, then falls back to a standard warning.
 */
export default function DetailNotFoundState({
  entityLabel,
  entityId,
  entityTableName,
  entityData: entityDataProp,
  breadcrumbs,
  listUrl,
  onBack,
  onRetry,
  isRetrying = false,
}: DetailNotFoundStateProps) {
  const { crossProjectData, isResolving } = useCrossProjectResolve(
    entityTableName,
    entityId
  );

  const entityData = useMemo(
    () =>
      entityDataProp ??
      buildNotFoundEntityData({
        entityLabel,
        entityId,
        tableName: entityTableName,
        listUrl,
      }),
    [entityDataProp, entityLabel, entityId, entityTableName, listUrl]
  );

  const displayLabel =
    entityData.model_name_display || entityData.model_name || entityLabel;

  const pageTitle = crossProjectData
    ? crossProjectData.resolution === 'no_access'
      ? `${displayLabel} — No access`
      : `${displayLabel} in another project`
    : `${displayLabel} not found`;

  if (isResolving) {
    return (
      <PageLayout title={pageTitle} breadcrumbs={breadcrumbs}>
        <Box sx={{ flexGrow: 1, pt: 3 }}>
          <Alert severity="info">Checking other projects...</Alert>
        </Box>
      </PageLayout>
    );
  }

  if (crossProjectData) {
    return (
      <PageLayout title={pageTitle} breadcrumbs={breadcrumbs}>
        <Box sx={{ flexGrow: 1, pt: 3 }}>
          <CrossProjectAlert
            resolvedEntity={crossProjectData}
            entityData={entityData}
          />
        </Box>
      </PageLayout>
    );
  }

  const listLabel = displayLabel.endsWith('s') ? displayLabel : `${displayLabel}s`;

  return (
    <PageLayout title={pageTitle} breadcrumbs={breadcrumbs}>
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            Sorry, we couldn&apos;t load this {displayLabel.toLowerCase()}
          </Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {entityData.message}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {displayLabel} ID: {entityId}
          </Typography>
        </Alert>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button variant="contained" onClick={onBack}>
            Back to {listLabel}
          </Button>
          {onRetry && (
            <Button variant="outlined" onClick={onRetry} disabled={isRetrying}>
              {isRetrying ? (
                <>
                  <CircularProgress color="inherit" size={16} sx={{ mr: 1 }} />
                  Retrying...
                </>
              ) : (
                'Try Again'
              )}
            </Button>
          )}
        </Box>
      </Box>
    </PageLayout>
  );
}
