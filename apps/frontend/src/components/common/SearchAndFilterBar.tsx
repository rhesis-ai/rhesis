'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import InputBase from '@mui/material/InputBase';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import AddIcon from '@mui/icons-material/Add';
import { useTheme } from '@mui/material/styles';
import GridFilterButton from '@/components/common/GridFilterButton';

interface SearchAndFilterBarProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  onReset?: () => void;
  hasActiveFilters?: boolean;
  onAddNew?: () => void;
  addNewLabel?: string;
  renderAddButton?: () => React.ReactNode;
  searchPlaceholder?: string;
  children?: React.ReactNode;
  onFilterClick?: () => void;
  activeFilterCount?: number;
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
  onFilterClick,
  activeFilterCount: _activeFilterCount = 0,
}: SearchAndFilterBarProps) {
  const theme = useTheme();

  return (
    <Box
      data-testid="search-action-row"
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        gap: 2.5,
        alignItems: { xs: 'stretch', md: 'center' },
        justifyContent: 'space-between',
        mb: 3,
      }}
    >
      {/* Left: Filter button + Search field */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          flexShrink: 0,
          gap: 1.25,
        }}
      >
        {onFilterClick && <GridFilterButton onClick={onFilterClick} />}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            bgcolor: theme.greyscale.surface.default,
            borderRadius: theme.customRadius.full,
            height: 38,
            pl: 2,
            pr: 0.5,
            minWidth: { xs: '100%', sm: 288 },
            gap: 1.25,
          }}
        >
          <InputBase
            placeholder={searchPlaceholder}
            value={searchValue}
            onChange={e => onSearchChange(e.target.value)}
            sx={{
              flex: 1,
              fontSize: '0.875rem',
              '& .MuiInputBase-input': {
                p: 0,
                '&::placeholder': {
                  color: theme.greyscale.text.caption,
                  opacity: 1,
                },
              },
            }}
            inputProps={{
              'aria-label': 'search',
            }}
          />
          <IconButton
            size="small"
            sx={{
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
              width: 30,
              height: 30,
              '&:hover': {
                bgcolor: 'primary.dark',
              },
            }}
            aria-label="search"
          >
            <SearchIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Box>
      </Box>

      {/* Center: Inline filters (children) */}
      {children && (
        <Box
          data-testid="filter-row"
          sx={{
            display: 'flex',
            gap: 2,
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {children}
        </Box>
      )}

      {/* Right: Action buttons */}
      <Box
        data-testid="actions-box"
        sx={{
          display: 'flex',
          gap: 1,
          flexShrink: 0,
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'flex-end',
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
