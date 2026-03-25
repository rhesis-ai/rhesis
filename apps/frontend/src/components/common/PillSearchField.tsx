'use client';

import React from 'react';
import { InputBase, Box, IconButton } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';

interface PillSearchFieldProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  onSearch?: () => void;
}

export default function PillSearchField({
  value,
  onChange,
  placeholder = 'Search...',
  onSearch,
}: PillSearchFieldProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && onSearch) {
      onSearch();
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        bgcolor: 'grey.100',
        borderRadius: 999,
        pl: 2,
        pr: 0.5,
        py: 0.25,
        minWidth: 220,
        maxWidth: 360,
      }}
    >
      <InputBase
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        sx={{
          flex: 1,
          fontSize: 14,
          '& .MuiInputBase-input': {
            py: 0.5,
          },
        }}
      />
      <IconButton
        onClick={onSearch}
        size="small"
        sx={{
          bgcolor: 'primary.main',
          color: 'primary.contrastText',
          width: 32,
          height: 32,
          '&:hover': {
            bgcolor: 'primary.light',
          },
        }}
      >
        <SearchIcon sx={{ fontSize: 18 }} />
      </IconButton>
    </Box>
  );
}
