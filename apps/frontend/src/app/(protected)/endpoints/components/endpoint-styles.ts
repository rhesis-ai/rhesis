import { alpha, type Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme-constants';

// Chip for displaying template variable labels (read-only)
export const variableChipSx = {
  fontFamily: 'monospace',
  fontSize: 11,
  height: 22,
  bgcolor: (t: Theme) => t.palette.greyscale.surface1,
  color: (t: Theme) => t.palette.greyscale?.body ?? t.palette.text.primary,
  border: 'none',
  '& .MuiChip-label': { px: 1 },
};

// Chip for inserting template variables (clickable)
export const insertableVariableChipSx = {
  ...variableChipSx,
  cursor: 'pointer',
  '&:hover': {
    bgcolor: (t: Theme) =>
      t.palette.mode === 'light'
        ? alpha(t.palette.greyscale.body, 0.08)
        : alpha(t.palette.greyscale.body, 0.12),
  },
};

/** Read-only / preview content block (Figma fieldSurface) */
export const fieldSurfaceBoxSx = {
  bgcolor: (t: Theme) => t.palette.greyscale.fieldSurface,
  borderRadius: BORDER_RADIUS.xs,
  pl: '16px',
  pr: '12px',
  py: '16px',
};

export const testPreviewSx = {
  ...fieldSurfaceBoxSx,
  fontFamily: 'monospace',
  fontSize: 12,
  color: (t: Theme) => t.palette.greyscale.body,
  whiteSpace: 'pre-wrap' as const,
  wordBreak: 'break-word' as const,
  overflowY: 'auto' as const,
  minHeight: 120,
  maxHeight: 280,
  m: 0,
};

/** Editable Monaco / JSON editor container */
export const editorContainerSx = {
  border: 1,
  borderColor: (t: Theme) => t.palette.greyscale.border,
  borderRadius: BORDER_RADIUS.xs,
  bgcolor: (t: Theme) => t.palette.greyscale.fieldSurface,
  overflow: 'hidden' as const,
};
