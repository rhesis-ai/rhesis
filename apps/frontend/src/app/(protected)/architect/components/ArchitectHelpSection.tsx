'use client';

import React from 'react';
import { Box } from '@mui/material';
import { EntityEmptyStateEnrichmentSections } from '@/components/common/EntityEmptyStateEnrichmentParts';
import type { EntityEmptyStateEnrichment } from '@/constants/entity-empty-state-types';
import { useArchitectHelpArticles } from '@/hooks/useArchitectHelpArticles';
import { useProjectNeedsEndpoint } from '@/hooks/useProjectNeedsEndpoint';

/** Figma frame width for the help section (1858:49358) — wider than the input column. */
const MAX_WIDTH = 1126;

/**
 * Getting-started help articles for a project that has no endpoint yet. Renders
 * nothing once an endpoint exists, so it fades out on its own as the user
 * completes setup.
 */
export default function ArchitectHelpSection() {
  const { needsEndpoint } = useProjectNeedsEndpoint();
  const { data: articleUrls } = useArchitectHelpArticles();

  // Stay hidden until we know the project has no endpoint — otherwise users who
  // do have one see the cards flash on every visit.
  if (!needsEndpoint) return null;
  if (!articleUrls || articleUrls.length === 0) return null;

  const enrichment: EntityEmptyStateEnrichment = {
    helpArticles: {
      title: 'Top Help Articles',
      items: articleUrls.map(href => ({ href })),
    },
  };

  return (
    <Box sx={{ width: '100%', maxWidth: MAX_WIDTH }}>
      <EntityEmptyStateEnrichmentSections enrichment={enrichment} />
    </Box>
  );
}
