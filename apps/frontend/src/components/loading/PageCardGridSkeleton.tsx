'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import type { Theme } from '@mui/material/styles';
import {
  BORDER_RADIUS,
  ELEVATION,
  GRID_CARD_INSET,
} from '@/styles/theme-constants';
import { delayedRevealSx } from './DelayedReveal';
import SkeletonPageHeader from './SkeletonPageHeader';
import { skeletonTextSx } from './skeletonText';

/**
 * Loading placeholder for card-directory pages: metrics, requirements, models,
 * tools and projects. These render a responsive grid of `EntityCard`s rather
 * than a DataGrid, so the table skeleton is the wrong shape for them.
 *
 * Geometry mirrors those pages: the borderless `directoryToolbarSx` toolbar,
 * the identical `xs: 1fr / sm: 1fr 1fr / md: repeat(3, 1fr)` grid they each
 * declare, and `EntityCard`'s own inset, radius, elevation and internal stack.
 */

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

/** Borderless toolbar above the cards, mirroring `directoryToolbarSx`. */
const TOOLBAR = {
  /** Gap between controls. */
  gap: '20px',
  /** Bottom margin, in MUI spacing units. */
  marginBottom: 3,
  filterButtonSize: 36,
  searchWidth: 240,
  controlHeight: 38,
  pillTabsWidth: 248,
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

/** Card border, matching EntityCard. */
const cardBorder = (theme: Theme) =>
  `1px solid ${theme.palette.greyscale.border}`;

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
    <Box
      sx={{ width: '100%', ...delayedRevealSx }}
      role="status"
      aria-label="Loading page"
    >
      <SkeletonPageHeader actionCount={actionCount} />

      {showToolbar && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: TOOLBAR.gap,
            mb: TOOLBAR.marginBottom,
          }}
          aria-hidden
        >
          <Skeleton
            variant="rounded"
            width={TOOLBAR.filterButtonSize}
            height={TOOLBAR.filterButtonSize}
            sx={{ borderRadius: BORDER_RADIUS.sm, flexShrink: 0 }}
          />
          <Skeleton
            variant="rounded"
            width={TOOLBAR.searchWidth}
            height={TOOLBAR.controlHeight}
            sx={{
              borderRadius: '30px', // Intentional: matches SearchPill's elongated pill
              flexShrink: 0,
            }}
          />
          <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
            <Skeleton
              variant="rounded"
              width={TOOLBAR.pillTabsWidth}
              height={TOOLBAR.controlHeight}
              sx={{ borderRadius: BORDER_RADIUS.pill }}
            />
          </Box>
        </Box>
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
              border: cardBorder,
              borderRadius: BORDER_RADIUS.md,
              boxShadow: ELEVATION.xs,
              bgcolor: 'background.paper',
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
    </Box>
  );
}
