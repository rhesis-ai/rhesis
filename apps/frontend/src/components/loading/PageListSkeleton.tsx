'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import type { Theme } from '@mui/material/styles';
import {
  BORDER_RADIUS,
  ELEVATION,
  GRID_CARD_INSET,
  GRID_TOOLBAR_MIN_HEIGHT,
} from '@/styles/theme-constants';
import { delayedRevealSx } from './DelayedReveal';
import SkeletonPageHeader from './SkeletonPageHeader';
import { skeletonTextSx } from './skeletonText';

/**
 * Loading placeholder for the standard list page: `PageLayout` header (title,
 * description, FAB cluster) above a grid card holding `GridToolbar`, column
 * headers, rows and the pagination footer.
 *
 * Shared geometry comes from `theme-constants` so this cannot drift from the
 * components it stands in for. The card's border, radius and elevation mirror
 * BaseDataGrid's `GRID_PAPER_SX`, which is re-declared here rather than
 * imported because importing BaseDataGrid would pull @mui/x-data-grid into the
 * loading chunk and defeat the point of a lightweight fallback.
 */

/** Placeholder widths for the header text. Layout geometry lives in
 *  SkeletonPageHeader, which mirrors PageLayout. */
const HEADER = {
  titleWidth: 180,
  descriptionWidth: 420,
} as const;

/** Toolbar controls, mirroring `GridToolbar`, `FilterButton` and `SearchPill`. */
const TOOLBAR = {
  /** Gap between controls, in MUI spacing units. */
  gap: 1.5,
  filterButtonSize: 36,
  searchWidth: 240,
  controlHeight: 38,
  pillTabsWidth: 248,
} as const;

/** Grid rows and footer, mirroring BaseDataGrid's styled DataGrid. */
const GRID = {
  headerHeight: 56,
  rowHeight: 52,
  footerHeight: 56,
  /** Height of a `GridBadge`/`Chip` inside a cell. */
  chipHeight: 24,
  paginationButtonSize: 32,
  paginationLabelWidth: 64,
  /** Trailing padding on non-edge cells, in MUI spacing units. */
  cellGap: 2,
} as const;

/** Column widths approximating a typical entity grid: wide first column, then
 *  chip columns, then metadata. `chip` cells render pill shapes because those
 *  columns hold `GridBadge`/`Chip` renderers rather than plain text. */
const COLUMNS = [
  { key: 'primary', width: '17%', header: 64, cell: '86%', kind: 'text' },
  { key: 'chip-a', width: '11%', header: 84, cell: 72, kind: 'chip' },
  { key: 'chip-b', width: '13%', header: 52, cell: 104, kind: 'chip' },
  { key: 'chip-c', width: '12%', header: 68, cell: 82, kind: 'chip' },
  { key: 'type', width: '10%', header: 72, cell: 70, kind: 'text' },
  { key: 'created', width: '13%', header: 60, cell: 116, kind: 'text' },
  { key: 'meta-a', width: '9%', header: 76, cell: 24, kind: 'text' },
  { key: 'meta-b', width: '9%', header: 48, cell: 24, kind: 'text' },
  { key: 'actions', width: '6%', header: 56, cell: 24, kind: 'text' },
] as const;

/** Text links in the toolbar's right slot (Select / Columns / Density / Export). */
const TOOLBAR_ACTIONS = [76, 62, 56, 50];

