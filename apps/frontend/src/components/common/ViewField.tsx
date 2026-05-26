'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';

interface ViewFieldProps {
  label: string;
  value?: string | number | null;
  helperText?: string;
  fullWidth?: boolean;
  multiline?: boolean;
  /** Inner box background. Defaults to theme fieldSurface. Pass 'transparent' for technical/code fields. */
  bgcolor?: string;
  inputSx?: React.CSSProperties;
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
          fontSize: 14,
          lineHeight: '22px',
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
          minHeight: multiline ? 120 : undefined,
          alignItems: multiline ? 'flex-start' : 'center',
        }}
      >
        {children ?? (
          <Typography
            sx={{
              fontSize: 16,
              lineHeight: '24px',
              color: theme => theme.palette.greyscale.body,
              whiteSpace: multiline ? 'pre-wrap' : 'normal',
              wordBreak: 'break-word',
              ...inputSx,
            }}
          >
            {displayValue}
          </Typography>
        )}
      </Box>

      {/* Helper text — greyscale.subtitle */}
      {helperText && (
        <Typography
          sx={{
            fontSize: 12,
            lineHeight: '18px',
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
