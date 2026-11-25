'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { PageLayout } from '@/components/layout/PageLayout';
import { useListAuthGate } from '@/hooks/useListAuthGate';
import AnnotationsGrid from './AnnotationsGrid';
import { annotationsList } from './list';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import type { Annotation } from '@/utils/api-client/interfaces/annotation';
import { PAGE_HEADERS } from '@/constants/page-headers';

interface AnnotationsPageClientProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: Annotation[];
  initialTotalCount?: number;
}

export default function AnnotationsPageClient({
  initialData,
  initialTotalCount = 0,
}: AnnotationsPageClientProps) {
  const gate = useListAuthGate(annotationsList);

  useDocumentTitle('Annotations');

  if (!gate.ready) return gate.node;

  return (
    <PageLayout
      title={PAGE_HEADERS.annotations.title}
      description={PAGE_HEADERS.annotations.description}
      breadcrumbs={[]}
    >
      <Box sx={{ mt: 2, mb: 2 }}>
        <Paper
          sx={{
            width: '100%',
            borderRadius: BORDER_RADIUS.md,
            boxShadow: ELEVATION.xs,
            border: theme => `1px solid ${theme.palette.greyscale.border}`,
            overflow: 'hidden',
          }}
        >
          <AnnotationsGrid
            initialData={initialData}
            initialTotalCount={initialTotalCount}
          />
        </Paper>
      </Box>
    </PageLayout>
  );
}
