import * as React from 'react';
import { Box } from '@mui/material';
import { Metadata } from 'next';
import { scaledVh } from '@/styles/viewport-scaling';

export const metadata: Metadata = {
  title: 'Onboarding',
};

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Box
      sx={{
        minHeight: scaledVh(),
        bgcolor: 'background.default',
      }}
    >
      {children}
    </Box>
  );
}
