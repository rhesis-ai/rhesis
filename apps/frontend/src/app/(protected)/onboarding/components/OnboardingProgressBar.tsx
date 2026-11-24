'use client';

import { Box } from '@mui/material';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import type { OnboardingStepConfig } from './onboarding-steps';

interface OnboardingProgressBarProps {
  activeStep: number;
  steps: OnboardingStepConfig[];
}

export default function OnboardingProgressBar({
  activeStep,
  steps,
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
      {steps.map((step, index) => (
        <Box
          key={step.id}
          sx={{
            flex: 1,
            height: 10,
            borderRadius: BORDER_RADIUS.sm,
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
