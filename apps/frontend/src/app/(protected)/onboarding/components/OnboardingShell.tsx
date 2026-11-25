'use client';

import { Box } from '@mui/material';
import OnboardingSidebar from './OnboardingSidebar';
import OnboardingProgressBar from './OnboardingProgressBar';
import { scaledVh } from '@/styles/viewport-scaling';
import type { OnboardingStepConfig } from './onboarding-steps';

interface OnboardingShellProps {
  activeStep: number;
  steps: OnboardingStepConfig[];
  children: React.ReactNode;
}

export default function OnboardingShell({
  activeStep,
  steps,
  children,
}: OnboardingShellProps) {
  return (
    <Box
      sx={{
        minHeight: scaledVh(),
        bgcolor: 'background.default',
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        gap: { xs: 2, md: 0 },
        p: { xs: 2, md: '20px' },
      }}
    >
      <OnboardingSidebar activeStep={activeStep} steps={steps} />

      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'space-between',
          minHeight: { xs: 'auto', md: `calc(${scaledVh()} - 40px)` },
          pt: { xs: 2, md: '100px' },
          pb: { xs: 3, md: '50px' },
          px: { xs: 0, md: 2 },
        }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '50px',
            width: '100%',
            maxWidth: 600,
            flex: 1,
            justifyContent: 'center',
          }}
        >
          {children}
        </Box>

        <Box sx={{ width: '100%', maxWidth: 600, mt: 4 }}>
          <OnboardingProgressBar activeStep={activeStep} steps={steps} />
        </Box>
      </Box>
    </Box>
  );
}
