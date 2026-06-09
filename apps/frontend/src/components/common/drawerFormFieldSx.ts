import type { SxProps, Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme';

/** Default drawer shell width — 518px content + 30px padding each side (Figma 1641:16598). */
export const DRAWER_WIDTH = 578;

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
    padding: theme =>
      `${theme.spacing(2)} ${theme.spacing(1.5)} ${theme.spacing(2)} ${theme.spacing(2)} !important`,
    minHeight: '24px',
    fontSize: 16,
    lineHeight: '24px',
    boxSizing: 'border-box',
  },
  '& .MuiSelect-select': {
    padding: theme =>
      `${theme.spacing(2)} ${theme.spacing(4)} ${theme.spacing(2)} ${theme.spacing(2)} !important`,
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
    padding: theme =>
      `${theme.spacing(2)} ${theme.spacing(1.5)} ${theme.spacing(2)} ${theme.spacing(2)} !important`,
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

/** Footer cancel button — Figma Drawer Create toolbar (1641:16615). */
export const drawerFooterCancelButtonSx: SxProps<Theme> = {
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

/** Footer delete button — outlined error, matches drawer toolbar sizing. */
export const drawerFooterDeleteButtonSx: SxProps<Theme> = {
  ...drawerFooterCancelButtonSx,
  borderColor: 'error.main',
  color: 'error.main',
  '&:hover': {
    borderWidth: 2,
    borderColor: 'error.dark',
    bgcolor: theme => theme.palette.action.hover,
  },
};

/** Footer primary action button — Figma Drawer Create toolbar (1641:16616). */
export const drawerFooterSaveButtonSx: SxProps<Theme> = {
  borderRadius: BORDER_RADIUS.sm,
  px: '16px',
  py: '8px',
  fontWeight: 700,
  fontSize: 14,
  lineHeight: '22px',
  textTransform: 'none',
  '&.Mui-disabled': {
    bgcolor: theme => theme.palette.greyscale.border,
    color: '#fff',
  },
};
