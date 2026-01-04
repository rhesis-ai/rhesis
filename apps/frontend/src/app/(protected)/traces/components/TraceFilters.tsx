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
import { TraceQueryParams } from '@/utils/api-client/interfaces/telemetry';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

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
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);

  const handleFilterChange = (key: keyof TraceQueryParams, value: any) => {
    const newFilters = { ...filters, [key]: value, offset: 0 };
    onFiltersChange(newFilters);
  };

  // Fetch projects on mount
  useEffect(() => {
    const fetchProjects = async () => {
      console.log('Fetching projects...');
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const client = clientFactory.getProjectsClient();
        const response = await client.getProjects({ limit: 100 });

        console.log('Projects API response:', response);

        // Handle both array and paginated response formats (like other components)
        const projectsData = Array.isArray(response)
          ? response
          : response?.data || [];

        console.log('Processed projects data:', projectsData);
        setProjects(projectsData);

        // Don't auto-select project - let users see all traces initially
      } catch (error) {
        console.error('Failed to fetch projects:', error);
        // Set empty array on error to prevent crashes
        setProjects([]);
      }
    };

    if (sessionToken) {
      fetchProjects();
    }
  }, [sessionToken]); // Remove filters.project_id to prevent infinite loop

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

  const handleTimeRangeFilterChange = (range: string) => {
    const now = new Date();
    let start_time_after: string | undefined = undefined;

    switch (range) {
      case '24h':
        start_time_after = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();
        break;
      case '7d':
        start_time_after = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
        break;
      case '30d':
        start_time_after = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
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
      value !== undefined &&
      value !== '' &&
      value !== 'all' &&
      !['project_id', 'limit', 'offset', 'trace_source', 'status_code', 'start_time_after'].includes(key) ||
      (key === 'trace_source' && value !== 'all' && value !== undefined) ||
      (key === 'status_code' && value !== undefined) ||
      (key === 'start_time_after' && value !== undefined)
  ).length;

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
      {/* Left side: Project, Search and Status Filters */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          gap: 2,
          flex: 1,
          alignItems: { xs: 'stretch', sm: 'center' },
        }}
      >
        {/* Project Selector */}
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Project</InputLabel>
          <Select
            value={filters.project_id || ''}
            onChange={e => handleFilterChange('project_id', e.target.value || undefined)}
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
          sx={{ minWidth: { xs: '100%', sm: 250 } }}
        />

        {/* Status Filter Buttons */}
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
            variant={filters.status_code === 'ERROR' ? 'contained' : 'outlined'}
            startIcon={<ErrorOutlineIcon fontSize="small" />}
            sx={{
              ...(filters.status_code === 'ERROR' && {
                backgroundColor: theme.palette.error.main,
                '&:hover': {
                  backgroundColor: theme.palette.error.dark,
                },
              }),
            }}
          >
            Error
          </Button>
        </ButtonGroup>

        {/* Trace Source Filter Buttons */}
        <ButtonGroup size="small" variant="outlined">
          <Button
            onClick={() => handleTraceSourceFilterChange('all')}
            variant={!filters.trace_source || filters.trace_source === 'all' ? 'contained' : 'outlined'}
            startIcon={<ListIcon fontSize="small" />}
          >
            All
          </Button>
          <Button
            onClick={() => handleTraceSourceFilterChange('test')}
            variant={filters.trace_source === 'test' ? 'contained' : 'outlined'}
            startIcon={<ScienceIcon fontSize="small" />}
          >
            Test Runs
          </Button>
          <Button
            onClick={() => handleTraceSourceFilterChange('operation')}
            variant={filters.trace_source === 'operation' ? 'contained' : 'outlined'}
            startIcon={<PublicIcon fontSize="small" />}
          >
            Operation
          </Button>
        </ButtonGroup>

        {/* Time Range Filter Buttons */}
        <ButtonGroup size="small" variant="outlined">
          <Button
            onClick={() => handleTimeRangeFilterChange('all')}
            variant={getActiveTimeRange() === 'all' ? 'contained' : 'outlined'}
            startIcon={<AccessTimeIcon fontSize="small" />}
          >
            All Time
          </Button>
          <Button
            onClick={() => handleTimeRangeFilterChange('24h')}
            variant={getActiveTimeRange() === '24h' ? 'contained' : 'outlined'}
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
            variant={getActiveTimeRange() === '30d' ? 'contained' : 'outlined'}
          >
            30d
          </Button>
        </ButtonGroup>

        {/* Advanced Filters */}
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
            {/* Environment Filter */}
            <Box>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}
              >
                <TimelineIcon fontSize="small" color="action" />
                <Typography variant="subtitle2" fontWeight={600}>
                  Environment
                </Typography>
              </Box>
              <FormControl fullWidth size="small">
                <InputLabel>Environment</InputLabel>
                <Select
                  value={filters.environment || ''}
                  onChange={e =>
                    handleFilterChange(
                      'environment',
                      e.target.value || undefined
                    )
                  }
                  label="Environment"
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value="development">Development</MenuItem>
                  <MenuItem value="staging">Staging</MenuItem>
                  <MenuItem value="production">Production</MenuItem>
                </Select>
              </FormControl>
            </Box>

            <Divider />

            {/* Time Range Filters */}
            <Box>
              <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
                Time Range
              </Typography>
              <Stack spacing={2}>
                <TextField
                  fullWidth
                  size="small"
                  label="Start Time After"
                  type="datetime-local"
                  value={filters.start_time_after || ''}
                  onChange={e =>
                    handleFilterChange(
                      'start_time_after',
                      e.target.value || undefined
                    )
                  }
                  InputLabelProps={{ shrink: true }}
                />
                <TextField
                  fullWidth
                  size="small"
                  label="Start Time Before"
                  type="datetime-local"
                  value={filters.start_time_before || ''}
                  onChange={e =>
                    handleFilterChange(
                      'start_time_before',
                      e.target.value || undefined
                    )
                  }
                  InputLabelProps={{ shrink: true }}
                />
              </Stack>
            </Box>

            <Divider />

            {/* Test Association Filters */}
            <Box>
              <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
                Test Association
              </Typography>
              <Stack spacing={2}>
                <TextField
                  fullWidth
                  size="small"
                  label="Test Run ID"
                  placeholder="Filter by test run"
                  value={filters.test_run_id || ''}
                  onChange={e =>
                    handleFilterChange(
                      'test_run_id',
                      e.target.value || undefined
                    )
                  }
                />
                <TextField
                  fullWidth
                  size="small"
                  label="Test ID"
                  placeholder="Filter by test"
                  value={filters.test_id || ''}
                  onChange={e =>
                    handleFilterChange('test_id', e.target.value || undefined)
                  }
                />
              </Stack>
            </Box>
          </Stack>
        </Box>
      </Popover>
    </Box>
  );
}
