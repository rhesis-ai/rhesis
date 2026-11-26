'use client';

import { useMemo } from 'react';
import { Alert, Box, Button, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { usePathname } from 'next/navigation';
import { PageLayout } from '@/components/layout/PageLayout';
import {
  DeletedEntityAlert,
  type DeletedEntityData,
} from '@/components/common/DeletedEntityAlert';
import { parseEntityFromPathname } from '@/utils/entity-error-handler';

function formatEntityName(segment: string): string {
  return segment
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Where an error page sits: its breadcrumbs and the list it leads back to,
 * from the URL, and the record's name when a deleted record supplies one.
 */
export function useEntityErrorContext(
  deletedEntity?: DeletedEntityData | null
) {
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
    if (parsedPathEntity?.listUrl) return parsedPathEntity.listUrl;
    if (pathSegments.length > 1) return `/${pathSegments[0]}`;
    return '/';
  }, [parsedPathEntity, pathSegments]);

  const sectionName =
    pathSegments.length > 0 ? formatEntityName(pathSegments[0]) : undefined;

  const breadcrumbs = useMemo(() => {
    if (!sectionName) return [];
    const crumbs = [{ label: sectionName, href: `/${pathSegments[0]}` }];
    if (pathSegments.length > 1) {
      const itemId = pathSegments[1];
      let itemTitle = itemId;
      if (deletedEntity?.item_name) {
        itemTitle = deletedEntity.item_name;
      } else if (deletedEntity) {
        const displayName =
          deletedEntity.model_name_display || deletedEntity.model_name;
        itemTitle = `${displayName} (${itemId.substring(0, 8)}...)`;
      }
      crumbs.push({ label: itemTitle, href: pathname });
    }
    return crumbs;
  }, [sectionName, pathSegments, deletedEntity, pathname]);

  return {
    pathSegments,
    parsedPathEntity,
    backUrl,
    breadcrumbs,
    sectionName,
    backLabel: sectionName ? `Back to ${sectionName}` : 'Back',
  };
}

export type EntityErrorStateProps =
  | { kind: 'forbidden' }
  | { kind: 'deleted'; deletedEntity: DeletedEntityData };

/**
 * The page for a record the user may not see, or one that was deleted and
 * can be restored. Rendered by detail pages themselves (see
 * `entityErrorView`), since an error thrown from a server component reaches
 * the error boundary without its details in production builds.
 */
export default function EntityErrorState(props: EntityErrorStateProps) {
  const deletedEntity = props.kind === 'deleted' ? props.deletedEntity : null;
  const { breadcrumbs, backUrl, backLabel, sectionName } =
    useEntityErrorContext(deletedEntity);

  if (props.kind === 'deleted') {
    const { deletedEntity: entity } = props;
    const title = entity.item_name
      ? `${entity.item_name} (Deleted)`
      : `${entity.model_name_display || entity.model_name} Deleted`;
    return (
      <PageLayout title={title} breadcrumbs={breadcrumbs}>
        <DeletedEntityAlert
          entityData={entity}
          backUrl={backUrl}
          backLabel={backLabel}
          onRestoreSuccess={() => {
            setTimeout(() => {
              window.location.reload();
            }, 1000);
          }}
        />
      </PageLayout>
    );
  }

  const thing = sectionName
    ? sectionName.toLowerCase().replace(/s$/, '')
    : 'resource';
  return (
    <PageLayout
      title={sectionName ? `${sectionName} — Access denied` : 'Access denied'}
      breadcrumbs={breadcrumbs}
    >
      <Alert severity="warning" icon={<LockOutlinedIcon />}>
        <Box mb={2}>
          <Typography>
            You don&apos;t have permission to view this {thing}. Contact your
            project administrator if you need access.
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
    </PageLayout>
  );
}
