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
  Chip,
  Stack,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import DownloadIcon from '@mui/icons-material/Download';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import ListIcon from '@mui/icons-material/List';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import TableRowsIcon from '@mui/icons-material/TableRows';
import RateReviewIcon from '@mui/icons-material/RateReview';
import CommentOutlinedIcon from '@mui/icons-material/CommentOutlined';
import ClearAllIcon from '@mui/icons-material/ClearAll';
import ReplayIcon from '@mui/icons-material/Replay';

export interface FilterState {
  searchQuery: string;
  statusFilter: 'all' | 'passed' | 'failed';
  selectedBehaviors: string[];
  overruleFilter: 'all' | 'overruled' | 'original' | 'conflicting';
  selectedFailedMetrics: string[];
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
  isDownloading?: boolean;
  totalTests: number;
  filteredTests: number;
  viewMode?: 'split' | 'table';
  onViewModeChange?: (mode: 'split' | 'table') => void;
  onRerun?: () => void;
  isRerunning?: boolean;
  canRerun?: boolean;
}

export default function TestRunFilterBar({
  filter,
  onFilterChange,
  availableBehaviors,
  availableMetrics,
  onDownload,
  onCompare,
  isDownloading = false,
  totalTests: _totalTests,
  filteredTests: _filteredTests,
  viewMode = 'split',
  onViewModeChange,
  onRerun,
  isRerunning = false,
  canRerun = false,
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

  const handleOverruleFilterChange = (
    overruleFilter: 'all' | 'overruled' | 'original' | 'conflicting'
  ) => {
    onFilterChange({
      ...filter,
      overruleFilter,
    });
  };

  const handleMetricToggle = (metricName: string) => {
    const newMetrics = filter.selectedFailedMetrics.includes(metricName)
      ? filter.selectedFailedMetrics.filter(name => name !== metricName)
      : [...filter.selectedFailedMetrics, metricName];

    onFilterChange({
      ...filter,
      selectedFailedMetrics: newMetrics,
    });
  };

  const handleCommentFilterChange = (
    commentFilter: 'all' | 'with_comments' | 'without_comments' | 'range'
  ) => {
    onFilterChange({
      ...filter,
      commentFilter,
    });
  };

  const handleCommentRangeChange = (range: { min: number; max: number }) => {
    onFilterChange({
      ...filter,
      commentCountRange: range,
    });
  };

  const handleTaskFilterChange = (
    taskFilter: 'all' | 'with_tasks' | 'without_tasks' | 'range'
  ) => {
    onFilterChange({
      ...filter,
      taskFilter,
    });
  };

  const handleTaskRangeChange = (range: { min: number; max: number }) => {
    onFilterChange({
      ...filter,
      taskCountRange: range,
    });
  };

  const handleClearAllFilters = () => {
    onFilterChange({
      ...filter,
      selectedBehaviors: [],
      overruleFilter: 'all',
      selectedFailedMetrics: [],
      commentFilter: 'all',
      taskFilter: 'all',
    });
  };

  const activeFilterCount =
    filter.selectedBehaviors.length +
    (filter.statusFilter !== 'all' ? 1 : 0) +
    (filter.overruleFilter !== 'all' ? 1 : 0) +
    filter.selectedFailedMetrics.length +
    (filter.commentFilter !== 'all' ? 1 : 0) +
    (filter.taskFilter !== 'all' ? 1 : 0);

  const hasActiveFilters = activeFilterCount > 0;
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
      </Box>

      {/* Right side: View Mode and Actions */}
      <Box
        sx={{
          display: 'flex',
          gap: 1,
          flexShrink: 0,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        {/* View Mode Toggle */}
        {onViewModeChange && (
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
        {onRerun && (
          <Button
            size="small"
            variant="contained"
            color="primary"
            startIcon={<ReplayIcon />}
            onClick={onRerun}
            disabled={isRerunning || !canRerun}
          >
            Re-run
          </Button>
        )}
      </Box>

      {/* Advanced Filter Popover */}
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
            p: 0,
            width: 400,
            maxHeight: 600,
          },
        }}
      >
        {/* Header */}
        <Box
          sx={{
            p: 2,
            borderBottom: 1,
            borderColor: 'divider',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Typography variant="subtitle1" fontWeight={600}>
            Advanced Filters
          </Typography>
          {hasActiveFilters && (
            <Button
              size="small"
              startIcon={<ClearAllIcon />}
              onClick={handleClearAllFilters}
              color="secondary"
            >
              Clear All
            </Button>
          )}
        </Box>

        {/* Content */}
        <Box sx={{ p: 2.5, maxHeight: 520, overflow: 'auto' }}>
          <Stack spacing={3}>
            {/* Review Status */}
            <Box>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}
              >
                <RateReviewIcon fontSize="small" color="action" />
                <Typography variant="subtitle2" fontWeight={600}>
                  Review Status
                </Typography>
              </Box>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                <Chip
                  label="All"
                  size="small"
                  onClick={() => handleOverruleFilterChange('all')}
                  color={
                    filter.overruleFilter === 'all' ? 'primary' : 'default'
                  }
                  variant={
                    filter.overruleFilter === 'all' ? 'filled' : 'outlined'
                  }
                />
                <Chip
                  label="Reviewed"
                  size="small"
                  onClick={() => handleOverruleFilterChange('overruled')}
                  color={
                    filter.overruleFilter === 'overruled'
                      ? 'primary'
                      : 'default'
                  }
                  variant={
                    filter.overruleFilter === 'overruled'
                      ? 'filled'
                      : 'outlined'
                  }
                />
                <Chip
                  label="Not Reviewed"
                  size="small"
                  onClick={() => handleOverruleFilterChange('original')}
                  color={
                    filter.overruleFilter === 'original' ? 'primary' : 'default'
                  }
                  variant={
                    filter.overruleFilter === 'original' ? 'filled' : 'outlined'
                  }
                />
                <Chip
                  label="Conflicting"
                  size="small"
                  onClick={() => handleOverruleFilterChange('conflicting')}
                  color={
                    filter.overruleFilter === 'conflicting'
                      ? 'warning'
                      : 'default'
                  }
                  variant={
                    filter.overruleFilter === 'conflicting'
                      ? 'filled'
                      : 'outlined'
                  }
                />
              </Stack>
            </Box>

            <Divider />

            {/* Activity Filters */}
            <Box>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}
              >
                <CommentOutlinedIcon fontSize="small" color="action" />
                <Typography variant="subtitle2" fontWeight={600}>
                  Activity
                </Typography>
              </Box>

              {/* Comments */}
              <Box sx={{ mb: 2 }}>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    mb: 1,
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    Comments
                  </Typography>
                  <ButtonGroup size="small" variant="outlined">
                    <Button
                      onClick={() => handleCommentFilterChange('all')}
                      variant={
                        filter.commentFilter === 'all'
                          ? 'contained'
                          : 'outlined'
                      }
                      sx={{ fontSize: '0.75rem', px: 1.5, py: 0.5 }}
                    >
                      All
                    </Button>
                    <Button
                      onClick={() => handleCommentFilterChange('with_comments')}
                      variant={
                        filter.commentFilter === 'with_comments'
                          ? 'contained'
                          : 'outlined'
                      }
                      sx={{ fontSize: '0.75rem', px: 1.5, py: 0.5 }}
                    >
                      With
                    </Button>
                    <Button
                      onClick={() =>
                        handleCommentFilterChange('without_comments')
                      }
                      variant={
                        filter.commentFilter === 'without_comments'
                          ? 'contained'
                          : 'outlined'
                      }
                      sx={{ fontSize: '0.75rem', px: 1.5, py: 0.5 }}
                    >
                      Without
                    </Button>
                  </ButtonGroup>
                </Box>
              </Box>

              {/* Tasks */}
              <Box>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    mb: 1,
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    Tasks
                  </Typography>
                  <ButtonGroup size="small" variant="outlined">
                    <Button
                      onClick={() => handleTaskFilterChange('all')}
                      variant={
                        filter.taskFilter === 'all' ? 'contained' : 'outlined'
                      }
                      sx={{ fontSize: '0.75rem', px: 1.5, py: 0.5 }}
                    >
                      All
                    </Button>
                    <Button
                      onClick={() => handleTaskFilterChange('with_tasks')}
                      variant={
                        filter.taskFilter === 'with_tasks'
                          ? 'contained'
                          : 'outlined'
                      }
                      sx={{ fontSize: '0.75rem', px: 1.5, py: 0.5 }}
                    >
                      With
                    </Button>
                    <Button
                      onClick={() => handleTaskFilterChange('without_tasks')}
                      variant={
                        filter.taskFilter === 'without_tasks'
                          ? 'contained'
                          : 'outlined'
                      }
                      sx={{ fontSize: '0.75rem', px: 1.5, py: 0.5 }}
                    >
                      Without
                    </Button>
                  </ButtonGroup>
                </Box>
              </Box>
            </Box>

            <Divider />

            {/* Failed Metrics */}
            {availableMetrics && availableMetrics.length > 0 && (
              <>
                <Box>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      mb: 1.5,
                    }}
                  >
                    <CancelOutlinedIcon fontSize="small" color="action" />
                    <Typography variant="subtitle2" fontWeight={600}>
                      Failed Metrics
                    </Typography>
                    {filter.selectedFailedMetrics.length > 0 && (
                      <Chip
                        label={filter.selectedFailedMetrics.length}
                        size="small"
                        color="primary"
                        sx={{
                          height: 20,
                          fontSize: theme => theme.typography.caption.fontSize,
                          '& .MuiChip-label': {
                            fontSize: 'inherit',
                          },
                        }}
                      />
                    )}
                  </Box>
                  <FormGroup>
                    {availableMetrics.map(metric => (
                      <FormControlLabel
                        key={metric.name}
                        control={
                          <Checkbox
                            checked={filter.selectedFailedMetrics.includes(
                              metric.name
                            )}
                            onChange={() => handleMetricToggle(metric.name)}
                            size="small"
                          />
                        }
                        label={
                          <Typography variant="body2">{metric.name}</Typography>
                        }
                        sx={{ mb: 0.5 }}
                      />
                    ))}
                  </FormGroup>
                </Box>
                <Divider />
              </>
            )}

            {/* Behaviors */}
            {availableBehaviors.length > 0 && (
              <Box>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    mb: 1.5,
                  }}
                >
                  <ListIcon fontSize="small" color="action" />
                  <Typography variant="subtitle2" fontWeight={600}>
                    Behaviors
                  </Typography>
                  {filter.selectedBehaviors.length > 0 && (
                    <Chip
                      label={filter.selectedBehaviors.length}
                      size="small"
                      color="primary"
                      sx={{
                        height: 20,
                        fontSize: theme => theme.typography.caption.fontSize,
                        '& .MuiChip-label': {
                          fontSize: 'inherit',
                        },
                      }}
                    />
                  )}
                </Box>
                <FormGroup>
                  {availableBehaviors.map(behavior => (
                    <FormControlLabel
                      key={behavior.id}
                      control={
                        <Checkbox
                          checked={filter.selectedBehaviors.includes(
                            behavior.id
                          )}
                          onChange={() => handleBehaviorToggle(behavior.id)}
                          size="small"
                        />
                      }
                      label={
                        <Typography variant="body2">{behavior.name}</Typography>
                      }
                      sx={{ mb: 0.5 }}
                    />
                  ))}
                </FormGroup>
              </Box>
            )}
          </Stack>
        </Box>
      </Popover>
    </Box>
  );
}
