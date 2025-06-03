'use client';

import * as React from 'react';
import { IconButton } from '@mui/material';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import { ColorModeContext } from '../providers/ThemeProvider';

export default function ThemeToggle() {
  const colorMode = React.useContext(ColorModeContext);

  return (
    <IconButton
      onClick={colorMode.toggleColorMode}
      color="inherit"
      aria-label="toggle theme"
      sx={{ ml: 1 }}
    >
      {colorMode.mode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
    </IconButton>
  );
} 