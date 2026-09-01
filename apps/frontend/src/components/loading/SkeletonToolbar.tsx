'use client';

import Box from '@mui/material/Box';
import Skeleton from '@mui/material/Skeleton';
import type { SxProps, Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { skeletonTextSx } from './skeletonText';

/**
 * The filter / search / tabs row that sits above a page's content, standing in
 * for `GridToolbar`.
 *
 * Shared because three page shapes draw it: the bordered grid card, the
 * borderless card directory (`directoryToolbarSx`) and the insights filter bar.
 * They differ only in the gap between controls and what occupies the right
 * side, so those are props rather than three copies of the same row.
 */

/** Control geometry, mirroring `FilterButton`, `SearchPill` and `ToolbarPillTabs`. */
const CONTROL = {
  filterButtonSize: 36,
  searchWidth: 240,
  height: 38,
  pillTabsWidth: 248,
} as const;

/** Text links in the grid toolbar's right slot (Select / Columns / Density / Export). */
const ACTION_WIDTHS = [76, 62, 56, 50];

export interface SkeletonToolbarProps {
  /**
   * Gap between controls. The grid card uses MUI spacing units (`1.5`), the
   * card directory a literal `'20px'` from `directoryToolbarSx`.
   */
  gap?: number | string;
  /** Extra styles for the row, e.g. the card directory's inset and margin. */
  sx?: SxProps<Theme>;
  /**
   * Render the centred pill tabs. False for toolbars whose page passes no
   * `middleContent` to GridToolbar, which would otherwise show tabs that
   * vanish when content arrives.
   */
  showTabs?: boolean;
  /**
   * Right-hand slot. `actions` draws the grid toolbar's four text links
   * (Select / Columns / Density / Export); `none` leaves it bare, as the card
   * directories and the insights filter bar do.
   */
  rightSlot?: 'actions' | 'none';
}

export default function SkeletonToolbar({
  gap = 1.5,
  sx,
  showTabs = true,
  rightSlot = 'none',
}: SkeletonToolbarProps = {}) {
  return (
    <Box
      sx={[
        { display: 'flex', alignItems: 'center', gap },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
      aria-hidden
    >
      <Skeleton
        variant="rounded"
        width={CONTROL.filterButtonSize}
        height={CONTROL.filterButtonSize}
        sx={{ borderRadius: BORDER_RADIUS.sm, flexShrink: 0 }}
      />
      <Skeleton
        variant="rounded"
        width={CONTROL.searchWidth}
        height={CONTROL.height}
        sx={{
          borderRadius: '30px', // Intentional: matches SearchPill's elongated pill
          flexShrink: 0,
        }}
      />

      {showTabs ? (
        <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
          <Skeleton
            variant="rounded"
            width={CONTROL.pillTabsWidth}
            height={CONTROL.height}
            sx={{ borderRadius: BORDER_RADIUS.pill }}
          />
        </Box>
      ) : (
        // GridToolbar inserts this spacer whenever middleContent is absent.
        <Box sx={{ flex: 1 }} />
      )}

      {rightSlot === 'actions' && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap, flexShrink: 0 }}>
          {ACTION_WIDTHS.map(width => (
            <Skeleton
              key={width}
              variant="text"
              width={width}
              sx={skeletonTextSx('bodyMReg')}
            />
          ))}
        </Box>
      )}
    </Box>
  );
}
