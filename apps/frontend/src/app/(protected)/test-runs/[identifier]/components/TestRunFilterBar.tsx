'use client';

import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  ButtonGroup,
  InputAdornment,
  Badge,
  Tooltip,
  useTheme,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import DownloadIcon from '@mui/icons-material/Download';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined';
import ListIcon from '@mui/icons-material/List';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import TableRowsIcon from '@mui/icons-material/TableRows';
import ReplayIcon from '@mui/icons-material/Replay';
import GridToolbar, {
  PrimarySegmentedPills,
} from '@/components/common/GridToolbar';
import TestRunDetailFilterDrawer, {
  extractDetailDrawerFilters,
  hasActiveTestRunDetailDrawerFilters,
  countActiveTestRunDetailDrawerFilters,
  type TestRunDetailDrawerFilters,
} from './TestRunDetailFilterDrawer';

export interface FilterState {
  searchQuery: string;
  statusFilter: 'all' | 'passed' | 'failed';
  selectedBehaviors: string[];
  overruleFilter: 'all' | 'overruled' | 'original' | 'conflicting';
  selectedMetrics: string[];
  commentFilter: 'all' | 'with_comments' | 'without_comments' | 'range';
  commentCountRange: { min: number; max: number };
  taskFilter: 'all' | 'with_tasks' | 'without_tasks' | 'range';
  taskCountRange: { min: number; max: number };
}

interface TestRunFilterBarProps {
  filter: FilterState;
  onFilterChange: (filter: FilterState) => void;
  availableBehaviors: Array<{ id: string; name: string }>;
  availableMetrics: Array<{ name: string; description?: string }>;
  onDownload: () => void;
  onCompare: () => void;
  canCompare?: boolean;
  isDownloading?: boolean;
  totalTests: number;
  filteredTests: number;
  viewMode?: 'split' | 'table';
  onViewModeChange?: (mode: 'split' | 'table') => void;
  onRerun?: () => void;
  isRerunning?: boolean;
  canRerun?: boolean;
  /** Shown when re-run is disabled (e.g. deleted test set). */
  rerunDisabledReason?: string;
  /** Linked entities tab: search + status pills + advanced filters only */
  variant?: 'default' | 'linkedEntities';
  hideViewModeToggle?: boolean;
}

