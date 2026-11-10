'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import { BORDER_RADIUS, GRID_CARD_INSET } from '@/styles/theme-constants';
import DelayedReveal from './DelayedReveal';
import SkeletonPageHeader from './SkeletonPageHeader';
import { skeletonSurfaceSx } from './skeletonSurface';
import { skeletonTextSx } from './skeletonText';
import SkeletonToolbar from './SkeletonToolbar';

/**
 * Loading placeholder for card-directory pages: metrics, requirements, models,
 * tools and projects. These render a responsive grid of `EntityCard`s rather
 * than a DataGrid, so the table skeleton is the wrong shape for them.
 *
 * Geometry mirrors those pages: the borderless `directoryToolbarSx` toolbar,
 * the identical `xs: 1fr / sm: 1fr 1fr / md: repeat(3, 1fr)` grid they each
 * declare, and `EntityCard`'s own inset, radius, elevation and internal stack.
 */

/** Borderless toolbar above the cards. Only the gap and margin differ from
 *  the grid-card toolbar; the controls live in SkeletonToolbar. */
const DIRECTORY_TOOLBAR = {
  /** `directoryToolbarSx` spaces its controls 20px apart, not by spacing units. */
  gap: '20px',
  /** Bottom margin, in MUI spacing units. */
  marginBottom: 3,
} as const;

/** Card directory grid, mirroring the container in MetricsDirectoryTab,
 *  RequirementsClient, ToolsPageClient, ModelsPageClient and
 *  ProjectsClientWrapper, which all declare it identically. */
const CARD_GRID = {
  columns: { xs: '1fr', sm: '1fr 1fr', md: 'repeat(3, 1fr)' },
  /** Gap between cards, in MUI spacing units. */
  gap: 3,
  /** Bottom margin below the grid, in MUI spacing units. */
  marginBottom: 4,
} as const;

/** EntityCard internals: context, title, facts, description, relations, footer. */
const CARD = {
  /** Vertical gap between the card's slots, in MUI spacing units. */
  gap: 1.25,
  titleGap: '10px',
  iconSize: 24,
  titleWidth: '62%',
  contextWidth: 88,
  /** Kind chip and one plain fact. */
  chipHeight: 22,
  chipWidth: 80,
  factWidth: 72,
  /** Description is clamped to 2 lines at 22px. */
  descriptionLines: 2,
  descriptionLineHeight: 22,
  relationWidths: [64, 52, 72],
  avatarSize: 20,
  avatarLabelWidth: 64,
} as const;

export interface PageCardGridSkeletonProps {
  /** FAB placeholders in the header, matching the page's action cluster. */
  actionCount?: number;
  /** Card placeholders. Default fills two rows at desktop width. */
  cards?: number;
  /** Render the filter + search + tabs toolbar row. */
  showToolbar?: boolean;
  /**
   * Render the centred pill tabs in the toolbar. Tools passes false because it
   * is the one card directory that gives GridToolbar no `middleContent`.
   */
  showTabs?: boolean;
}

export default function PageCardGridSkeleton({
  actionCount = 2,
  cards = 6,
  showToolbar = true,
  showTabs = true,
}: PageCardGridSkeletonProps = {}) {
  const cardKeys = Array.from({ length: cards }, (_, i) => `card-${i}`);
  const descriptionKeys = Array.from(
    { length: CARD.descriptionLines },
    (_, i) => `line-${i}`
  );

  return (
    <DelayedReveal>
      <SkeletonPageHeader actionCount={actionCount} />

      {showToolbar && (
        <SkeletonToolbar
          gap={DIRECTORY_TOOLBAR.gap}
          showTabs={showTabs}
          sx={{ mb: DIRECTORY_TOOLBAR.marginBottom }}
        />
      )}

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: CARD_GRID.columns,
          gap: CARD_GRID.gap,
          mb: CARD_GRID.marginBottom,
        }}
        aria-hidden
      >
        {cardKeys.map(cardKey => (
          <Box
            key={cardKey}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: CARD.gap,
              ...skeletonSurfaceSx,
              p: GRID_CARD_INSET,
            }}
          >
            {/* Context */}
            <Skeleton
              variant="text"
              width={CARD.contextWidth}
              sx={skeletonTextSx('bodyMReg')}
            />

            {/* Title row: icon plus name */}
            <Box
              sx={{ display: 'flex', alignItems: 'center', gap: CARD.titleGap }}
            >
              <Skeleton
                variant="circular"
                width={CARD.iconSize}
                height={CARD.iconSize}
              />
              <Skeleton
                variant="text"
                width={CARD.titleWidth}
                sx={skeletonTextSx('h6')}
              />
            </Box>

            {/* Facts: kind chip plus one plain fact */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
              <Skeleton
                variant="rounded"
                width={CARD.chipWidth}
                height={CARD.chipHeight}
                sx={{ borderRadius: BORDER_RADIUS.pill }}
              />
              <Skeleton
                variant="text"
                width={CARD.factWidth}
                sx={skeletonTextSx('bodyMReg')}
              />
            </Box>

            <Box>
              {descriptionKeys.map((lineKey, idx) => (
                <Skeleton
                  key={lineKey}
                  variant="text"
                  width={idx === CARD.descriptionLines - 1 ? '55%' : '100%'}
                  height={CARD.descriptionLineHeight}
                />
              ))}
            </Box>

            <Box sx={{ height: '1px', bgcolor: 'divider' }} />

            {/* Relations */}
            <Box sx={{ display: 'flex', gap: 2 }}>
              {CARD.relationWidths.map(width => (
                <Skeleton
                  key={width}
                  variant="text"
                  width={width}
                  sx={skeletonTextSx('bodyMReg')}
                />
              ))}
            </Box>

            {/* Footer: avatar plus name */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Skeleton
                variant="circular"
                width={CARD.avatarSize}
                height={CARD.avatarSize}
              />
              <Skeleton
                variant="text"
                width={CARD.avatarLabelWidth}
                sx={skeletonTextSx('bodyMReg')}
              />
            </Box>
          </Box>
        ))}
      </Box>
    </DelayedReveal>
  );
}
