'use client';

import { Box } from '@mui/material';
import { ONBOARDING_STEPS } from './onboarding-steps';

interface OnboardingProgressBarProps {
  activeStep: number;
}

export default function OnboardingProgressBar({
  activeStep,
}: OnboardingProgressBarProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        gap: '10px',
        width: '100%',
        maxWidth: 600,
      }}
    >
      {ONBOARDING_STEPS.map((step, index) => (
        <Box
          key={step.id}
          sx={{
            flex: 1,
            height: 10,
            borderRadius: '6px',
            bgcolor: theme =>
              index === activeStep
                ? theme.palette.primary.main
                : theme.palette.greyscale.surface2,
          }}
        />
      ))}
    </Box>
  );
}
