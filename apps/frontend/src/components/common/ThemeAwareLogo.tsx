'use client';

import React from 'react';
import Image from 'next/image';
import { Box } from '@mui/material';
import { ColorModeContext } from '../providers/ThemeProvider';

interface ThemeAwareLogoProps {
  /** `BRAND_PRODUCT_NAME`, for the alt text. The wordmark image itself is still
   * the Rhesis one — only `BRAND_FAVICON_URL` replaces artwork (see BrandMark). */
  productName?: string;
}

export default function ThemeAwareLogo({
  productName = 'Rhesis AI',
}: ThemeAwareLogoProps) {
  const { mode } = React.useContext(ColorModeContext);

  const logoSrc =
    mode === 'dark'
      ? '/logos/rhesis-logo-platypus-dark-white.png'
      : '/logos/rhesis-logo-website-white-font.png';

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
      <Image
        src={logoSrc}
        alt={`${productName} logo`}
        width={130}
        height={35}
        style={{ width: 'auto', height: '35px' }}
        priority
      />
    </Box>
  );
}
