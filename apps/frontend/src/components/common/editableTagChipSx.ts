import type { SxProps, Theme } from '@mui/material/styles';
import { GREYSCALE } from '@/styles/theme';
import { tagSurfaceSx } from '@/components/common/Tag';

/**
 * MUI Chip overrides for BaseTag — matches {@link tagSurfaceSx} + delete icon.
 */
export const editableTagChipSx: SxProps<Theme> = {
  ...tagSurfaceSx,
  '& .MuiChip-label': {
    px: '10px',
    py: 0,
    fontSize: 14,
    lineHeight: '22px',
    fontWeight: 600,
  },
  '& .MuiChip-deleteIcon': {
    fontSize: 16,
    width: 16,
    height: 16,
    margin: '0 4px 0 2px',
    color: theme =>
      theme.palette.mode === 'light'
        ? GREYSCALE.light.subtitle
        : GREYSCALE.dark.subtitle,
    '&:hover': {
      color: theme =>
        theme.palette.mode === 'light'
          ? GREYSCALE.light.body
          : GREYSCALE.dark.body,
    },
  },
};
