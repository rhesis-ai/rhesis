'use client';

import Image from 'next/image';
import { Box, Typography } from '@mui/material';

interface OnboardingStepHeaderProps {
  title: string;
  description: string;
}

export default function OnboardingStepHeader({
  title,
  description,
}: OnboardingStepHeaderProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '10px',
        textAlign: 'center',
        width: '100%',
      }}
    >
      <Box sx={{ width: 92, height: 92, position: 'relative', flexShrink: 0 }}>
        <Image
          src="/logos/rhesis-logo-favicon.svg"
          alt="Rhesis AI"
          width={92}
          height={92}
          priority
        />
      </Box>
      <Typography
        component="h2"
        sx={{
          fontSize: 33,
          fontWeight: 800,
          lineHeight: '39.6px',
          color: 'primary.main',
          width: '100%',
        }}
      >
        {title}
      </Typography>
      <Typography
        sx={{
          fontSize: 16,
          lineHeight: '24px',
          color: theme => theme.palette.greyscale.body,
          px: 2.5,
          width: '100%',
        }}
      >
        {description}
      </Typography>
    </Box>
  );
}
