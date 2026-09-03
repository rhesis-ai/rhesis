'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import {
  BORDER_RADIUS,
  GRID_CARD_INSET,
  GRID_TOOLBAR_MIN_HEIGHT,
} from '@/styles/theme-constants';
import DelayedReveal from './DelayedReveal';
import SkeletonPageHeader from './SkeletonPageHeader';
import { skeletonBorder, skeletonSurfaceSx } from './skeletonSurface';
import { skeletonTextSx } from './skeletonText';
import SkeletonToolbar from './SkeletonToolbar';

/**
 * Loading placeholder for the standard list page: `PageLayout` header above a
 * grid card holding `GridToolbar`, column headers, rows and the pagination
 * footer.
 *
 * Shared geometry comes from `theme-constants` so this cannot drift from the
 * components it stands in for.
 */

/** Placeholder widths for the header text. Layout geometry lives in
 *  SkeletonPageHeader, which mirrors PageLayout. */
const HEADER = {
  titleWidth: 180,
  descriptionWidth: 420,
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
  /** Gap between the footer's controls, in MUI spacing units. */
  footerGap: 1.5,
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
    <DelayedReveal>
      <SkeletonPageHeader
        actionCount={actionCount}
        titleWidth={HEADER.titleWidth}
        descriptionWidth={HEADER.descriptionWidth}
      />

      <Box sx={{ width: '100%', ...skeletonSurfaceSx, overflow: 'hidden' }}>
        {showToolbar && (
          <SkeletonToolbar
            rightSlot="actions"
            sx={{
              px: GRID_CARD_INSET,
              py: GRID_CARD_INSET,
              minHeight: GRID_TOOLBAR_MIN_HEIGHT,
            }}
          />
        )}

        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            height: GRID.headerHeight,
            borderTop: skeletonBorder,
            borderBottom: skeletonBorder,
          }}
          aria-hidden
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
              ...(rowIdx < rowKeys.length - 1 && {
                borderBottom: skeletonBorder,
              }),
            }}
            aria-hidden
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
            gap: GRID.footerGap,
            height: GRID.footerHeight,
            px: GRID_CARD_INSET,
            borderTop: skeletonBorder,
          }}
          aria-hidden
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
    </DelayedReveal>
  );
}
