'use client';

import React from 'react';
import Image from 'next/image';
import { Box } from '@mui/material';
import { ColorModeContext } from '../providers/ThemeProvider';

export default function ThemeAwareLogo() {
  const { mode } = React.useContext(ColorModeContext);
  
  const logoSrc = mode === 'dark' 
    ? '/logos/rhesis-logo-platypus-dark-white.png'
    : '/logos/rhesis-logo-platypus.png';

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
      <Image
        src={logoSrc}
        alt="Rhesis AI Logo"
        width={150}
        height={50}
        style={{ width: 'auto' }}
        priority
      />
    </Box>
  );
}
