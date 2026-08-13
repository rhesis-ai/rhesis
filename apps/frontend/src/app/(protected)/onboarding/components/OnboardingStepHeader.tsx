'use client';

import { Box, Typography } from '@mui/material';
import BrandMark from '@/components/common/BrandMark';
import { useNavigationItems } from '@/contexts/NavigationItemsContext';

interface OnboardingStepHeaderProps {
  title: string;
  description: string;
}

export default function OnboardingStepHeader({
  title,
  description,
}: OnboardingStepHeaderProps) {
  const { branding } = useNavigationItems();

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
        <BrandMark
          src={branding?.iconUrl}
          size={92}
          alt={branding?.productName ?? 'Rhesis AI'}
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
