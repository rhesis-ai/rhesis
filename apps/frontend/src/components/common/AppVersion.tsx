'use client';

import React from 'react';
import { Typography, TypographyProps } from '@mui/material';

interface AppVersionProps extends Omit<TypographyProps, 'children'> {
  prefix?: string;
  showPrefix?: boolean;
}

/**
 * Component to display the application version.
 * Uses the APP_VERSION environment variable set in next.config.mjs
 */
export const AppVersion: React.FC<AppVersionProps> = ({ 
  prefix = 'v',
  showPrefix = true,
  variant = 'caption',
  color = 'text.secondary',
  ...typographyProps 
}) => {
  const version = process.env.APP_VERSION || '0.0.0';
  const displayVersion = showPrefix ? `${prefix}${version}` : version;

  return (
    <Typography 
      variant={variant}
      color={color}
      {...typographyProps}
    >
      {displayVersion}
    </Typography>
  );
};

export default AppVersion; 