'use client';

import React, { useRef } from 'react';
import { Box, ButtonBase } from '@mui/material';
import type { DensityMode } from './summary-tokens';

interface DensityControlProps {
  density: DensityMode;
  onChange: (d: DensityMode) => void;
}

const OPTIONS: { value: DensityMode; label: string }[] = [
  { value: 'numbers', label: 'Numbers' },
  { value: 'shape', label: 'Numbers + Shape' },
  { value: 'detail', label: 'Detail' },
];

export default function DensityControl({
  density,
  onChange,
}: DensityControlProps) {
  const buttonRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const focusAndSelect = (index: number) => {
    const wrapped = (index + OPTIONS.length) % OPTIONS.length;
    onChange(OPTIONS[wrapped].value);
    buttonRefs.current[wrapped]?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      focusAndSelect(index + 1);
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      focusAndSelect(index - 1);
    } else if (e.key === 'Home') {
      e.preventDefault();
      focusAndSelect(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      focusAndSelect(OPTIONS.length - 1);
    }
  };

  return (
    <Box
      role="radiogroup"
      aria-label="Verdict grid density"
      sx={{
        display: 'inline-flex',
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        overflow: 'hidden',
      }}
    >
      {OPTIONS.map((option, index) => {
        const checked = option.value === density;
        return (
          <ButtonBase
            key={option.value}
            ref={el => {
              buttonRefs.current[index] = el;
            }}
            role="radio"
            aria-checked={checked}
            // Roving tabindex: only the checked option is a Tab stop, so
            // Tab enters/exits the group as one stop and arrow keys move
            // selection within it.
            tabIndex={checked ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={e => handleKeyDown(e, index)}
            sx={{
              px: 1.5,
              py: 0.5,
              fontSize: '0.8125rem',
              fontWeight: 500,
              color: checked ? 'primary.contrastText' : 'text.secondary',
              bgcolor: checked ? 'primary.main' : 'transparent',
              borderLeft: index > 0 ? 1 : 0,
              borderColor: 'divider',
              '&:hover': {
                bgcolor: checked ? 'primary.dark' : 'action.hover',
              },
            }}
          >
            {option.label}
          </ButtonBase>
        );
      })}
    </Box>
  );
}
