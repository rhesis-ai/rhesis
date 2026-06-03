'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import { BORDER_RADIUS } from '@/styles/theme';

interface ViewFieldProps {
  label: string;
  value?: string | number | null;
  helperText?: string;
  fullWidth?: boolean;
  multiline?: boolean;
  /** Inner box background. Defaults to theme fieldSurface. Pass 'transparent' for technical/code fields. */
  bgcolor?: string;
  /** Extra sx applied to the value Typography (supports theme callbacks). */
  inputSx?: SxProps<Theme>;
  /** Custom value content (badges, links). When set, `value` is ignored. */
  children?: React.ReactNode;
}

/**
 * Read-only field that matches the Figma "Data Output Textfield" design:
 *   - label above in greyscale.subtitle colour (14px)
 *   - value inside a subtle-background box, no border, greyscale.body colour
 *   - optional helper text below in greyscale.subtitle colour (12px)
 */
export default function ViewField({
  label,
  value,
  helperText,
  multiline = false,
  bgcolor,
  inputSx,
  children,
}: ViewFieldProps) {
  const displayValue =
    value !== null && value !== undefined && value !== '' ? String(value) : '—';

  return (
    <Box sx={{ width: '100%' }}>
      {/* Label — greyscale.subtitle */}
      <Typography
        variant="bodyMReg"
        sx={{
          color: theme => theme.palette.greyscale.subtitle,
          px: 1.75,
          mb: 0.75,
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </Typography>

      {/* Value box */}
      <Box
        sx={{
          bgcolor: bgcolor ?? (theme => theme.palette.greyscale.fieldSurface),
          borderRadius: BORDER_RADIUS.xs,
          pl: 2,
          pr: 1.5,
          py: 2,
          alignItems: multiline ? 'flex-start' : 'center',
        }}
      >
        {children ?? (
          <Typography
            variant="body1"
            sx={[
              {
                color: theme => theme.palette.greyscale.body,
                whiteSpace: multiline ? 'pre-wrap' : 'normal',
                wordBreak: 'break-word',
              },
              ...(Array.isArray(inputSx) ? inputSx : inputSx ? [inputSx] : []),
            ]}
          >
            {displayValue}
          </Typography>
        )}
      </Box>

      {/* Helper text — greyscale.subtitle */}
      {helperText && (
        <Typography
          variant="caption"
          sx={{
            color: theme => theme.palette.greyscale.subtitle,
            px: 1.75,
            pt: 0.5,
          }}
        >
          {helperText}
        </Typography>
      )}
    </Box>
  );
}
