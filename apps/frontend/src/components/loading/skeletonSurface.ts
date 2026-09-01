import type { Theme } from '@mui/material/styles';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';

/**
 * The 1px divider the grid card, section cards and dashboard panels all draw.
 * Matches BaseDataGrid's cell borders and EntityCard's outline.
 */
export const skeletonBorder = (theme: Theme) =>
  `1px solid ${theme.palette.greyscale.border}`;

/**
 * The elevated card surface every skeleton container sits on: the grid card,
 * an EntityCard, a SectionCard, a dashboard panel.
 *
 * Mirrors BaseDataGrid's `GRID_PAPER_SX`, which is re-declared here rather than
 * imported because importing BaseDataGrid would pull @mui/x-data-grid into the
 * loading chunk and defeat the point of a lightweight fallback.
 */
export const skeletonSurfaceSx = {
  borderRadius: BORDER_RADIUS.md,
  boxShadow: ELEVATION.xs,
  border: skeletonBorder,
  bgcolor: 'background.paper',
} as const;
