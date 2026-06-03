import type { SxProps, Theme } from '@mui/material/styles';
import { tagSurfaceSx } from '@/components/common/Tag';

/**
 * MUI Chip overrides for BaseTag — matches {@link tagSurfaceSx} + delete icon.
 */
export const editableTagChipSx: SxProps<Theme> = {
  ...tagSurfaceSx,
  '& .MuiChip-label': {
    px: 1.25,
    py: 0,
    fontSize: (theme: Theme) => theme.typography.body2.fontSize,
    lineHeight: '22px',
    fontWeight: (theme: Theme) => theme.typography.button.fontWeight,
  },
  '& .MuiChip-deleteIcon': {
    fontSize: (theme: Theme) => theme.typography.body1.fontSize,
    width: 16,
    height: 16,
    margin: theme => theme.spacing(0, 0.5, 0, 0.25),
    color: (theme: Theme) => theme.palette.greyscale.subtitle,
    '&:hover': {
      color: (theme: Theme) => theme.palette.greyscale.body,
    },
  },
};
