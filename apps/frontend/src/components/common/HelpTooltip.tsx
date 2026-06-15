'use client';

import React from 'react';
import { Tooltip, Box } from '@mui/material';
import type { TooltipProps } from '@mui/material/Tooltip';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';

export interface HelpTooltipProps {
  /** Tooltip content — can be a plain string or rich JSX */
  title: TooltipProps['title'];
  /** Icon size in px. Defaults to 14. */
  size?: number;
  placement?: TooltipProps['placement'];
}

/**
 * A small inline help icon that shows a tooltip on hover.
 *
 * Usage:
 *   <HelpTooltip title="Explain something here" />
 *   <HelpTooltip title={<>Rich <strong>JSX</strong> content</>} placement="right" />
 */
export function HelpTooltip({
  title,
  size = 14,
  placement = 'top',
}: HelpTooltipProps) {
  return (
    <Tooltip title={title} placement={placement} arrow>
      <Box
        component="span"
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          cursor: 'help',
          color: 'text.disabled',
          '&:hover': { color: 'text.secondary' },
        }}
      >
        <HelpOutlineIcon sx={{ fontSize: size }} />
      </Box>
    </Tooltip>
  );
}

export default HelpTooltip;
