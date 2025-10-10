'use client';

import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  ButtonGroup,
  InputAdornment,
  Badge,
  Popover,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Typography,
  Divider,
  useTheme,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import DownloadIcon from '@mui/icons-material/Download';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import ListIcon from '@mui/icons-material/List';

export interface FilterState {
  searchQuery: string;
  statusFilter: 'all' | 'passed' | 'failed';
  selectedBehaviors: string[];
}

interface TestRunFilterBarProps {
  filter: FilterState;
  onFilterChange: (filter: FilterState) => void;
  availableBehaviors: Array<{ id: string; name: string }>;
  onDownload: () => void;
  onCompare: () => void;
  isDownloading?: boolean;
  totalTests: number;
  filteredTests: number;
}

export default function TestRunFilterBar({
  filter,
  onFilterChange,
  availableBehaviors,
  onDownload,
  onCompare,
  isDownloading = false,
  totalTests,
  filteredTests,
}: TestRunFilterBarProps) {
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);

  const handleFilterClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleFilterClose = () => {
    setAnchorEl(null);
  };

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onFilterChange({
      ...filter,
      searchQuery: event.target.value,
    });
  };

  const handleStatusFilterChange = (status: 'all' | 'passed' | 'failed') => {
    onFilterChange({
      ...filter,
      statusFilter: status,
    });
  };

  const handleBehaviorToggle = (behaviorId: string) => {
    const newBehaviors = filter.selectedBehaviors.includes(behaviorId)
      ? filter.selectedBehaviors.filter(id => id !== behaviorId)
      : [...filter.selectedBehaviors, behaviorId];

    onFilterChange({
      ...filter,
      selectedBehaviors: newBehaviors,
    });
  };

  const handleClearBehaviors = () => {
    onFilterChange({
      ...filter,
      selectedBehaviors: [],
    });
  };

  const activeFilterCount =
    filter.selectedBehaviors.length + (filter.statusFilter !== 'all' ? 1 : 0);
  const open = Boolean(anchorEl);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        gap: 2,
        mb: 3,
        alignItems: { xs: 'stretch', md: 'center' },
        justifyContent: 'space-between',
      }}
    >
      {/* Left side: Search and Filters */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          gap: 2,
          flex: 1,
          alignItems: { xs: 'stretch', sm: 'center' },
        }}
      >
        {/* Search */}
        <TextField
          size="small"
          placeholder="Search tests..."
          value={filter.searchQuery}
          onChange={handleSearchChange}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{ minWidth: { xs: '100%', sm: 250 } }}
        />

        {/* Status Filter Buttons */}
        <ButtonGroup size="small" variant="outlined">
          <Button
            onClick={() => handleStatusFilterChange('all')}
            variant={filter.statusFilter === 'all' ? 'contained' : 'outlined'}
            startIcon={<ListIcon fontSize="small" />}
          >
            All
          </Button>
          <Button
            onClick={() => handleStatusFilterChange('passed')}
            variant={
              filter.statusFilter === 'passed' ? 'contained' : 'outlined'
            }
            startIcon={<CheckCircleOutlineIcon fontSize="small" />}
            sx={{
              ...(filter.statusFilter === 'passed' && {
                backgroundColor: theme.palette.success.main,
                '&:hover': {
                  backgroundColor: theme.palette.success.dark,
                },
              }),
            }}
          >
            Passed
          </Button>
          <Button
            onClick={() => handleStatusFilterChange('failed')}
            variant={
              filter.statusFilter === 'failed' ? 'contained' : 'outlined'
            }
            startIcon={<CancelOutlinedIcon fontSize="small" />}
            sx={{
              ...(filter.statusFilter === 'failed' && {
                backgroundColor: theme.palette.error.main,
                '&:hover': {
                  backgroundColor: theme.palette.error.dark,
                },
              }),
            }}
          >
            Failed
          </Button>
        </ButtonGroup>

        {/* Behavior Filter */}
        {availableBehaviors.length > 0 && (
          <Badge badgeContent={activeFilterCount} color="primary">
            <Button
              size="small"
              variant="outlined"
              startIcon={<FilterListIcon />}
              onClick={handleFilterClick}
            >
              Filters
            </Button>
          </Badge>
        )}

        {/* Results count */}
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ display: 'flex', alignItems: 'center' }}
        >
          {filteredTests === totalTests
            ? `${totalTests} tests`
            : `${filteredTests} of ${totalTests} tests`}
        </Typography>
      </Box>

      {/* Right side: Actions */}
      <Box sx={{ display: 'flex', gap: 1, flexShrink: 0 }}>
        <Button
          size="small"
          variant="outlined"
          startIcon={<CompareArrowsIcon />}
          onClick={onCompare}
        >
          Compare
        </Button>
        <Button
          size="small"
          variant="outlined"
          startIcon={<DownloadIcon />}
          onClick={onDownload}
          disabled={isDownloading}
        >
          {isDownloading ? 'Downloading...' : 'Download'}
        </Button>
      </Box>

      {/* Behavior Filter Popover */}
      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleFilterClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        PaperProps={{
          sx: {
            p: 2,
            minWidth: 250,
            maxHeight: 400,
          },
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="subtitle2" fontWeight={600}>
            Filter by Behaviors
          </Typography>
          {filter.selectedBehaviors.length > 0 && (
            <Button size="small" onClick={handleClearBehaviors}>
              Clear
            </Button>
          )}
        </Box>

        <Divider sx={{ mb: 2 }} />

        <FormGroup>
          {availableBehaviors.map(behavior => (
            <FormControlLabel
              key={behavior.id}
              control={
                <Checkbox
                  checked={filter.selectedBehaviors.includes(behavior.id)}
                  onChange={() => handleBehaviorToggle(behavior.id)}
                  size="small"
                />
              }
              label={<Typography variant="body2">{behavior.name}</Typography>}
            />
          ))}
        </FormGroup>
      </Popover>
    </Box>
  );
}
