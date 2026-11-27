'use client';

import { Box, Button, CircularProgress } from '@mui/material';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import { SkeletonSlot } from '@/components/loading/SkeletonMode';
import { BORDER_RADIUS, rem } from '@/styles/theme-constants';

/** Figma Button 1413:8164 — outlined Edit on section cards */
export const sectionEditButtonSx = {
  fontWeight: 700,
  fontSize: rem(14),
  lineHeight: rem(22),
  px: '16px',
  py: '8px',
  borderRadius: BORDER_RADIUS.sm,
  borderWidth: 2,
  borderColor: 'primary.main',
  color: 'primary.main',
  gap: '4px',
  '& .MuiButton-startIcon': {
    marginRight: '4px',
    '& > *:nth-of-type(1)': { fontSize: rem(20) },
  },
  // The theme's outlined hover fills the button and turns the label light;
  // a background set here would keep that light label on a pale fill.
  '&:hover': {
    borderWidth: 2,
    borderColor: 'primary.main',
  },
} as const;

export const sectionContainedButtonSx = {
  fontWeight: 700,
  fontSize: rem(14),
  lineHeight: rem(22),
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
    <SkeletonSlot>
      <Button
        size="small"
        variant="outlined"
        startIcon={<EditOutlinedIcon sx={{ fontSize: rem(20) }} />}
        onClick={onClick}
        disabled={disabled}
        sx={sectionEditButtonSx}
      >
        Edit
      </Button>
    </SkeletonSlot>
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
