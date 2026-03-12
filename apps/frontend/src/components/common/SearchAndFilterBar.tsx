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
  /** Overrides the built-in Add button. Use when custom routing or attributes are needed. */
  renderAddButton?: () => React.ReactNode;
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
  renderAddButton,
  searchPlaceholder = 'Search...',
  children,
}: SearchAndFilterBarProps) {
  return (
    <Box
      data-testid="search-action-row"
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        gap: 2,
        alignItems: { xs: 'stretch', md: 'center' },
        justifyContent: 'space-between',
        mb: 3,
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
        {children && (
          <Box
            data-testid="filter-row"
            sx={{
              display: 'flex',
              gap: 2,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            {children}
          </Box>
        )}
      </Box>

      {/* Right side: Action buttons */}
      <Box
        data-testid="actions-box"
        sx={{
          display: 'flex',
          gap: 1,
          flexShrink: 0,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        {renderAddButton
          ? renderAddButton()
          : onAddNew && (
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
  );
}
