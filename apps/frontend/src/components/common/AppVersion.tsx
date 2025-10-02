'use client';

import React from 'react';
import { Typography, TypographyProps } from '@mui/material';
import { getVersionInfo, formatVersionDisplay } from '@/utils/git-utils';

interface AppVersionProps extends Omit<TypographyProps, 'children'> {
  prefix?: string;
  showPrefix?: boolean;
}

/**
 * Component to display the application version.
 * Uses the APP_VERSION environment variable set in next.config.mjs
 * and optionally includes git branch/commit information in non-production environments.
 */
export const AppVersion: React.FC<AppVersionProps> = ({
  prefix = 'v',
  showPrefix = true,
  variant = 'caption',
  color = 'text.secondary',
  ...typographyProps
}) => {
  const versionInfo = getVersionInfo();
  const displayVersion = showPrefix
    ? formatVersionDisplay(versionInfo, prefix)
    : formatVersionDisplay(versionInfo, '');

  return (
    <Typography variant={variant} color={color} {...typographyProps}>
      {displayVersion}
    </Typography>
  );
};

export default AppVersion;
