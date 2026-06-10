import { alpha, type Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme-constants';

// Chip for displaying template variable labels (read-only)
export const variableChipSx = {
  fontFamily: 'monospace',
  fontSize: 11,
  height: 22,
  bgcolor: (t: Theme) =>
    t.palette.mode === 'light'
      ? alpha(t.palette.primary.main, 0.08)
      : alpha(t.palette.primary.main, 0.18),
  color: 'primary.main',
  border: 1,
  borderColor: 'transparent',
  '& .MuiChip-label': { px: 1 },
};

// Chip for inserting template variables (clickable)
export const insertableVariableChipSx = {
  ...variableChipSx,
  cursor: 'pointer',
  '&:hover': {
    bgcolor: (t: Theme) =>
      t.palette.mode === 'light'
        ? alpha(t.palette.primary.main, 0.16)
        : alpha(t.palette.primary.main, 0.28),
    borderColor: 'primary.main',
  },
};

// Shared layout for the side-by-side request/response panels in test tabs
export const testPanelSx = {
  flex: 1,
  border: 1,
  borderColor: 'divider',
  borderRadius: BORDER_RADIUS.sm,
  overflow: 'hidden',
  display: 'flex',
  flexDirection: 'column' as const,
  minWidth: 0,
};

export const testPanelHeaderSx = {
  px: 2,
  py: 1,
  borderBottom: 1,
  borderColor: 'divider',
  display: 'flex',
  alignItems: 'center',
  gap: 1,
};

export const testPreviewSx = {
  p: 2,
  fontFamily: 'monospace',
  fontSize: 12,
  color: 'text.secondary',
  whiteSpace: 'pre-wrap' as const,
  wordBreak: 'break-word' as const,
  overflowY: 'auto' as const,
  bgcolor: 'background.default',
  minHeight: 180,
  maxHeight: 280,
  m: 0,
};
