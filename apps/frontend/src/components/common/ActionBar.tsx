'use client';

import React from 'react';
import { Box, Button } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';

interface ActionButton {
  label: string;
  onClick: () => void;
  variant?: 'text' | 'outlined' | 'contained';
  disabled?: boolean;
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
  color?:
    | 'inherit'
    | 'primary'
    | 'secondary'
    | 'success'
    | 'error'
    | 'info'
    | 'warning';
  sx?: SxProps<Theme>;
}

interface ActionBarProps {
  leftButton?: ActionButton;
  rightButton?: ActionButton;
}

/**
 * ActionBar Component
 * Reusable bottom action bar with optional left and right buttons
 */
export default function ActionBar({ leftButton, rightButton }: ActionBarProps) {
  return (
    <Box
      sx={{
        borderTop: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        p: 2,
        display: 'flex',
        justifyContent:
          leftButton && rightButton
            ? 'space-between'
            : rightButton
              ? 'flex-end'
              : 'flex-start',
      }}
    >
      {leftButton && (
        <Button
          variant={leftButton.variant || 'outlined'}
          size="large"
          onClick={leftButton.onClick}
          disabled={leftButton.disabled}
          startIcon={leftButton.startIcon}
          endIcon={leftButton.endIcon}
          color={leftButton.color}
          sx={{
            ...leftButton.sx,
            '&.Mui-disabled': {
              opacity: 0.5,
              cursor: 'not-allowed',
              pointerEvents: 'auto',
            },
          }}
        >
          {leftButton.label}
        </Button>
      )}

      {rightButton && (
        <Button
          variant={rightButton.variant || 'contained'}
          size="large"
          onClick={rightButton.onClick}
          disabled={rightButton.disabled}
          startIcon={rightButton.startIcon}
          endIcon={rightButton.endIcon}
          color={rightButton.color}
          sx={{
            ...rightButton.sx,
            '&.Mui-disabled': {
              opacity: 0.5,
              cursor: 'not-allowed',
              pointerEvents: 'auto',
            },
          }}
        >
          {rightButton.label}
        </Button>
      )}
    </Box>
  );
}
