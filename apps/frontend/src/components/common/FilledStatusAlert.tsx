import React from 'react';
import { Box, Typography } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { BORDER_RADIUS } from '@/styles/theme-constants';

/** Figma Alert filled success surface (nodes 1299:16004, 1435:45891). */
const FILLED_SUCCESS_BG = '#38ad87';

/** Figma-aligned filled error surface used across status UI. */
const FILLED_ERROR_BG = '#de3355';

export type FilledStatusAlertSeverity = 'success' | 'error';

export interface FilledStatusAlertProps {
  severity: FilledStatusAlertSeverity;
  title: string;
  description?: string;
}

/**
 * Figma-aligned filled status banner (Alert / Type=Filled / State=Success).
 * Green (#38ad87) or red background with white icon and text.
 */
export function FilledStatusAlert({
  severity,
  title,
  description,
}: FilledStatusAlertProps) {
  const isSuccess = severity === 'success';
  const Icon = isSuccess ? CheckCircleOutlineIcon : ErrorOutlineIcon;

  return (
    <Box
      role="status"
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        width: '100%',
        px: '30px',
        py: '12px',
        borderRadius: BORDER_RADIUS.xs,
        bgcolor: isSuccess ? FILLED_SUCCESS_BG : FILLED_ERROR_BG,
        color: '#ffffff',
      }}
    >
      <Box
        sx={{
          flexShrink: 0,
          pr: '12px',
          py: '7px',
          display: 'flex',
        }}
      >
        <Icon sx={{ fontSize: 22, color: 'inherit' }} />
      </Box>
      <Box
        sx={{
          flex: 1,
          py: '8px',
          display: 'flex',
          flexDirection: 'column',
          gap: description ? '4px' : 0,
        }}
      >
        <Typography
          sx={{
            fontWeight: 700,
            fontSize: 18,
            lineHeight: '25px',
            color: 'inherit',
          }}
        >
          {title}
        </Typography>
        {description ? (
          <Typography
            sx={{
              fontWeight: 400,
              fontSize: 16,
              lineHeight: '24px',
              color: 'inherit',
            }}
          >
            {description}
          </Typography>
        ) : null}
      </Box>
    </Box>
  );
}

export default FilledStatusAlert;