export default function TestRunFilterBar({
  filter,
  onFilterChange,
  availableBehaviors,
  availableMetrics,
  onDownload,
  onCompare,
  canCompare = true,
  isDownloading = false,
  totalTests: _totalTests,
  filteredTests: _filteredTests,
  viewMode = 'split',
  onViewModeChange,
  onRerun,
  isRerunning = false,
  canRerun = false,
  rerunDisabledReason,
  variant = 'default',
  hideViewModeToggle = false,
}: TestRunFilterBarProps) {
  const showHeaderActions = variant !== 'linkedEntities';
  const showViewMode = !hideViewModeToggle && onViewModeChange;
  const theme = useTheme();
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

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

  const handleDrawerApply = (drawerFilters: TestRunDetailDrawerFilters) => {
    onFilterChange({
      ...filter,
      ...drawerFilters,
    });
  };

  const drawerFilters = extractDetailDrawerFilters(filter);
  const hasActiveDrawerFilters =
    hasActiveTestRunDetailDrawerFilters(drawerFilters);
  const activeDrawerFilterCount =
    countActiveTestRunDetailDrawerFilters(drawerFilters);

  const advancedFilterDrawer = (
    <TestRunDetailFilterDrawer
      open={filterDrawerOpen}
      onClose={() => setFilterDrawerOpen(false)}
      filters={drawerFilters}
      availableBehaviors={availableBehaviors}
      availableMetrics={availableMetrics}
      onApply={handleDrawerApply}
    />
  );

  if (variant === 'linkedEntities') {
    return (
      <>
        <GridToolbar
          searchQuery={filter.searchQuery}
          onSearchChange={value =>
            onFilterChange({ ...filter, searchQuery: value })
          }
          searchPlaceholder="Search tests..."
          searchWidth={288}
          onFilterClick={() => setFilterDrawerOpen(true)}
          hasActiveFilters={hasActiveDrawerFilters}
          activeFilterCount={activeDrawerFilterCount}
          sx={{
            px: 0,
            py: 0,
            minHeight: 'auto',
            gap: 2.5,
            width: '100%',
            flexWrap: { xs: 'wrap', lg: 'nowrap' },
            justifyContent: 'space-between',
          }}
          middleContent={
            <PrimarySegmentedPills
              mode="single"
              tabs={[
                { value: 'all', label: 'All' },
                {
                  value: 'passed',
                  label: 'Passed',
                  icon: <CheckCircleOutlineIcon />,
                },
                {
                  value: 'failed',
                  label: 'Failed',
                  icon: <BlockOutlinedIcon />,
                },
              ]}
              activeValue={filter.statusFilter}
              onSingleChange={value =>
                handleStatusFilterChange(value as 'all' | 'passed' | 'failed')
              }
            />
          }
        />
        {advancedFilterDrawer}
      </>
    );
  }

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
            startIcon={<BlockOutlinedIcon fontSize="small" />}
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

        <Badge
          badgeContent={
            activeDrawerFilterCount > 0 ? activeDrawerFilterCount : 0
          }
          color="secondary"
          invisible={!hasActiveDrawerFilters}
        >
          <Button
            size="small"
            variant="outlined"
            startIcon={<FilterListIcon />}
            onClick={() => setFilterDrawerOpen(true)}
          >
            Filters
          </Button>
        </Badge>
      </Box>

      <Box
        sx={{
          display: 'flex',
          gap: 1,
          flexShrink: 0,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        {showViewMode && (
          <Box
            sx={{
              display: 'flex',
              gap: 0.5,
              alignItems: 'center',
              mr: 1,
            }}
          >
            <ButtonGroup size="small" variant="outlined">
              <Button
                onClick={() => onViewModeChange('split')}
                variant={viewMode === 'split' ? 'contained' : 'outlined'}
                startIcon={<ViewColumnIcon fontSize="small" />}
                sx={{ minWidth: 'auto', px: 1.5 }}
              >
                Split
              </Button>
              <Button
                onClick={() => onViewModeChange('table')}
                variant={viewMode === 'table' ? 'contained' : 'outlined'}
                startIcon={<TableRowsIcon fontSize="small" />}
                sx={{ minWidth: 'auto', px: 1.5 }}
              >
                Table
              </Button>
            </ButtonGroup>
          </Box>
        )}

        {showHeaderActions &&
          (canCompare ? (
            <Button
              size="small"
              variant="outlined"
              startIcon={<CompareArrowsIcon />}
              onClick={onCompare}
            >
              Compare
            </Button>
          ) : (
            <Tooltip title="No other test runs on this test set to compare against">
              <span>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<CompareArrowsIcon />}
                  onClick={onCompare}
                  disabled
                >
                  Compare
                </Button>
              </span>
            </Tooltip>
          ))}
        {showHeaderActions && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={onDownload}
            disabled={isDownloading}
          >
            {isDownloading ? 'Downloading...' : 'Download'}
          </Button>
        )}
        {showHeaderActions &&
          onRerun &&
          (canRerun && !isRerunning ? (
            <Button
              size="small"
              variant="contained"
              color="primary"
              startIcon={<ReplayIcon />}
              onClick={onRerun}
            >
              Re-run
            </Button>
          ) : (
            <Tooltip
              title={
                isRerunning
                  ? 'Re-run in progress'
                  : (rerunDisabledReason ?? 'Re-run is unavailable')
              }
            >
              <span>
                <Button
                  size="small"
                  variant="contained"
                  color="primary"
                  startIcon={<ReplayIcon />}
                  onClick={onRerun}
                  disabled
                >
                  Re-run
                </Button>
              </span>
            </Tooltip>
          ))}
      </Box>

      {advancedFilterDrawer}
    </Box>
  );
}
