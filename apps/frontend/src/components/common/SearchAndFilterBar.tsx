'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import InputAdornment from '@mui/material/InputAdornment';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import AddIcon from '@mui/icons-material/Add';

interface SearchAndFilterBarProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  onReset?: () => void;
  hasActiveFilters?: boolean;
  onAddNew?: () => void;
  addNewLabel?: string;
  searchPlaceholder?: string;
  children?: React.ReactNode;
}

export default function SearchAndFilterBar({
  searchValue,
  onSearchChange,
  onReset,
  hasActiveFilters = false,
  onAddNew,
  addNewLabel = 'New Item',
  searchPlaceholder = 'Search...',
  children,
}: SearchAndFilterBarProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        mb: 3,
      }}
    >
      {/* Top row: Search and Actions */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', md: 'row' },
          gap: 2,
          alignItems: { xs: 'stretch', md: 'center' },
          justifyContent: 'space-between',
        }}
      >
        {/* Left side: Search and inline filters */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            gap: 2,
            flex: 1,
            alignItems: { xs: 'stretch', sm: 'center' },
          }}
        >
          <TextField
            size="small"
            placeholder={searchPlaceholder}
            value={searchValue}
            onChange={e => onSearchChange(e.target.value)}
            variant="outlined"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ minWidth: { xs: '100%', sm: 250 } }}
          />
          {children && <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>{children}</Box>}
        </Box>

        {/* Right side: Action buttons */}
        <Box
          sx={{
            display: 'flex',
            gap: 1,
            flexShrink: 0,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          {onAddNew && (
            <Button
              variant="contained"
              size="small"
              startIcon={<AddIcon />}
              onClick={onAddNew}
              sx={{ whiteSpace: 'nowrap' }}
            >
              {addNewLabel}
            </Button>
          )}
          {hasActiveFilters && onReset && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<ClearIcon />}
              onClick={onReset}
              sx={{ whiteSpace: 'nowrap' }}
            >
              Reset
            </Button>
          )}
        </Box>
      </Box>
    </Box>
  );
}

