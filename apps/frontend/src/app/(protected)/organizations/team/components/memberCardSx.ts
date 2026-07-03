import type { SxProps, Theme } from '@mui/material/styles';
import { alpha } from '@mui/material';
import { BORDER_RADIUS } from '@/styles/theme';

/** Avatar for a project row — small square with project icon. */
export const projectAvatarSx: SxProps<Theme> = {
  width: theme => theme.spacing(4),
  height: theme => theme.spacing(4),
  bgcolor: 'primary.main',
  flexShrink: 0,
  fontSize: theme => theme.typography.body2.fontSize,
  fontWeight: theme => theme.typography.fontWeightBold,
  '& svg': { fontSize: theme => theme.spacing(2) },
};

/** Single-line overflow truncation. */
export const truncateSx: SxProps<Theme> = {
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

/** Project name text — medium weight, title colour, truncated. */
export const projectNameSx: SxProps<Theme> = {
  ...truncateSx,
  fontWeight: theme => theme.typography.fontWeightMedium,
  color: theme => theme.palette.greyscale?.title,
};

/** Project description text — caption size, block, truncated. */
export const projectDescriptionSx: SxProps<Theme> = {
  ...truncateSx,
  display: 'block',
};

/** Read-only project row card (MemberAccessDrawer). */
export const projectCardItemSx: SxProps<Theme> = {
  borderRadius: BORDER_RADIUS.md,
  border: theme => `1px solid ${theme.palette.divider}`,
  px: 1.5,
  py: 1.25,
  gap: 1.5,
  display: 'flex',
  alignItems: 'center',
};

/**
 * Selectable project row card (TeamInviteForm).
 *
 * We intentionally do NOT pass `selected` to the ListItemButton so that MUI
 * never adds the Mui-selected class. The Drawer's global Mui-selected rules
 * force color:white and background:#primary on every child (including
 * Typography), which is unreadable on our near-transparent tint.
 *
 * Visual selection state is managed entirely through the `isSelected` JS
 * variable, bypassing all MUI global overrides.
 */
export function getSelectableProjectItemSx(
  isSelected: boolean
): SxProps<Theme> {
  return {
    borderRadius: BORDER_RADIUS.md,
    border: theme =>
      isSelected
        ? `2px solid ${theme.palette.primary.main}`
        : `1px solid ${theme.palette.divider}`,
    px: 1.5,
    py: 1.25,
    gap: 1.5,
    ...(isSelected && {
      backgroundColor: theme => alpha(theme.palette.primary.main, 0.06),
      // Keep the same subtle tint on hover so text/role-dropdown stay readable.
      '&:hover': {
        backgroundColor: theme =>
          `${alpha(theme.palette.primary.main, 0.06)} !important`,
      },
    }),
  };
}

/**
 * Project name text with selection-aware font weight.
 * Selected names are medium weight; unselected are regular.
 */
export function getSelectableProjectNameSx(
  isSelected: boolean
): SxProps<Theme> {
  return {
    ...truncateSx,
    fontWeight: theme =>
      isSelected
        ? theme.typography.fontWeightMedium
        : theme.typography.fontWeightRegular,
    color: theme => theme.palette.greyscale?.title,
  };
}

/** Large member avatar in the drawer header (MemberAccessDrawer). */
export const memberAvatarSx: SxProps<Theme> = {
  width: theme => theme.spacing(6),
  height: theme => theme.spacing(6),
  bgcolor: 'primary.main',
  flexShrink: 0,
};

/** Flex column aligning the org-role chip to the end of the header row. */
export const orgRoleContainerSx: SxProps<Theme> = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'flex-end',
  gap: 0.5,
  flexShrink: 0,
};
