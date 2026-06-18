'use client';

import { Box, Button, CircularProgress } from '@mui/material';

interface OnboardingNavButtonsProps {
  onBack?: () => void;
  onPrimary: () => void;
  primaryLabel: string;
  primaryType?: 'button' | 'submit';
  showBack?: boolean;
  isSubmitting?: boolean;
  disabled?: boolean;
}

export default function OnboardingNavButtons({
  onBack,
  onPrimary,
  primaryLabel,
  primaryType = 'button',
  showBack = true,
  isSubmitting = false,
  disabled = false,
}: OnboardingNavButtonsProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        gap: '10px',
        justifyContent: 'center',
        width: '100%',
      }}
    >
      {showBack && onBack && (
        <Button
          variant="outlined"
          onClick={onBack}
          disabled={isSubmitting}
          sx={{
            borderWidth: 2,
            fontWeight: 700,
            fontSize: 14,
            px: 2,
            py: 1,
            '&:hover': { borderWidth: 2 },
          }}
        >
          Back
        </Button>
      )}
      <Button
        type={primaryType}
        variant="contained"
        onClick={primaryType === 'button' ? onPrimary : undefined}
        disabled={isSubmitting || disabled}
        startIcon={
          isSubmitting ? <CircularProgress size={20} color="inherit" /> : null
        }
        sx={{
          fontWeight: 700,
          fontSize: 14,
          px: 2,
          py: 1,
        }}
      >
        {primaryLabel}
      </Button>
    </Box>
  );
}
