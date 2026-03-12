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
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        mb: 3,
      }}
    >
      {/* Top row: Search and Action buttons */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          gap: 2,
          alignItems: { xs: 'stretch', sm: 'center' },
          justifyContent: 'space-between',
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
          sx={{ minWidth: { xs: '100%', sm: theme => theme.spacing(31) } }}
        />

        {/* Action buttons */}
        <Box
          sx={{
            display: 'flex',
            gap: 1,
            flexShrink: 0,
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

      {/* Filter row: inline filter chips and controls */}
      {children && (
        <Box
          sx={{
            display: 'flex',
            gap: 1.5,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          {children}
        </Box>
      )}
    </Box>
  );
}
