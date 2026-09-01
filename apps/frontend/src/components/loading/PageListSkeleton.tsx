'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import {
  BORDER_RADIUS,
  ELEVATION,
  FAB_GROUP_GAP,
} from '@/styles/theme-constants';

/**
 * Loading placeholder for the standard list page: `PageLayout` header (title,
 * description, FAB cluster) above a grid card holding `GridToolbar`, column
 * headers, rows and the pagination footer.
 *
 * Geometry is copied from the real components so the swap to content doesn't
 * shift anything: 56px FABs at `FAB_GROUP_GAP` (Fab.tsx), 30px toolbar inset
 * and 36/38px controls (GridToolbar, FilterButton, SearchPill), 30px column
 * inset (BaseDataGrid `theme.spacing(3.75)`), and the card's own border,
 * radius and elevation (`GRID_PAPER_SX`). Those tokens are re-declared rather
 * than imported from BaseDataGrid because importing it would pull
 * @mui/x-data-grid into the loading chunk, which defeats the point.
 */

const HEADER_ROW_HEIGHT = 56;
const DATA_ROW_HEIGHT = 52;
const FOOTER_HEIGHT = 56;

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
  const fabKeys = Array.from({ length: actionCount }, (_, i) => `fab-${i}`);

  return (
    <Box sx={{ width: '100%' }} role="status" aria-label="Loading page">
      {/* PageLayout header: title row (minHeight 56) then description, mb: 5 */}
      <Box sx={{ display: 'flex', flexDirection: 'column', mb: 5 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            minHeight: HEADER_ROW_HEIGHT,
          }}
        >
          <Skeleton variant="text" width={180} sx={{ fontSize: '2.125rem' }} />
          {actionCount > 0 && (
            <Box
              sx={{ display: 'flex', gap: FAB_GROUP_GAP, flexShrink: 0 }}
              aria-hidden
            >
              {fabKeys.map(key => (
                <Skeleton key={key} variant="circular" width={56} height={56} />
              ))}
            </Box>
          )}
        </Box>
        <Skeleton variant="text" width={420} sx={{ fontSize: '1rem' }} />
      </Box>

      {/* Grid card — mirrors GRID_PAPER_SX */}
      <Box
        sx={{
          width: '100%',
          borderRadius: BORDER_RADIUS.md,
          boxShadow: ELEVATION.xs,
          border: theme => `1px solid ${theme.palette.greyscale.border}`,
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
              gap: 1.5,
              px: '30px',
              py: '30px',
              minHeight: 52,
            }}
          >
            {/* FilterButton: 36px square, radius sm */}
            <Skeleton
              variant="rounded"
              width={36}
              height={36}
              sx={{ borderRadius: BORDER_RADIUS.sm, flexShrink: 0 }}
            />
            {/* SearchPill: 240x38, elongated pill */}
            <Skeleton
              variant="rounded"
              width={240}
              height={38}
              sx={{ borderRadius: '30px', flexShrink: 0 }}
            />
            {/* Centered pill tabs */}
            <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
              <Skeleton
                variant="rounded"
                width={248}
                height={38}
                sx={{ borderRadius: BORDER_RADIUS.pill }}
              />
            </Box>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                flexShrink: 0,
              }}
            >
              {TOOLBAR_ACTIONS.map(width => (
                <Skeleton
                  key={width}
                  variant="text"
                  width={width}
                  sx={{ fontSize: '0.875rem' }}
                />
              ))}
            </Box>
          </Box>
        )}

        {/* Column headers: 56px, paper background, bottom divider */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            height: HEADER_ROW_HEIGHT,
            borderTop: theme => `1px solid ${theme.palette.greyscale.border}`,
            borderBottom: theme =>
              `1px solid ${theme.palette.greyscale.border}`,
          }}
        >
          {COLUMNS.map((col, idx) => (
            <Box
              key={col.key}
              sx={{
                width: col.width,
                flexShrink: 0,
                pl: idx === 0 ? '30px' : 0,
                pr: idx === COLUMNS.length - 1 ? '30px' : 2,
              }}
            >
              <Skeleton
                variant="text"
                width={col.header}
                sx={{ fontSize: '0.875rem' }}
              />
            </Box>
          ))}
        </Box>

        {/* Data rows: 52px, divider between */}
        {rowKeys.map((rowKey, rowIdx) => (
          <Box
            key={rowKey}
            sx={{
              display: 'flex',
              alignItems: 'center',
              height: DATA_ROW_HEIGHT,
              ...(rowIdx < rowKeys.length - 1 && {
                borderBottom: theme =>
                  `1px solid ${theme.palette.greyscale.border}`,
              }),
            }}
          >
            {COLUMNS.map((col, idx) => (
              <Box
                key={col.key}
                sx={{
                  width: col.width,
                  flexShrink: 0,
                  pl: idx === 0 ? '30px' : 0,
                  pr: idx === COLUMNS.length - 1 ? '30px' : 2,
                }}
              >
                {col.kind === 'chip' ? (
                  <Skeleton
                    variant="rounded"
                    width={col.cell}
                    height={24}
                    sx={{ borderRadius: BORDER_RADIUS.pill }}
                  />
                ) : (
                  <Skeleton
                    variant="text"
                    width={col.cell}
                    sx={{ fontSize: '0.875rem' }}
                  />
                )}
              </Box>
            ))}
          </Box>
        ))}

        {/* Pagination footer: right-aligned prev/next + range label */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 1.5,
            height: FOOTER_HEIGHT,
            px: '30px',
            borderTop: theme => `1px solid ${theme.palette.greyscale.border}`,
          }}
        >
          <Skeleton variant="circular" width={32} height={32} />
          <Skeleton variant="text" width={64} sx={{ fontSize: '0.875rem' }} />
          <Skeleton variant="circular" width={32} height={32} />
        </Box>
      </Box>
    </Box>
  );
}
