'use client';

import React from 'react';
import { ToggleButtonGroup, ToggleButton } from '@mui/material';

interface PillToggleOption {
  label: string;
  value: string;
}

interface PillToggleGroupProps {
  options: PillToggleOption[];
  value: string;
  onChange: (value: string) => void;
  exclusive?: boolean;
}

export default function PillToggleGroup({
  options,
  value,
  onChange,
  exclusive = true,
}: PillToggleGroupProps) {
  const handleChange = (
    _event: React.MouseEvent<HTMLElement>,
    newValue: string | null
  ) => {
    if (newValue !== null) {
      onChange(newValue);
    }
  };

  return (
    <ToggleButtonGroup
      value={value}
      exclusive={exclusive}
      onChange={handleChange}
      size="small"
      sx={{
        '& .MuiToggleButtonGroup-grouped': {
          border: 1,
          borderColor: 'primary.main',
          color: 'primary.main',
          fontSize: 13,
          fontWeight: 500,
          textTransform: 'none',
          px: 2,
          py: 0.5,
          '&.Mui-selected': {
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            '&:hover': {
              bgcolor: 'primary.dark',
            },
          },
          '&:hover:not(.Mui-selected)': {
            bgcolor: 'action.hover',
          },
          '&:first-of-type': {
            borderTopLeftRadius: 999,
            borderBottomLeftRadius: 999,
          },
          '&:last-of-type': {
            borderTopRightRadius: 999,
            borderBottomRightRadius: 999,
          },
        },
      }}
    >
      {options.map(option => (
        <ToggleButton key={option.value} value={option.value}>
          {option.label}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}
