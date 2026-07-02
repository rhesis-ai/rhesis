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
 * The MUI Drawer injects a high-specificity global rule
 * (.MuiDrawer-root .MuiListItemButton-root.Mui-selected) that overrides
 * sx bgcolor. The !important on backgroundColor ensures our subtle tint
 * wins so text and the inline role dropdown remain readable.
 */
export function getSelectableProjectItemSx(isSelected: boolean): SxProps<Theme> {
  return {
    borderRadius: BORDER_RADIUS.md,
    border: theme =>
      isSelected
        ? `2px solid ${theme.palette.primary.main}`
        : `1px solid ${theme.palette.divider}`,
    px: 1.5,
    py: 1.25,
    gap: 1.5,
    '&.Mui-selected, &.Mui-selected:hover': {
      backgroundColor: theme =>
        `${alpha(theme.palette.primary.main, 0.06)} !important`,
    },
  };
}

/**
 * Project name text with selection-aware font weight.
 * Selected names are medium weight; unselected are regular.
 */
export function getSelectableProjectNameSx(isSelected: boolean): SxProps<Theme> {
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
