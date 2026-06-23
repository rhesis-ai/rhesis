import type { SxProps, Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme-constants';

/** Shared video placeholder / player shell styles (Figma GH_Short_Demo). */
export const onboardingVideoShellSx: SxProps<Theme> = {
  width: '100%',
  aspectRatio: '16 / 9',
  borderRadius: BORDER_RADIUS.lg,
  bgcolor: 'common.black',
};

export const onboardingSidebarSx: SxProps<Theme> = {
  borderRadius: BORDER_RADIUS.lg,
};
