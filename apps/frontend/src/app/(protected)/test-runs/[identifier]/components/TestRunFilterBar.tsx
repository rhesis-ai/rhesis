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
  Switch,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Tooltip,
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
import GavelIcon from '@mui/icons-material/Gavel';
import CommentOutlinedIcon from '@mui/icons-material/CommentOutlined';
import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import ClearAllIcon from '@mui/icons-material/ClearAll';

export interface FilterState {
  searchQuery: string;
  statusFilter: 'all' | 'passed' | 'failed';
  selectedBehaviors: string[];
  overruleFilter: 'all' | 'overruled' | 'original';
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
}

export default function TestRunFilterBar({
  filter,
  onFilterChange,
  availableBehaviors,
  availableMetrics,
  onDownload,
  onCompare,
  isDownloading = false,
  totalTests,
  filteredTests,
  viewMode = 'split',
  onViewModeChange,
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

  const handleOverruleFilterChange = (overruleFilter: 'all' | 'overruled' | 'original') => {
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

  const handleCommentFilterChange = (commentFilter: 'all' | 'with_comments' | 'without_comments' | 'range') => {
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

  const handleTaskFilterChange = (taskFilter: 'all' | 'with_tasks' | 'without_tasks' | 'range') => {
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
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mr: 0.5, display: { xs: 'none', sm: 'block' } }}
            >
              View:
            </Typography>
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
            minWidth: 350,
            maxHeight: 600,
            overflow: 'hidden',
          },
        }}
      >
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle1" fontWeight={600}>
            Advanced Filters
          </Typography>
        </Box>

        <Box sx={{ maxHeight: 500, overflow: 'auto', p: 1 }}>
          {/* Overrule Status Filter */}
          <Accordion defaultExpanded>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <GavelIcon fontSize="small" />
                <Typography variant="subtitle2">Overrule Status</Typography>
                {filter.overruleFilter !== 'all' && (
                  <Badge color="primary" variant="dot" />
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <FormControl fullWidth size="small">
                <Select
                  value={filter.overruleFilter}
                  onChange={(e) => handleOverruleFilterChange(e.target.value as any)}
                >
                  <MenuItem value="all">All Tests</MenuItem>
                  <MenuItem value="overruled">Overruled Only</MenuItem>
                  <MenuItem value="original">Original Judgments Only</MenuItem>
                </Select>
              </FormControl>
            </AccordionDetails>
          </Accordion>

          {/* Failed Metrics Filter */}
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CancelOutlinedIcon fontSize="small" />
                <Typography variant="subtitle2">Failed Metrics</Typography>
                {filter.selectedFailedMetrics.length > 0 && (
                  <Badge badgeContent={filter.selectedFailedMetrics.length} color="primary" />
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <FormGroup>
                {availableMetrics?.map(metric => (
                  <FormControlLabel
                    key={metric.name}
                    control={
                      <Checkbox
                        checked={filter.selectedFailedMetrics.includes(metric.name)}
                        onChange={() => handleMetricToggle(metric.name)}
                        size="small"
                      />
                    }
                    label={
                      <Box>
                        <Typography variant="body2">{metric.name}</Typography>
                        {metric.description && (
                          <Typography variant="caption" color="text.secondary">
                            {metric.description}
                          </Typography>
                        )}
                      </Box>
                    }
                  />
                ))}
              </FormGroup>
            </AccordionDetails>
          </Accordion>

          {/* Comment Activity Filter */}
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CommentOutlinedIcon fontSize="small" />
                <Typography variant="subtitle2">Comment Activity</Typography>
                {filter.commentFilter !== 'all' && (
                  <Badge color="primary" variant="dot" />
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                <Select
                  value={filter.commentFilter}
                  onChange={(e) => handleCommentFilterChange(e.target.value as any)}
                >
                  <MenuItem value="all">All Tests</MenuItem>
                  <MenuItem value="with_comments">With Comments</MenuItem>
                  <MenuItem value="without_comments">Without Comments</MenuItem>
                  <MenuItem value="range">Comment Count Range</MenuItem>
                </Select>
              </FormControl>
              
              {filter.commentFilter === 'range' && (
                <Box sx={{ px: 1 }}>
                  <Typography variant="caption" color="text.secondary" gutterBottom>
                    Comment Count: {filter.commentCountRange.min} - {filter.commentCountRange.max}
                  </Typography>
                  <Slider
                    value={[filter.commentCountRange.min, filter.commentCountRange.max]}
                    onChange={(_, newValue) => {
                      const [min, max] = newValue as number[];
                      handleCommentRangeChange({ min, max });
                    }}
                    valueLabelDisplay="auto"
                    min={0}
                    max={20}
                    marks={[
                      { value: 0, label: '0' },
                      { value: 10, label: '10' },
                      { value: 20, label: '20+' },
                    ]}
                  />
                </Box>
              )}
            </AccordionDetails>
          </Accordion>

          {/* Task Activity Filter */}
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TaskAltOutlinedIcon fontSize="small" />
                <Typography variant="subtitle2">Task Activity</Typography>
                {filter.taskFilter !== 'all' && (
                  <Badge color="primary" variant="dot" />
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                <Select
                  value={filter.taskFilter}
                  onChange={(e) => handleTaskFilterChange(e.target.value as any)}
                >
                  <MenuItem value="all">All Tests</MenuItem>
                  <MenuItem value="with_tasks">With Tasks</MenuItem>
                  <MenuItem value="without_tasks">Without Tasks</MenuItem>
                  <MenuItem value="range">Task Count Range</MenuItem>
                </Select>
              </FormControl>
              
              {filter.taskFilter === 'range' && (
                <Box sx={{ px: 1 }}>
                  <Typography variant="caption" color="text.secondary" gutterBottom>
                    Task Count: {filter.taskCountRange.min} - {filter.taskCountRange.max}
                  </Typography>
                  <Slider
                    value={[filter.taskCountRange.min, filter.taskCountRange.max]}
                    onChange={(_, newValue) => {
                      const [min, max] = newValue as number[];
                      handleTaskRangeChange({ min, max });
                    }}
                    valueLabelDisplay="auto"
                    min={0}
                    max={10}
                    marks={[
                      { value: 0, label: '0' },
                      { value: 5, label: '5' },
                      { value: 10, label: '10+' },
                    ]}
                  />
                </Box>
              )}
            </AccordionDetails>
          </Accordion>

          {/* Behaviors Filter */}
          {availableBehaviors.length > 0 && (
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ListIcon fontSize="small" />
                  <Typography variant="subtitle2">Behaviors</Typography>
                  {filter.selectedBehaviors.length > 0 && (
                    <Badge badgeContent={filter.selectedBehaviors.length} color="primary" />
                  )}
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    Select behaviors to filter by
                  </Typography>
                  {filter.selectedBehaviors.length > 0 && (
                    <Button size="small" onClick={handleClearBehaviors}>
                      Clear
                    </Button>
                  )}
                </Box>
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
              </AccordionDetails>
            </Accordion>
          )}
        </Box>
      </Popover>
    </Box>
  );
}