/** Row and cell separator, matching BaseDataGrid's cell borders. */
const divider = (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`;

export interface PageListSkeletonProps {
  /** FAB placeholders in the header, matching the page's action cluster. */
  actionCount?: number;
  /** Placeholder data rows. */
  rows?: number;
  /** Render the search + filter + tabs toolbar row. */
  showToolbar?: boolean;
}

export default function PageListSkeleton({
  actionCount = 2,
  rows = 6,
  showToolbar = true,
}: PageListSkeletonProps = {}) {
  const rowKeys = Array.from({ length: rows }, (_, i) => `row-${i}`);

  /** Edge cells carry the card inset; the rest carry a trailing gap. */
  const cellInsetSx = (idx: number) => ({
    pl: idx === 0 ? GRID_CARD_INSET : 0,
    pr: idx === COLUMNS.length - 1 ? GRID_CARD_INSET : GRID.cellGap,
  });

  return (
    <Box
      sx={{ width: '100%', ...delayedRevealSx }}
      role="status"
      aria-label="Loading page"
    >
      <SkeletonPageHeader
        actionCount={actionCount}
        titleWidth={HEADER.titleWidth}
        descriptionWidth={HEADER.descriptionWidth}
      />

      {/* Grid card — mirrors GRID_PAPER_SX */}
      <Box
        sx={{
          width: '100%',
          borderRadius: BORDER_RADIUS.md,
          boxShadow: ELEVATION.xs,
          border: divider,
          overflow: 'hidden',
          bgcolor: 'background.paper',
        }}
        aria-hidden
      >
        {showToolbar && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: TOOLBAR.gap,
              px: GRID_CARD_INSET,
              py: GRID_CARD_INSET,
              minHeight: GRID_TOOLBAR_MIN_HEIGHT,
            }}
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
            {/* Pill tabs sit centred, as ToolbarPillTabs does */}
            <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
              <Skeleton
                variant="rounded"
                width={TOOLBAR.pillTabsWidth}
                height={TOOLBAR.controlHeight}
                sx={{ borderRadius: BORDER_RADIUS.pill }}
              />
            </Box>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: TOOLBAR.gap,
                flexShrink: 0,
              }}
            >
              {TOOLBAR_ACTIONS.map(width => (
                <Skeleton
                  key={width}
                  variant="text"
                  width={width}
                  sx={skeletonTextSx('bodyMReg')}
                />
              ))}
            </Box>
          </Box>
        )}

        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            height: GRID.headerHeight,
            borderTop: divider,
            borderBottom: divider,
          }}
        >
          {COLUMNS.map((col, idx) => (
            <Box
              key={col.key}
              sx={{ width: col.width, flexShrink: 0, ...cellInsetSx(idx) }}
            >
              <Skeleton
                variant="text"
                width={col.header}
                sx={skeletonTextSx('bodyMReg')}
              />
            </Box>
          ))}
        </Box>

        {rowKeys.map((rowKey, rowIdx) => (
          <Box
            key={rowKey}
            sx={{
              display: 'flex',
              alignItems: 'center',
              height: GRID.rowHeight,
              ...(rowIdx < rowKeys.length - 1 && { borderBottom: divider }),
            }}
          >
            {COLUMNS.map((col, idx) => (
              <Box
                key={col.key}
                sx={{ width: col.width, flexShrink: 0, ...cellInsetSx(idx) }}
              >
                {col.kind === 'chip' ? (
                  <Skeleton
                    variant="rounded"
                    width={col.cell}
                    height={GRID.chipHeight}
                    sx={{ borderRadius: BORDER_RADIUS.pill }}
                  />
                ) : (
                  <Skeleton
                    variant="text"
                    width={col.cell}
                    sx={skeletonTextSx('bodyMReg')}
                  />
                )}
              </Box>
            ))}
          </Box>
        ))}

        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: TOOLBAR.gap,
            height: GRID.footerHeight,
            px: GRID_CARD_INSET,
            borderTop: divider,
          }}
        >
          <Skeleton
            variant="circular"
            width={GRID.paginationButtonSize}
            height={GRID.paginationButtonSize}
          />
          <Skeleton
            variant="text"
            width={GRID.paginationLabelWidth}
            sx={skeletonTextSx('bodyMReg')}
          />
          <Skeleton
            variant="circular"
            width={GRID.paginationButtonSize}
            height={GRID.paginationButtonSize}
          />
        </Box>
      </Box>
    </Box>
  );
}
