'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';

export interface StepNavItem {
  key: string;
  label: string;
}

export interface StepNavProps {
  steps: StepNavItem[];
  activeIndex: number;
  /** Highest step the user may jump to; later steps are only reached via Next. */
  maxReachableIndex: number;
  onChange: (index: number) => void;
  'aria-label'?: string;
  sx?: SxProps<Theme>;
}

/**
 * Numbered wizard step navigation (Figma Step_navi_menu 2474:29785).
 * Same label type and underline as DetailTabNav, plus a step number and a
 * connector line between steps.
 */
export function StepNav({
  steps,
  activeIndex,
  maxReachableIndex,
  onChange,
  'aria-label': ariaLabel = 'Steps',
  sx,
}: StepNavProps) {
  return (
    <Box
      component="nav"
      aria-label={ariaLabel}
      sx={[
        { display: 'flex', alignItems: 'flex-start', gap: 1.25 },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
    >
      {steps.map((step, index) => {
        const selected = index === activeIndex;
        const reachable = index <= maxReachableIndex;
        return (
          <React.Fragment key={step.key}>
            {index > 0 && (
              <Box
                aria-hidden
                sx={{
                  width: theme => theme.spacing(6.25),
                  height: '1px',
                  mt: 2,
                  flexShrink: 0,
                  bgcolor: theme => theme.palette.greyscale.subtitle,
                }}
              />
            )}
            <Box
              component="button"
              type="button"
              aria-current={selected ? 'step' : undefined}
              disabled={!reachable}
              onClick={() => onChange(index)}
              sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: 1,
                py: '5px',
                px: 0,
                border: 'none',
                background: 'transparent',
                cursor: reachable && !selected ? 'pointer' : 'default',
                outline: 'none',
                flexShrink: 0,
                '&:focus-visible': {
                  outline: '2px solid',
                  outlineColor: 'primary.main',
                  outlineOffset: 2,
                  borderRadius: '2px',
                },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box
                  sx={{
                    width: theme => theme.spacing(3.25),
                    height: theme => theme.spacing(3.25),
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    bgcolor: theme =>
                      selected
                        ? theme.palette.greyscale.title
                        : theme.palette.greyscale.surface2,
                    color: theme =>
                      selected
                        ? theme.palette.background.paper
                        : theme.palette.greyscale.subtitle,
                  }}
                >
                  <Typography
                    component="span"
                    variant="body1"
                    sx={{ fontWeight: 700, lineHeight: 1, color: 'inherit' }}
                  >
                    {index + 1}
                  </Typography>
                </Box>
                <Typography
                  component="span"
                  sx={{
                    fontSize: 18,
                    fontWeight: 700,
                    lineHeight: '25px',
                    color: theme =>
                      selected
                        ? theme.palette.greyscale.title
                        : theme.palette.greyscale.subtitle,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {step.label}
                </Typography>
              </Box>
              <Box
                aria-hidden
                sx={{
                  width: '100%',
                  height: '3px',
                  bgcolor: theme =>
                    selected ? theme.palette.greyscale.title : 'transparent',
                }}
              />
            </Box>
          </React.Fragment>
        );
      })}
    </Box>
  );
}

export default StepNav;
