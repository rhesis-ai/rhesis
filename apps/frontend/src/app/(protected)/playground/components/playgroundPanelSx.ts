import type { SxProps, Theme } from '@mui/material/styles';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';

/** Bordered panel style aligned with list-page content areas (8px corners). */
export const playgroundPanelSx: SxProps<Theme> = {
  borderRadius: BORDER_RADIUS.sm,
  border: theme => `1px solid ${theme.palette.greyscale.border}`,
  boxShadow: ELEVATION.xs,
  overflow: 'hidden',
};
