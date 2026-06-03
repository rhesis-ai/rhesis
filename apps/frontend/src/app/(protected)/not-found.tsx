'use client';

import { useMemo } from 'react';
import { alpha, Box, Button, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import SearchIcon from '@mui/icons-material/SearchOutlined';
import FolderOffOutlinedIcon from '@mui/icons-material/FolderOffOutlined';
import { PageLayout } from '@/components/layout/PageLayout';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

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
 * project.
 */
export default function ProtectedNotFound() {
  const pathname = usePathname();

  const { entityName, listHref, breadcrumbs } = useMemo(() => {
    const segments = pathname.split('/').filter(Boolean);
    const rawEntity = segments[0] ?? '';
    const name = rawEntity ? formatEntityName(rawEntity) : 'Page';
    const href = rawEntity ? `/${rawEntity}` : '/';

    return {
      entityName: name,
      listHref: href,
      breadcrumbs: [
        { label: name, href },
        { label: 'Not Found' },
      ],
    };
  }, [pathname]);

  return (
    <PageLayout title="" breadcrumbs={breadcrumbs}>
      <Box
        display="flex"
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
        minHeight="60vh"
        textAlign="center"
        px={3}
      >
        {/* Large backdrop number */}
        <Box position="relative" mb={2}>
          <Typography
            component="span"
            sx={{
              fontSize: { xs: '6rem', sm: '9rem' },
              fontWeight: 800,
              lineHeight: 1,
              color: theme => alpha(theme.palette.text.primary, 0.07),
              userSelect: 'none',
              letterSpacing: '-0.04em',
            }}
            aria-hidden
          >
            404
          </Typography>

          {/* Overlay icon */}
          <Box
            sx={{ position: 'absolute', inset: 0 }}
            display="flex"
            alignItems="center"
            justifyContent="center"
          >
            <FolderOffOutlinedIcon
              sx={{ fontSize: { xs: '2.5rem', sm: '3.5rem' }, color: 'text.secondary' }}
            />
          </Box>
        </Box>

        <Typography variant="h5" fontWeight={600} gutterBottom>
          Resource not found
        </Typography>

        <Typography
          variant="body1"
          color="text.secondary"
          sx={{ maxWidth: 440, mb: 4 }}
        >
          The resource you&apos;re looking for doesn&apos;t exist, was
          deleted, or belongs to a different project. Switch to the correct
          project and try again.
        </Typography>

        <Box display="flex" gap={1.5} flexWrap="wrap" justifyContent="center">
          <Button
            variant="outlined"
            startIcon={<ArrowBackIcon />}
            onClick={() => window.history.back()}
          >
            Go Back
          </Button>
          <Button
            component={Link}
            href={listHref}
            variant="outlined"
            startIcon={<SearchIcon />}
          >
            Browse {pluralize(entityName)}
          </Button>
        </Box>
      </Box>
    </PageLayout>
  );
}
