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

/** EntityCard internals: title row, clamped description, footer meta. */
const CARD = {
  /** Vertical gap between the card's sections. */
  gap: '20px',
  /** Gap inside the title block. */
  titleGap: '10px',
  iconSize: 24,
  titleWidth: '62%',
  /** Description is clamped to 3 lines at 22px, so it reserves 66px. */
  descriptionLines: 3,
  descriptionLineHeight: 22,
  /** Avatar in the footer meta row. */
  avatarSize: 24,
  avatarLabelWidth: 96,
  /** Chip row under the divider. */
  chipHeight: 24,
  chipWidths: [64, 88, 52],
} as const;

export interface PageCardGridSkeletonProps {
  /** FAB placeholders in the header, matching the page's action cluster. */
  actionCount?: number;
  /** Card placeholders. Default fills two rows at desktop width. */
  cards?: number;
  /** Render the filter + search + tabs toolbar row. */
  showToolbar?: boolean;
}

export default function PageCardGridSkeleton({
  actionCount = 2,
  cards = 6,
  showToolbar = true,
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
            {/* Title row: icon plus name */}
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: CARD.titleGap,
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: CARD.titleGap,
                }}
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
            </Box>

            {/* Description, clamped to 3 lines in the real card */}
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

            {/* Footer meta: avatar plus name */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
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

            {/* Chip section */}
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {CARD.chipWidths.map(width => (
                <Skeleton
                  key={width}
                  variant="rounded"
                  width={width}
                  height={CARD.chipHeight}
                  sx={{ borderRadius: BORDER_RADIUS.pill }}
                />
              ))}
            </Box>
          </Box>
        ))}
      </Box>
    </DelayedReveal>
  );
}
