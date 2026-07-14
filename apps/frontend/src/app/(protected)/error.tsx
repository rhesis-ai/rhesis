'use client';

import { useEffect, useMemo, useState } from 'react';
import { Paper, Typography, Button, Box, Alert } from '@mui/material';
import { PageLayout } from '@/components/layout/PageLayout';
import Link from 'next/link';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';
import { usePathname } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { DeletedEntityAlert } from '@/components/common/DeletedEntityAlert';
import DetailNotFoundState from '@/components/common/DetailNotFoundState';
import {
  getDeletedEntityData,
  getNotFoundEntityData,
  getErrorMessage,
  isForbiddenError,
  parseEntityFromPathname,
  urlSegmentToResolveEntityType,
} from '@/utils/entity-error-handler';

interface ErrorProps {
  error: Error & {
    digest?: string;
    status?: number;
    data?: Record<string, unknown>;
  };
  reset: () => void;
}

/**
 * Global error handler for all protected routes.
 *
 * Entity 404s render DetailNotFoundState (with cross-project resolution).
 * Deleted entities, forbidden access, and other errors have dedicated UI.
 */
export default function ProtectedError({ error, reset }: ErrorProps) {
  const { data: session } = useSession();
  const [isResetting, setIsResetting] = useState(false);

  const notFoundEntityData = useMemo(
    () => getNotFoundEntityData(error),
    [error]
  );
  const isForbidden = useMemo(() => isForbiddenError(error), [error]);
  const deletedEntityData = useMemo(() => getDeletedEntityData(error), [error]);

  const pathname = usePathname();
  const pathSegments = useMemo(
    () => pathname.split('/').filter(Boolean),
    [pathname]
  );
  const parsedPathEntity = useMemo(
    () => parseEntityFromPathname(pathname),
    [pathname]
  );

  const backUrl = useMemo(() => {
    if (parsedPathEntity?.listUrl) {
      return parsedPathEntity.listUrl;
    }
    if (pathSegments.length > 1) {
      return `/${pathSegments[0]}`;
    }
    return '/';
  }, [parsedPathEntity, pathSegments]);

  const formatEntityName = (segment: string): string => {
    return segment
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const breadcrumbs = useMemo(() => {
    if (pathSegments.length === 0) return [];

    const entityName = formatEntityName(pathSegments[0]);
    const crumbs = [{ label: entityName, href: `/${pathSegments[0]}` }];

    if (pathSegments.length > 1) {
      const itemId = pathSegments[1];
      let itemTitle = itemId;

      if (deletedEntityData?.item_name) {
        itemTitle = deletedEntityData.item_name;
      } else if (deletedEntityData) {
        const displayName =
          deletedEntityData.model_name_display || deletedEntityData.model_name;
        itemTitle = `${displayName} (${itemId.substring(0, 8)}...)`;
      }

      crumbs.push({
        label: itemTitle,
        href: pathname,
      });
    }

    return crumbs;
  }, [pathSegments, deletedEntityData, pathname]);

  useEffect(() => {
    if (notFoundEntityData) {
      console.warn('Entity not found:', {
        entity: notFoundEntityData.model_name,
        id: notFoundEntityData.item_id,
        message: notFoundEntityData.message,
      });
    } else if (deletedEntityData) {
      console.warn('Deleted entity accessed:', {
        entity: deletedEntityData.model_name,
        id: deletedEntityData.item_id,
        message: deletedEntityData.message,
      });
    } else {
      console.error('Protected route error:', {
        message: error.message,
        status: error.status,
        digest: error.digest,
        stack: error.stack,
      });
    }
  }, [error, notFoundEntityData, deletedEntityData]);

  const pageTitle = useMemo(() => {
    if (isForbidden) {
      if (pathSegments.length > 0) {
        return `${formatEntityName(pathSegments[0])} — Access denied`;
      }
      return 'Access denied';
    }
    if (deletedEntityData) {
      if (deletedEntityData.item_name) {
        return `${deletedEntityData.item_name} (Deleted)`;
      }
      const displayName =
        deletedEntityData.model_name_display || deletedEntityData.model_name;
      return `${displayName} Deleted`;
    }
    return 'Error';
  }, [deletedEntityData, isForbidden, pathSegments]);

  const backLabel = useMemo(() => {
    if (pathSegments.length > 0) {
      return `Back to ${formatEntityName(pathSegments[0])}`;
    }
    return 'Back';
  }, [pathSegments]);

  const handleReset = () => {
    setIsResetting(true);
    reset();
  };

  if (notFoundEntityData) {
    const displayName =
      notFoundEntityData.model_name_display || notFoundEntityData.model_name;

    return (
      <DetailNotFoundState
        entityLabel={displayName}
        entityId={notFoundEntityData.item_id}
        entityTableName={
          notFoundEntityData.table_name ||
          parsedPathEntity?.entityType ||
          (pathSegments[0]
            ? urlSegmentToResolveEntityType(pathSegments[0])
            : 'item')
        }
        entityData={notFoundEntityData}
        listUrl={backUrl}
        breadcrumbs={breadcrumbs}
        onBack={() => window.history.back()}
      />
    );
  }

  return (
    <PageLayout title={pageTitle} breadcrumbs={breadcrumbs}>
      {deletedEntityData ? (
        <DeletedEntityAlert
          entityData={deletedEntityData}
          sessionToken={session?.session_token}
          backUrl={backUrl}
          backLabel={backLabel}
          onRestoreSuccess={() => {
            setTimeout(() => {
              window.location.reload();
            }, 1000);
          }}
        />
      ) : isForbidden ? (
        <Alert severity="warning" icon={<LockOutlinedIcon />}>
          <Box mb={2}>
            <Typography>
              You don't have permission to view this{' '}
              {pathSegments.length > 0
                ? formatEntityName(pathSegments[0])
                    .toLowerCase()
                    .replace(/s$/, '')
                : 'resource'}
              . Contact your project administrator if you need access.
            </Typography>
          </Box>
          <Box display="flex" gap={2} flexWrap="wrap">
            <Button
              variant="outlined"
              size="medium"
              startIcon={<ArrowBackIcon />}
              onClick={() => window.history.back()}
            >
              Back
            </Button>
          </Box>
        </Alert>
      ) : (
        <Paper role="alert" aria-live="assertive" aria-atomic="true">
          <Box p={3}>
            <Typography variant="h6" color="error" gutterBottom>
              Something went wrong
            </Typography>

            <Typography color="error" paragraph>
              {getErrorMessage(error)}
            </Typography>

            {process.env.FRONTEND_ENV === 'development' && error.digest && (
              <Alert severity="info">
                <Typography variant="caption" component="div">
                  <strong>Error Digest:</strong> {error.digest}
                </Typography>
                <Typography variant="caption" component="div">
                  This information helps with debugging in development.
                </Typography>
              </Alert>
            )}

            <Box display="flex" gap={2} flexWrap="wrap" mt={2}>
              <Button
                variant="contained"
                onClick={handleReset}
                disabled={isResetting}
                startIcon={<RefreshIcon />}
                aria-label="Try again to reload this page"
              >
                {isResetting ? 'Reloading...' : 'Try Again'}
              </Button>
              <Button
                component={Link}
                href={backUrl}
                variant="outlined"
                startIcon={<ArrowBackIcon />}
                disabled={isResetting}
                aria-label={backLabel}
              >
                {backLabel}
              </Button>
            </Box>
          </Box>
        </Paper>
      )}
    </PageLayout>
  );
}
