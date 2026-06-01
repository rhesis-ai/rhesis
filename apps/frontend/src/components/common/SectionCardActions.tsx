'use client';

import { Box, Button, CircularProgress } from '@mui/material';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import { BORDER_RADIUS } from '@/styles/theme-constants';

/** Figma Button 1413:8164 — outlined Edit on section cards */
export const sectionEditButtonSx = {
  fontWeight: 700,
  fontSize: 14,
  lineHeight: '22px',
  px: '16px',
  py: '8px',
  borderRadius: BORDER_RADIUS.sm,
  borderWidth: 2,
  borderColor: 'primary.main',
  color: 'primary.main',
  gap: '4px',
  '& .MuiButton-startIcon': {
    marginRight: '4px',
    '& > *:nth-of-type(1)': { fontSize: 20 },
  },
  '&:hover': {
    borderWidth: 2,
    borderColor: 'primary.main',
    bgcolor: 'action.hover',
  },
} as const;

export const sectionContainedButtonSx = {
  fontWeight: 700,
  fontSize: 14,
  lineHeight: '22px',
  px: '16px',
  py: '8px',
  borderRadius: BORDER_RADIUS.sm,
} as const;

export const sectionOutlinedCancelButtonSx = {
  ...sectionContainedButtonSx,
  borderWidth: 2,
  '&:hover': { borderWidth: 2 },
} as const;

interface SectionEditButtonProps {
  onClick: () => void;
  disabled?: boolean;
}

export function SectionEditButton({
  onClick,
  disabled,
}: SectionEditButtonProps) {
  return (
    <Button
      size="small"
      variant="outlined"
      startIcon={<EditOutlinedIcon sx={{ fontSize: 20 }} />}
      onClick={onClick}
      disabled={disabled}
      sx={sectionEditButtonSx}
    >
      Edit
    </Button>
  );
}

interface SectionSaveCancelActionsProps {
  onSave: () => void;
  onCancel: () => void;
  isSaving?: boolean;
  saveDisabled?: boolean;
}

export function SectionSaveCancelActions({
  onSave,
  onCancel,
  isSaving = false,
  saveDisabled = false,
}: SectionSaveCancelActionsProps) {
  return (
    <Box sx={{ display: 'flex', gap: '10px' }}>
      <Button
        size="small"
        variant="outlined"
        onClick={onCancel}
        disabled={isSaving}
        sx={sectionOutlinedCancelButtonSx}
      >
        Cancel
      </Button>
      <Button
        size="small"
        variant="contained"
        onClick={onSave}
        disabled={saveDisabled || isSaving}
        startIcon={
          isSaving ? <CircularProgress size={14} color="inherit" /> : undefined
        }
        sx={sectionContainedButtonSx}
      >
        {isSaving ? 'Saving…' : 'Save'}
      </Button>
    </Box>
  );
}
