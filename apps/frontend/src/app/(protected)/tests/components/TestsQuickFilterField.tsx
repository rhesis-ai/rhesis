'use client';

import { useCallback, useEffect, useRef } from 'react';
import { IconButton, InputAdornment, TextField } from '@mui/material';
import type { SxProps, Theme } from '@mui/material/styles';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import type { GridFilterModel } from '@mui/x-data-grid';

interface TestsQuickFilterFieldProps {
  filterModel: GridFilterModel;
  onFilterModelChange: (model: GridFilterModel) => void;
  sx?: SxProps<Theme>;
}

/** Debounced quick search matching the main Tests grid filter fields. */
export default function TestsQuickFilterField({
  filterModel,
  onFilterModelChange,
  sx,
}: TestsQuickFilterFieldProps) {
  const quickFilterInputRef = useRef<HTMLInputElement | null>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const onFilterModelChangeRef = useRef(onFilterModelChange);
  const filterModelRef = useRef(filterModel);

  useEffect(() => {
    onFilterModelChangeRef.current = onFilterModelChange;
    filterModelRef.current = filterModel;
  });

  useEffect(() => {
    if (!quickFilterInputRef.current) return;

    const quickFilterItem = filterModel.items.find(
      item => item.field === 'quickFilter' || item.field === '__quickFilter__'
    );
    const newValue = quickFilterItem?.value || '';

    if (
      quickFilterInputRef.current.value !== newValue &&
      !debounceTimerRef.current
    ) {
      quickFilterInputRef.current.value =
        typeof newValue === 'string' ? newValue : String(newValue ?? '');
    }
  }, [filterModel]);

  const handleQuickFilterChange = useCallback(() => {
    const value = quickFilterInputRef.current?.value || '';

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      debounceTimerRef.current = null;

      if (!onFilterModelChangeRef.current || !filterModelRef.current) return;

      const otherFilters = filterModelRef.current.items.filter(
        item => item.field !== 'quickFilter' && item.field !== '__quickFilter__'
      );

      onFilterModelChangeRef.current({
        ...filterModelRef.current,
        items: value
          ? [
              ...otherFilters,
              { field: 'quickFilter', operator: 'contains', value },
            ]
          : otherFilters,
      });
    }, 300);
  }, []);

  const handleQuickFilterClear = useCallback(() => {
    if (quickFilterInputRef.current) {
      quickFilterInputRef.current.value = '';
    }

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    if (!onFilterModelChangeRef.current || !filterModelRef.current) return;

    const otherFilters = filterModelRef.current.items.filter(
      item => item.field !== 'quickFilter' && item.field !== '__quickFilter__'
    );
    onFilterModelChangeRef.current({
      ...filterModelRef.current,
      items: otherFilters,
    });
  }, []);

  return (
    <TextField
      inputRef={quickFilterInputRef}
      size="small"
      placeholder="Search tests…"
      defaultValue=""
      onChange={handleQuickFilterChange}
      sx={{ minWidth: 220, ...sx }}
      InputProps={{
        startAdornment: (
          <InputAdornment position="start">
            <SearchIcon fontSize="small" />
          </InputAdornment>
        ),
        endAdornment: (
          <InputAdornment position="end">
            <IconButton
              size="small"
              onClick={handleQuickFilterClear}
              aria-label="Clear search"
            >
              <ClearIcon fontSize="small" />
            </IconButton>
          </InputAdornment>
        ),
      }}
    />
  );
}
