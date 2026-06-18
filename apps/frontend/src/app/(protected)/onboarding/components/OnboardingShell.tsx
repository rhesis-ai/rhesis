'use client';

import { Box } from '@mui/material';
import OnboardingSidebar from './OnboardingSidebar';
import OnboardingProgressBar from './OnboardingProgressBar';

interface OnboardingShellProps {
  activeStep: number;
  children: React.ReactNode;
}

export default function OnboardingShell({
  activeStep,
  children,
}: OnboardingShellProps) {
  return (
    <Box
      sx={{
        minHeight: '100vh',
        bgcolor: 'background.default',
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        gap: { xs: 2, md: 0 },
        p: { xs: 2, md: '20px' },
      }}
    >
      <OnboardingSidebar activeStep={activeStep} />

      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'space-between',
          minHeight: { xs: 'auto', md: 'calc(100vh - 40px)' },
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
          <OnboardingProgressBar activeStep={activeStep} />
        </Box>
      </Box>
    </Box>
  );
}
