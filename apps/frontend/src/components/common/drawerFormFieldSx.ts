import type { SxProps, Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme';

/** 40px gap between top-level drawer sections (Figma "Drawer Create" Section spacing). */
export const drawerSectionSx: SxProps<Theme> = {
  display: 'flex',
  flexDirection: 'column',
  gap: '40px',
};

/** 30px gap between fields within a section. */
export const drawerFieldsSx: SxProps<Theme> = {
  display: 'flex',
  flexDirection: 'column',
  gap: '30px',
};

/**
 * Full-width outlined "Add …" button — border-2 primary, radius sm, 14px/700.
 * Matches the Figma "Button / Outlined / Medium" used inside drawer sections.
 */
export const drawerOutlineButtonSx: SxProps<Theme> = {
  borderWidth: 2,
  borderColor: 'primary.main',
  color: 'primary.main',
  fontWeight: 700,
  fontSize: 14,
  lineHeight: '22px',
  borderRadius: BORDER_RADIUS.sm,
  px: '16px',
  py: '8px',
  textTransform: 'none',
  '&:hover': { borderWidth: 2 },
};

/**
 * Figma outlined drawer field (node 1642:16790).
 * 56px control height: 16px vertical padding + 24px line-height content.
 */
export const drawerOutlinedFieldSx: SxProps<Theme> = {
  '& .MuiOutlinedInput-root': {
    borderRadius: BORDER_RADIUS.xs,
    minHeight: 56,
  },
  '& .MuiOutlinedInput-notchedOutline': {
    borderColor: theme => theme.palette.greyscale.border,
  },
  '& .MuiInputLabel-root.MuiInputLabel-shrink': {
    fontSize: 12,
    lineHeight: '18px',
    color: theme => theme.palette.greyscale.subtitle,
  },
  '& .MuiOutlinedInput-input': {
    padding: '16px 12px 16px 16px !important',
    minHeight: '24px',
    fontSize: 16,
    lineHeight: '24px',
    boxSizing: 'border-box',
  },
  '& .MuiSelect-select': {
    padding: '16px 32px 16px 16px !important',
    minHeight: '24px !important',
    fontSize: 16,
    lineHeight: '24px',
    display: 'flex',
    alignItems: 'center',
    boxSizing: 'border-box',
  },
};

export const drawerDisabledFieldSx: SxProps<Theme> = {
  ...drawerOutlinedFieldSx,
  '& .MuiOutlinedInput-root.Mui-disabled': {
    minHeight: 56,
  },
  '& .MuiOutlinedInput-input.Mui-disabled': {
    padding: '16px 12px 16px 16px !important',
    minHeight: '24px',
    WebkitTextFillColor: theme => theme.palette.greyscale.border,
    color: theme => theme.palette.greyscale.border,
    opacity: 1,
  },
};

export const drawerTagFieldSx: SxProps<Theme> = {
  ...drawerOutlinedFieldSx,
  '& .MuiOutlinedInput-root': {
    borderRadius: BORDER_RADIUS.xs,
    alignItems: 'center',
    gap: '10px',
    py: '16px',
    pl: '16px',
    pr: '12px',
  },
  '& .MuiOutlinedInput-input': {
    padding: 0,
    minHeight: '24px',
    fontSize: 16,
    lineHeight: '24px',
  },
  '& .MuiChip-root': {
    fontWeight: 400,
  },
};
