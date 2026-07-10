import type { SxProps, Theme } from '@mui/material/styles';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';

/**
 * Figma-aligned tokens for compact card empty states (node 1435:49277) and
 * related status/message variants. Shared by EntityEmptyState, SectionEmptyState,
 * and EntityMessageState.
 */
export const EMPTY_STATE = {
  iconSize: {
    compact: 32,
    standalone: 64,
  },
  gap: {
    sm: '10px',
    md: '20px',
    lg: '30px',
    xl: '50px',
  },
  descriptionMaxWidth: 480,
  enrichedMaxWidth: 734,
  horizontalPadding: { xs: 2, md: '200px' },
  cardShell: {
    px: '30px',
    py: '40px',
  },
  spinnerSize: {
    icon: 32,
    button: 16,
  },
} as const;

export const emptyStateCompactTitleSx: SxProps<Theme> = {
  fontWeight: 600,
  fontSize: 20,
  lineHeight: '24px',
  color: 'primary.main',
};

export const emptyStateStandaloneTitleSx: SxProps<Theme> = {
  fontWeight: 700,
  color: 'text.primary',
};

export function emptyStateIconSx(
  size: number,
  options?: { standalone?: boolean }
): SxProps<Theme> {
  return {
    fontSize: size,
    color: 'primary.main',
    opacity: options?.standalone ? 0.6 : 1,
  };
}

export function emptyStateDescriptionSx(options?: {
  compact?: boolean;
  enriched?: boolean;
}): SxProps<Theme> {
  return {
    color: 'text.secondary',
    maxWidth: options?.enriched
      ? EMPTY_STATE.enrichedMaxWidth
      : EMPTY_STATE.descriptionMaxWidth,
    ...(options?.compact ? { lineHeight: '22px' } : {}),
  };
}

export const emptyStateOutlinedActionSx: SxProps<Theme> = {
  fontWeight: 700,
  fontSize: 18,
  lineHeight: '25px',
  borderRadius: BORDER_RADIUS.md,
  textTransform: 'none',
  px: '20px',
  py: '12px',
  borderWidth: 2,
  '&:hover': { borderWidth: 2 },
};

export const emptyStateContainedActionSx: SxProps<Theme> = {
  fontWeight: 700,
  fontSize: 18,
  lineHeight: '25px',
  borderRadius: BORDER_RADIUS.md,
  textTransform: 'none',
  px: '20px',
  py: '12px',
};

export const emptyStateStandaloneContainedActionSx: SxProps<Theme> = {
  mt: 1,
  fontWeight: 700,
  fontSize: 18,
  lineHeight: '25px',
  borderRadius: BORDER_RADIUS.pill,
  textTransform: 'none',
  px: '20px',
  py: '12px',
  boxShadow: ELEVATION.xs,
};

export const emptyStateEnrichedActionBaseSx: SxProps<Theme> = {
  fontWeight: 700,
  fontSize: 14,
  lineHeight: '22px',
  borderRadius: BORDER_RADIUS.sm,
  textTransform: 'none',
  px: '16px',
  py: '8px',
};

export const emptyStateEnrichedOutlinedBorderSx: SxProps<Theme> = {
  borderWidth: 2,
  '&:hover': { borderWidth: 2 },
};

export function emptyStateEnrichedActionSx(
  variant: 'outlined' | 'contained'
): SxProps<Theme> {
  return variant === 'outlined'
    ? {
        ...emptyStateEnrichedActionBaseSx,
        ...emptyStateEnrichedOutlinedBorderSx,
      }
    : emptyStateEnrichedActionBaseSx;
}

export const emptyStateActionsRowSx: SxProps<Theme> = {
  display: 'flex',
  gap: EMPTY_STATE.gap.sm,
  alignItems: 'center',
  justifyContent: 'center',
  flexWrap: 'wrap',
};

export function emptyStateHeaderStackSx(compact: boolean): SxProps<Theme> {
  return {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: compact ? EMPTY_STATE.gap.sm : 0,
  };
}

export function emptyStateInnerStackSx(
  gap: keyof typeof EMPTY_STATE.gap = 'md'
): SxProps<Theme> {
  return {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: EMPTY_STATE.gap[gap],
  };
}

export const emptyStateCenteredColumnSx: SxProps<Theme> = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  textAlign: 'center',
};

export function emptyStateCompactContentSx(options?: {
  enriched?: boolean;
}): SxProps<Theme> {
  return {
    ...emptyStateCenteredColumnSx,
    py: 0,
    px: EMPTY_STATE.horizontalPadding,
    gap: options?.enriched ? EMPTY_STATE.gap.xl : EMPTY_STATE.gap.md,
  };
}

export const emptyStateStandaloneContentSx: SxProps<Theme> = {
  ...emptyStateCenteredColumnSx,
  py: 10,
  px: 4,
  gap: 2,
};

export const emptyStateCardShellSx: SxProps<Theme> = {
  border: theme => `1px solid ${theme.palette.greyscale.border}`,
  borderRadius: BORDER_RADIUS.md,
  boxShadow: ELEVATION.xs,
  px: EMPTY_STATE.cardShell.px,
  py: EMPTY_STATE.cardShell.py,
};

export function emptyStateSectionInsetSx(inset: boolean): SxProps<Theme> {
  return {
    ...(inset
      ? {
          border: theme => `1px solid ${theme.palette.greyscale.border}`,
          borderRadius: BORDER_RADIUS.md,
        }
      : {}),
    px: { xs: 2, sm: 4, md: EMPTY_STATE.horizontalPadding.md },
    py: inset ? EMPTY_STATE.cardShell.py : 0,
    ...emptyStateCenteredColumnSx,
    gap: EMPTY_STATE.gap.md,
  };
}
