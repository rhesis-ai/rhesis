'use client';

import { useMemo } from 'react';
import { Box } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import SearchIcon from '@mui/icons-material/SearchOutlined';
import FolderOffOutlinedIcon from '@mui/icons-material/FolderOffOutlined';
import { PageLayout } from '@/components/layout/PageLayout';
import { usePathname, useRouter } from 'next/navigation';
import DetailNotFoundState from '@/components/common/DetailNotFoundState';
import EntityMessageState from '@/components/common/EntityMessageState';
import { parseEntityFromPathname } from '@/utils/entity-error-handler';

function formatEntityName(segment: string): string {
  return segment
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function pluralize(name: string): string {
  return name.endsWith('s') ? name : `${name}s`;
}

/**
 * Not-found page for all protected routes.
 *
 * Shown when a server component calls notFound() — e.g. when the backend
 * returns 404 because the resource doesn't exist or belongs to a different
 * project. Detail pages with a UUID attempt cross-project resolution.
 */
export default function ProtectedNotFound() {
  const pathname = usePathname();
  const router = useRouter();

  const parsedEntity = useMemo(
    () => parseEntityFromPathname(pathname),
    [pathname]
  );

  const { entityName, listHref, breadcrumbs } = useMemo(() => {
    const segments = pathname.split('/').filter(Boolean);
    const rawEntity = segments[0] ?? '';
    const name = rawEntity ? formatEntityName(rawEntity) : 'Page';
    const href = rawEntity ? `/${rawEntity}` : '/';

    const crumbs: { label: string; href?: string }[] = [
      { label: name, href },
      { label: 'Not Found' },
    ];

    if (parsedEntity && segments.length >= 2) {
      crumbs.splice(1, 0, {
        label: parsedEntity.entityId,
        href: pathname,
      });
    }

    return {
      entityName: name,
      listHref: parsedEntity?.listUrl ?? href,
      breadcrumbs: crumbs,
    };
  }, [pathname, parsedEntity]);

  if (parsedEntity) {
    return (
      <DetailNotFoundState
        entityLabel={parsedEntity.entityLabel}
        entityId={parsedEntity.entityId}
        entityTableName={parsedEntity.entityType}
        listUrl={parsedEntity.listUrl}
        breadcrumbs={breadcrumbs}
        onBack={() => window.history.back()}
      />
    );
  }

  return (
    <PageLayout title="" breadcrumbs={breadcrumbs}>
      <Box sx={{ mt: 2, mb: 2 }}>
        <EntityMessageState
          icon={FolderOffOutlinedIcon}
          title="Resource not found"
          description="The resource you're looking for doesn't exist, was deleted, or belongs to a different project. Switch to the correct project and try again."
          primaryAction={{
            label: `Browse ${pluralize(entityName)}`,
            onClick: () => router.push(listHref),
            startIcon: <SearchIcon />,
            variant: 'contained',
          }}
          secondaryAction={{
            label: 'Go Back',
            onClick: () => window.history.back(),
            startIcon: <ArrowBackIcon />,
          }}
        />
      </Box>
    </PageLayout>
  );
}
