'use client';

import React, { useState, useCallback } from 'react';
import {
  Paper,
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Button,
  IconButton,
  Chip
} from '@mui/material';
import { FilterList, Clear } from '@mui/icons-material';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';

interface TestResultsFiltersProps {
  onFiltersChange: (filters: Partial<TestResultsStatsOptions>) => void;
  initialFilters?: Partial<TestResultsStatsOptions>;
}

const TIME_RANGES = [
  { value: 1, label: 'Last Month' },
  { value: 3, label: 'Last 3 Months' },
  { value: 6, label: 'Last 6 Months' },
  { value: 12, label: 'Last Year' }
];

export default function TestResultsFilters({ 
  onFiltersChange, 
  initialFilters = {} 
}: TestResultsFiltersProps) {
  const [filters, setFilters] = useState<Partial<TestResultsStatsOptions>>(initialFilters);

  const updateFilters = useCallback((newFilters: Partial<TestResultsStatsOptions>) => {
    const updatedFilters = { ...filters, ...newFilters };
    setFilters(updatedFilters);
    onFiltersChange(updatedFilters);
  }, [filters, onFiltersChange]);

  const handleTimeRangeChange = (months: number) => {
    updateFilters({ months, start_date: undefined, end_date: undefined });
  };

  const clearFilters = () => {
    const clearedFilters: Partial<TestResultsStatsOptions> = { months: 6 };
    setFilters(clearedFilters);
    onFiltersChange(clearedFilters);
  };

  const hasActiveFilters = Object.keys(filters).some(key => 
    key !== 'months' && filters[key as keyof TestResultsStatsOptions] !== undefined
  );

  return (
    <Paper elevation={1} sx={{ p: 2, mb: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FilterList />
          Filters
        </Typography>
        {hasActiveFilters && (
          <Button variant="outlined" size="small" onClick={clearFilters} startIcon={<Clear />}>
            Clear Filters
          </Button>
        )}
      </Box>

      <Grid container spacing={3}>
        {/* Time Range */}
        <Grid item xs={12} sm={6} md={3}>
          <FormControl fullWidth>
            <InputLabel>Time Range</InputLabel>
            <Select
              value={filters.months || 6}
              label="Time Range"
              onChange={(e) => handleTimeRangeChange(Number(e.target.value))}
            >
              {TIME_RANGES.map((range) => (
                <MenuItem key={range.value} value={range.value}>
                  {range.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        {/* Test Run Filter - Placeholder for now */}
        <Grid item xs={12} sm={6} md={3}>
          <FormControl fullWidth>
            <InputLabel>Test Run</InputLabel>
            <Select
              value=""
              label="Test Run"
              disabled
            >
              <MenuItem value="">All Test Runs</MenuItem>
            </Select>
          </FormControl>
        </Grid>

        {/* Test Set Filter - Placeholder for now */}
        <Grid item xs={12} sm={6} md={3}>
          <FormControl fullWidth>
            <InputLabel>Test Set</InputLabel>
            <Select
              value=""
              label="Test Set"
              disabled
            >
              <MenuItem value="">All Test Sets</MenuItem>
            </Select>
          </FormControl>
        </Grid>

        {/* Behavior Filter - Placeholder for now */}
        <Grid item xs={12} sm={6} md={3}>
          <FormControl fullWidth>
            <InputLabel>Behavior</InputLabel>
            <Select
              value=""
              label="Behavior"
              disabled
            >
              <MenuItem value="">All Behaviors</MenuItem>
            </Select>
          </FormControl>
        </Grid>
      </Grid>

      {/* Active Filters Display */}
      {hasActiveFilters && (
        <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="body2" color="text.secondary" sx={{ mr: 1 }}>
            Active filters:
          </Typography>
          {Object.entries(filters).map(([key, value]) => {
            if (key === 'months' || !value) return null;
            return (
              <Chip
                key={key}
                label={`${key}: ${value}`}
                size="small"
                onDelete={() => updateFilters({ [key]: undefined })}
              />
            );
          })}
        </Box>
      )}
    </Paper>
  );
}