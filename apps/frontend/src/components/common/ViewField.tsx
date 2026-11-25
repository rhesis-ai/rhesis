'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import { rem } from '@/styles/theme-constants';

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
        sx={{
          fontSize: rem(14),
          lineHeight: rem(22),
          color: theme => theme.palette.greyscale.subtitle,
          px: '14px',
          mb: '6px',
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </Typography>

      {/* Value box */}
      <Box
        sx={{
          bgcolor: bgcolor ?? (theme => theme.palette.greyscale.fieldSurface),
          borderRadius: '4px',
          pl: '16px',
          pr: '12px',
          py: '16px',
        }}
      >
        {children ?? (
          <Typography
            sx={[
              {
                fontSize: rem(16),
                lineHeight: rem(24),
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
          sx={{
            fontSize: rem(12),
            lineHeight: rem(18),
            color: theme => theme.palette.greyscale.subtitle,
            px: '14px',
            pt: '3px',
          }}
        >
          {helperText}
        </Typography>
      )}
    </Box>
  );
}
