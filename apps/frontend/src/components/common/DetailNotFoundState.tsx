'use client';

import { useMemo, type ReactNode } from 'react';
import { Box } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import RefreshIcon from '@mui/icons-material/RefreshOutlined';
import { PageLayout } from '@/components/layout/PageLayout';
import { CrossProjectAlert } from '@/components/common/CrossProjectAlert';
import EntityMessageState from '@/components/common/EntityMessageState';
import { useCrossProjectResolve } from '@/hooks/useCrossProjectResolve';
import {
  buildNotFoundEntityData,
  NotFoundEntityData,
} from '@/utils/entity-error-handler';
import {
  FolderOffOutlinedIcon,
  getResolveEntityIcon,
} from '@/utils/entity-detail-icons';
import { AccountTreeIcon } from '@/components/icons';

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

  const EntityIcon =
    entityLabel === 'Session'
      ? AccountTreeIcon
      : getResolveEntityIcon(entityTableName);

  const pageTitle = crossProjectData
    ? crossProjectData.resolution === 'no_access'
      ? `${displayLabel} — No access`
      : `${displayLabel} in another project`
    : `${displayLabel} not found`;

  const contentWrapper = (children: ReactNode) => (
    <PageLayout title={pageTitle} breadcrumbs={breadcrumbs}>
      <Box sx={{ mt: 2, mb: 2 }}>{children}</Box>
    </PageLayout>
  );

  if (isResolving) {
    return contentWrapper(
      <EntityMessageState
        icon={EntityIcon}
        title="Checking other projects..."
        description="Looking for this item in projects you have access to."
        loading
      />
    );
  }

  if (crossProjectData) {
    return contentWrapper(
      <CrossProjectAlert
        resolvedEntity={crossProjectData}
        entityData={entityData}
      />
    );
  }

  const listLabel = displayLabel.endsWith('s')
    ? displayLabel
    : `${displayLabel}s`;

  return contentWrapper(
    <EntityMessageState
      icon={FolderOffOutlinedIcon}
      title={`Couldn't load this ${displayLabel.toLowerCase()}`}
      description={entityData.message}
      meta={`${displayLabel} ID: ${entityId}`}
      primaryAction={{
        label: `Back to ${listLabel}`,
        onClick: onBack,
        startIcon: <ArrowBackIcon />,
        variant: 'contained',
      }}
      secondaryAction={
        onRetry
          ? {
              label: isRetrying ? 'Retrying...' : 'Try Again',
              onClick: onRetry,
              startIcon: <RefreshIcon />,
              disabled: isRetrying,
              loading: isRetrying,
            }
          : undefined
      }
    />
  );
}
