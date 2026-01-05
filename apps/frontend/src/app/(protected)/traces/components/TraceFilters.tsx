'use client';

import { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  Button,
  ButtonGroup,
  InputAdornment,
  Badge,
  Popover,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Divider,
  Stack,
  useTheme,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import FilterListIcon from '@mui/icons-material/FilterList';
import ClearAllIcon from '@mui/icons-material/ClearAll';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ListIcon from '@mui/icons-material/List';
import TimelineIcon from '@mui/icons-material/Timeline';
import ScienceIcon from '@mui/icons-material/Science';
import PublicIcon from '@mui/icons-material/Public';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import SpeedIcon from '@mui/icons-material/Speed';
import AttachMoneyIcon from '@mui/icons-material/AttachMoney';
import DataUsageIcon from '@mui/icons-material/DataUsage';
import CloseIcon from '@mui/icons-material/Close';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import Chip from '@mui/material/Chip';
import { TraceQueryParams } from '@/utils/api-client/interfaces/telemetry';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';

interface TraceFiltersProps {
  filters: TraceQueryParams;
  onFiltersChange: (filters: TraceQueryParams) => void;
  sessionToken: string;
}

export default function TraceFilters({
  filters,
  onFiltersChange,
  sessionToken,
}: TraceFiltersProps) {
  const theme = useTheme();
  const [projects, setProjects] = useState<Array<{ id: string; name: string }>>(
    []
  );
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);

  const handleFilterChange = (key: keyof TraceQueryParams, value: any) => {
    const newFilters = { ...filters, [key]: value, offset: 0 };

    // If project changes, clear endpoint_id if the selected endpoint doesn't belong to the new project
    if (key === 'project_id' && filters.endpoint_id) {
      const selectedEndpoint = endpoints.find(
        e => e.id === filters.endpoint_id
      );
      // Clear endpoint if:
      // 1. A new project is selected AND the endpoint doesn't belong to it
      // 2. Switching to "All Projects" (value is undefined/empty) - keep the endpoint selected
      if (value && selectedEndpoint && selectedEndpoint.project_id !== value) {
        newFilters.endpoint_id = undefined;
      }
    }

    onFiltersChange(newFilters);
  };

  // Fetch projects and endpoints on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        const clientFactory = new ApiClientFactory(sessionToken);

        // Fetch projects
        const projectsClient = clientFactory.getProjectsClient();
        const projectsResponse = await projectsClient.getProjects({
          limit: 100,
        });
        const projectsData = Array.isArray(projectsResponse)
          ? projectsResponse
          : projectsResponse?.data || [];
        setProjects(projectsData);

        // Fetch endpoints (all of them, we'll filter in the UI based on selected project)
        const endpointsClient = clientFactory.getEndpointsClient();
        const endpointsResponse = await endpointsClient.getEndpoints({
          limit: 100,
        });
        const endpointsData = Array.isArray(endpointsResponse)
          ? endpointsResponse
          : endpointsResponse?.data || [];
        setEndpoints(endpointsData);
      } catch (error) {
        console.error('Failed to fetch filter data:', error);
        setProjects([]);
        setEndpoints([]);
      }
    };

    if (sessionToken) {
      fetchData();
    }
  }, [sessionToken]);

  const handleFilterClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleFilterClose = () => {
    setAnchorEl(null);
  };

  const handleStatusFilterChange = (status: string) => {
    handleFilterChange('status_code', status === 'all' ? undefined : status);
  };

  const handleTraceSourceFilterChange = (source: string) => {
    handleFilterChange('trace_source', source === 'all' ? undefined : source);
  };

  const handleDurationFilterChange = (duration: string) => {
    switch (duration) {
      case 'normal':
        // Normal: < 5 seconds
        handleFilterChange('duration_min_ms', undefined);
        handleFilterChange('duration_max_ms', 5000);
        break;
      case 'slow':
        // Slow: >= 5 seconds
        handleFilterChange('duration_min_ms', 5000);
        handleFilterChange('duration_max_ms', undefined);
        break;
      case 'all':
      default:
        // Clear all duration filters
        handleFilterChange('duration_min_ms', undefined);
        handleFilterChange('duration_max_ms', undefined);
        break;
    }
  };

  const getActiveDurationFilter = (): string => {
    if (!filters.duration_min_ms && !filters.duration_max_ms) return 'all';

    if (filters.duration_max_ms === 5000 && !filters.duration_min_ms)
      return 'normal';
    if (filters.duration_min_ms === 5000 && !filters.duration_max_ms)
      return 'slow';

    return 'custom';
  };

  const handleTimeRangeFilterChange = (range: string) => {
    const now = new Date();
    let start_time_after: string | undefined = undefined;

    switch (range) {
      case '24h':
        start_time_after = new Date(
          now.getTime() - 24 * 60 * 60 * 1000
        ).toISOString();
        break;
      case '7d':
        start_time_after = new Date(
          now.getTime() - 7 * 24 * 60 * 60 * 1000
        ).toISOString();
        break;
      case '30d':
        start_time_after = new Date(
          now.getTime() - 30 * 24 * 60 * 60 * 1000
        ).toISOString();
        break;
      case 'all':
      default:
        start_time_after = undefined;
        break;
    }

    handleFilterChange('start_time_after', start_time_after);
  };

  // Determine active time range for button highlighting
  const getActiveTimeRange = (): string => {
    if (!filters.start_time_after) return 'all';

    const filterTime = new Date(filters.start_time_after).getTime();
    const now = Date.now();
    const diff = now - filterTime;

    const hour24 = 24 * 60 * 60 * 1000;
    const day7 = 7 * 24 * 60 * 60 * 1000;
    const day30 = 30 * 24 * 60 * 60 * 1000;

    // Allow 5% tolerance for rounding
    if (Math.abs(diff - hour24) < hour24 * 0.05) return '24h';
    if (Math.abs(diff - day7) < day7 * 0.05) return '7d';
    if (Math.abs(diff - day30) < day30 * 0.05) return '30d';

    return 'custom';
  };

  const handleClearAllFilters = () => {
    const clearedFilters: TraceQueryParams = {
      project_id: filters.project_id, // Keep project selection
      limit: filters.limit || 50,
      offset: 0,
    };
    onFiltersChange(clearedFilters);
  };

  const activeFilterCount = Object.entries(filters).filter(
    ([key, value]) =>
      (value !== undefined &&
        value !== '' &&
        value !== 'all' &&
        ![
          'project_id',
          'limit',
          'offset',
          'trace_source',
          'status_code',
          'start_time_after',
          'environment',
        ].includes(key)) ||
      (key === 'trace_source' && value !== 'all' && value !== undefined) ||
      (key === 'status_code' && value !== undefined) ||
      (key === 'start_time_after' && value !== undefined) ||
      (key === 'environment' && value !== undefined)
  ).length;

  const hasActiveFilters = activeFilterCount > 0;
  const open = Boolean(anchorEl);

  // Get active filter labels for chips
  const getActiveFilterChips = () => {
    const chips: Array<{ key: string; label: string; value: any }> = [];

    // Project filter
    if (filters.project_id) {
      const project = projects.find(p => p.id === filters.project_id);
      const projectLabel = project
        ? project.name
        : filters.project_id.slice(0, 8) + '...';
      chips.push({
        key: 'project_id',
        label: `Project: ${projectLabel}`,
        value: filters.project_id,
      });
    }

    // Endpoint filter
    if (filters.endpoint_id) {
      const endpoint = endpoints.find(e => e.id === filters.endpoint_id);
      const endpointLabel = endpoint
        ? endpoint.name
        : filters.endpoint_id.slice(0, 8) + '...';
      chips.push({
        key: 'endpoint_id',
        label: `Endpoint: ${endpointLabel}`,
        value: filters.endpoint_id,
      });
    }

    // Environment filter
    if (filters.environment) {
      const envLabel =
        filters.environment.charAt(0).toUpperCase() +
        filters.environment.slice(1);
      chips.push({
        key: 'environment',
        label: `Environment: ${envLabel}`,
        value: filters.environment,
      });
    }

    // Operation search
    if (filters.span_name) {
      chips.push({
        key: 'span_name',
        label: `Operation: ${filters.span_name}`,
        value: filters.span_name,
      });
    }

    // Time range filter
    const activeTimeRange = getActiveTimeRange();
    if (activeTimeRange !== 'all') {
      const timeLabels: Record<string, string> = {
        '24h': 'Last 24 Hours',
        '7d': 'Last 7 Days',
        '30d': 'Last 30 Days',
        custom: 'Custom Time Range',
      };
      chips.push({
        key: 'start_time_after',
        label: `Time: ${timeLabels[activeTimeRange] || activeTimeRange}`,
        value: activeTimeRange,
      });
    }

    // Status filter
    if (filters.status_code) {
      chips.push({
        key: 'status_code',
        label: `Status: ${filters.status_code}`,
        value: filters.status_code,
      });
    }

    // Trace source filter
    if (filters.trace_source && filters.trace_source !== 'all') {
      const sourceLabel = filters.trace_source === 'test' ? 'Tests' : 'App';
      chips.push({
        key: 'trace_source',
        label: `Source: ${sourceLabel}`,
        value: filters.trace_source,
      });
    }

    // Duration filter
    const activeDuration = getActiveDurationFilter();
    if (activeDuration === 'normal') {
      chips.push({
        key: 'duration',
        label: 'Duration: Normal (<5s)',
        value: 'normal',
      });
    } else if (activeDuration === 'slow') {
      chips.push({
        key: 'duration',
        label: 'Duration: Slow (≥5s)',
        value: 'slow',
      });
    } else if (activeDuration === 'custom') {
      // For custom duration ranges, show the actual values
      if (filters.duration_min_ms && filters.duration_max_ms) {
        chips.push({
          key: 'duration',
          label: `Duration: ${filters.duration_min_ms / 1000}s-${filters.duration_max_ms / 1000}s`,
          value: 'custom',
        });
      } else if (filters.duration_min_ms) {
        chips.push({
          key: 'duration',
          label: `Duration: >${filters.duration_min_ms / 1000}s`,
          value: 'custom',
        });
      } else if (filters.duration_max_ms) {
        chips.push({
          key: 'duration',
          label: `Duration: <${filters.duration_max_ms / 1000}s`,
          value: 'custom',
        });
      }
    }

    // Test-related filters
    if (filters.test_run_id) {
      chips.push({
        key: 'test_run_id',
        label: `Test Run: ${filters.test_run_id.slice(0, 8)}...`,
        value: filters.test_run_id,
      });
    }
    if (filters.test_result_id) {
      chips.push({
        key: 'test_result_id',
        label: `Test Result: ${filters.test_result_id.slice(0, 8)}...`,
        value: filters.test_result_id,
      });
    }
    if (filters.test_id) {
      chips.push({
        key: 'test_id',
        label: `Test: ${filters.test_id.slice(0, 8)}...`,
        value: filters.test_id,
      });
    }

    // Time before filter
    if (filters.start_time_before) {
      const date = new Date(filters.start_time_before).toLocaleDateString();
      chips.push({
        key: 'start_time_before',
        label: `Before: ${date}`,
        value: filters.start_time_before,
      });
    }

    return chips;
  };

  const activeChips = getActiveFilterChips();

  // Filter endpoints by selected project
  const filteredEndpoints = filters.project_id
    ? endpoints.filter(e => e.project_id === filters.project_id)
    : endpoints;

  return (
    <>
      <Stack spacing={1.5} sx={{ mb: 1.5 }}>
        {/* Row 1: Context & Search */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            gap: 2,
            alignItems: { xs: 'stretch', sm: 'center' },
            flexWrap: 'wrap',
          }}
        >
          {/* Project Selector */}
          <FormControl
            size="small"
            sx={{ minWidth: 160, flex: { xs: '1 1 100%', sm: '0 0 auto' } }}
          >
            <InputLabel>Project</InputLabel>
            <Select
              value={filters.project_id || ''}
              onChange={e =>
                handleFilterChange('project_id', e.target.value || undefined)
              }
              label="Project"
            >
              <MenuItem value="">All Projects</MenuItem>
              {projects?.map(project => (
                <MenuItem key={project.id} value={project.id}>
                  {project.name}
                </MenuItem>
              )) || []}
            </Select>
          </FormControl>

          {/* Endpoint Selector */}
          <FormControl
            size="small"
            sx={{ minWidth: 180, flex: { xs: '1 1 100%', sm: '0 0 auto' } }}
            disabled={filteredEndpoints.length === 0}
          >
            <InputLabel>Endpoint</InputLabel>
            <Select
              value={filters.endpoint_id || ''}
              onChange={e =>
                handleFilterChange('endpoint_id', e.target.value || undefined)
              }
              label="Endpoint"
            >
              <MenuItem value="">
                {filters.project_id
                  ? filteredEndpoints.length === 0
                    ? 'No endpoints in project'
                    : 'All Endpoints'
                  : 'All Endpoints'}
              </MenuItem>
              {filteredEndpoints.map(endpoint => (
                <MenuItem key={endpoint.id} value={endpoint.id}>
                  {endpoint.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Environment Selector */}
          <FormControl
            size="small"
            sx={{ minWidth: 140, flex: { xs: '1 1 100%', sm: '0 0 auto' } }}
          >
            <InputLabel>Environment</InputLabel>
            <Select
              value={filters.environment || ''}
              onChange={e =>
                handleFilterChange('environment', e.target.value || undefined)
              }
              label="Environment"
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="development">Development</MenuItem>
              <MenuItem value="staging">Staging</MenuItem>
              <MenuItem value="production">Production</MenuItem>
            </Select>
          </FormControl>

          {/* Search */}
          <TextField
            size="small"
            placeholder="Search operations..."
            value={filters.span_name || ''}
            onChange={e =>
              handleFilterChange('span_name', e.target.value || undefined)
            }
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ minWidth: 200, flex: { xs: '1 1 100%', sm: '1 1 auto' } }}
          />
        </Box>

        {/* Row 2: Filters & Actions */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            gap: 2,
            alignItems: { xs: 'stretch', sm: 'center' },
            flexWrap: 'wrap',
          }}
        >
          {/* Time Range Filter */}
          <ButtonGroup size="small" variant="outlined">
            <Button
              onClick={() => handleTimeRangeFilterChange('all')}
              variant={
                getActiveTimeRange() === 'all' ? 'contained' : 'outlined'
              }
              startIcon={<ListIcon fontSize="small" />}
            >
              All
            </Button>
            <Button
              onClick={() => handleTimeRangeFilterChange('24h')}
              variant={
                getActiveTimeRange() === '24h' ? 'contained' : 'outlined'
              }
            >
              24h
            </Button>
            <Button
              onClick={() => handleTimeRangeFilterChange('7d')}
              variant={getActiveTimeRange() === '7d' ? 'contained' : 'outlined'}
            >
              7d
            </Button>
            <Button
              onClick={() => handleTimeRangeFilterChange('30d')}
              variant={
                getActiveTimeRange() === '30d' ? 'contained' : 'outlined'
              }
            >
              30d
            </Button>
          </ButtonGroup>

          <Divider
            orientation="vertical"
            flexItem
            sx={{ display: { xs: 'none', sm: 'block' } }}
          />

          {/* Status Filter */}
          <ButtonGroup size="small" variant="outlined">
            <Button
              onClick={() => handleStatusFilterChange('all')}
              variant={!filters.status_code ? 'contained' : 'outlined'}
              startIcon={<ListIcon fontSize="small" />}
            >
              All
            </Button>
            <Button
              onClick={() => handleStatusFilterChange('OK')}
              variant={filters.status_code === 'OK' ? 'contained' : 'outlined'}
              startIcon={<CheckCircleOutlineIcon fontSize="small" />}
              sx={{
                ...(filters.status_code === 'OK' && {
                  backgroundColor: theme.palette.success.main,
                  color: 'white',
                  '&:hover': {
                    backgroundColor: theme.palette.success.dark,
                  },
                }),
              }}
            >
              OK
            </Button>
            <Button
              onClick={() => handleStatusFilterChange('ERROR')}
              variant={
                filters.status_code === 'ERROR' ? 'contained' : 'outlined'
              }
              startIcon={<ErrorOutlineIcon fontSize="small" />}
              sx={{
                ...(filters.status_code === 'ERROR' && {
                  backgroundColor: theme.palette.error.main,
                  color: 'white',
                  '&:hover': {
                    backgroundColor: theme.palette.error.dark,
                  },
                }),
              }}
            >
              Error
            </Button>
          </ButtonGroup>

          <Divider
            orientation="vertical"
            flexItem
            sx={{ display: { xs: 'none', sm: 'block' } }}
          />

          {/* Trace Source Filter */}
          <ButtonGroup size="small" variant="outlined">
            <Button
              onClick={() => handleTraceSourceFilterChange('all')}
              variant={
                !filters.trace_source || filters.trace_source === 'all'
                  ? 'contained'
                  : 'outlined'
              }
              startIcon={<ListIcon fontSize="small" />}
            >
              All
            </Button>
            <Button
              onClick={() => handleTraceSourceFilterChange('test')}
              variant={
                filters.trace_source === 'test' ? 'contained' : 'outlined'
              }
              startIcon={<ScienceIcon fontSize="small" />}
            >
              Tests
            </Button>
            <Button
              onClick={() => handleTraceSourceFilterChange('operation')}
              variant={
                filters.trace_source === 'operation' ? 'contained' : 'outlined'
              }
              startIcon={<PublicIcon fontSize="small" />}
            >
              App
            </Button>
          </ButtonGroup>

          <Divider
            orientation="vertical"
            flexItem
            sx={{ display: { xs: 'none', sm: 'block' } }}
          />

          {/* Duration Filter */}
          <ButtonGroup size="small" variant="outlined">
            <Button
              onClick={() => handleDurationFilterChange('all')}
              variant={
                getActiveDurationFilter() === 'all' ? 'contained' : 'outlined'
              }
              startIcon={<ListIcon fontSize="small" />}
            >
              All
            </Button>
            <Button
              onClick={() => handleDurationFilterChange('normal')}
              variant={
                getActiveDurationFilter() === 'normal'
                  ? 'contained'
                  : 'outlined'
              }
              startIcon={<SpeedIcon fontSize="small" />}
            >
              Normal
            </Button>
            <Button
              onClick={() => handleDurationFilterChange('slow')}
              variant={
                getActiveDurationFilter() === 'slow' ? 'contained' : 'outlined'
              }
              startIcon={<HourglassEmptyIcon fontSize="small" />}
            >
              Slow
            </Button>
          </ButtonGroup>

          {/* Spacer */}
          <Box sx={{ flex: 1, minWidth: { xs: 0, sm: 20 } }} />

          {/* Advanced Filters Button */}
          <Badge badgeContent={activeFilterCount} color="primary">
            <Button
              size="small"
              variant="outlined"
              startIcon={<FilterListIcon />}
              onClick={handleFilterClick}
            >
              More Filters
            </Button>
          </Badge>
        </Box>

        {/* Row 3: Active Filter Chips */}
        {activeChips.length > 0 && (
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 1,
              alignItems: 'center',
            }}
          >
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mr: 0.5 }}
            >
              Active filters:
            </Typography>
            {activeChips.map(chip => (
              <Chip
                key={chip.key}
                label={chip.label}
                size="small"
                onDelete={() => {
                  // Handle duration filter specially - clear both min and max
                  if (chip.key === 'duration') {
                    handleFilterChange('duration_min_ms', undefined);
                    handleFilterChange('duration_max_ms', undefined);
                  } else {
                    handleFilterChange(
                      chip.key as keyof TraceQueryParams,
                      undefined
                    );
                  }
                }}
                deleteIcon={<CloseIcon />}
                sx={{
                  height: 24,
                  '& .MuiChip-label': { px: 1.5, py: 0 },
                }}
              />
            ))}
          </Box>
        )}
      </Stack>

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
            {/* Custom Time Range */}
            <Box>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}
              >
                <AccessTimeIcon fontSize="small" color="action" />
                <Typography variant="subtitle2" fontWeight={600}>
                  Custom Time Range
                </Typography>
              </Box>
              <Stack spacing={2}>
                <TextField
                  fullWidth
                  size="small"
                  label="Start Time After"
                  type="datetime-local"
                  value={
                    filters.start_time_after
                      ? new Date(filters.start_time_after)
                          .toISOString()
                          .slice(0, 16)
                      : ''
                  }
                  onChange={e =>
                    handleFilterChange(
                      'start_time_after',
                      e.target.value
                        ? new Date(e.target.value).toISOString()
                        : undefined
                    )
                  }
                  InputLabelProps={{ shrink: true }}
                  helperText="Override quick time filters above"
                />
                <TextField
                  fullWidth
                  size="small"
                  label="Start Time Before"
                  type="datetime-local"
                  value={
                    filters.start_time_before
                      ? new Date(filters.start_time_before)
                          .toISOString()
                          .slice(0, 16)
                      : ''
                  }
                  onChange={e =>
                    handleFilterChange(
                      'start_time_before',
                      e.target.value
                        ? new Date(e.target.value).toISOString()
                        : undefined
                    )
                  }
                  InputLabelProps={{ shrink: true }}
                />
              </Stack>
            </Box>

            <Divider />

            {/* Test Association */}
            <Box>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}
              >
                <ScienceIcon fontSize="small" color="action" />
                <Typography variant="subtitle2" fontWeight={600}>
                  Test Association
                </Typography>
              </Box>
              <Stack spacing={2}>
                <TextField
                  fullWidth
                  size="small"
                  label="Test Run ID"
                  placeholder="e.g., 123e4567-e89b-12d3"
                  value={filters.test_run_id || ''}
                  onChange={e =>
                    handleFilterChange(
                      'test_run_id',
                      e.target.value || undefined
                    )
                  }
                  helperText="Filter traces from a specific test run"
                />
                <TextField
                  fullWidth
                  size="small"
                  label="Test Result ID"
                  placeholder="e.g., 123e4567-e89b-12d3"
                  value={filters.test_result_id || ''}
                  onChange={e =>
                    handleFilterChange(
                      'test_result_id',
                      e.target.value || undefined
                    )
                  }
                />
                <TextField
                  fullWidth
                  size="small"
                  label="Test ID"
                  placeholder="e.g., 123e4567-e89b-12d3"
                  value={filters.test_id || ''}
                  onChange={e =>
                    handleFilterChange('test_id', e.target.value || undefined)
                  }
                />
              </Stack>
            </Box>

            <Divider />

            {/* Tips */}
            <Box
              sx={{
                p: 1.5,
                backgroundColor:
                  theme.palette.mode === 'dark'
                    ? 'rgba(255, 255, 255, 0.05)'
                    : 'rgba(0, 0, 0, 0.02)',
                borderRadius: theme => theme.shape.borderRadius,
              }}
            >
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  mb: 0.5,
                }}
              >
                <LightbulbIcon sx={{ fontSize: 14 }} />
                <strong>Pro tip:</strong> Use the search box to filter by
                operation name (e.g., "ai.llm.invoke")
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Use Test Run filter to analyze traces from specific test
                executions
              </Typography>
            </Box>
          </Stack>
        </Box>
      </Popover>
    </>
  );
}
