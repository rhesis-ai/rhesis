'use client';

import * as React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  CircularProgress,
  Stack,
  InputAdornment,
  Paper,
  Chip,
  SvgIcon,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import FaceIcon from '@mui/icons-material/Face';
import HandymanIcon from '@mui/icons-material/Handyman';
import BugReportIcon from '@mui/icons-material/BugReport';
import StorageIcon from '@mui/icons-material/Storage';
import NumbersIcon from '@mui/icons-material/Numbers';
import CategoryIcon from '@mui/icons-material/Category';
import ToggleOnIcon from '@mui/icons-material/ToggleOn';
import { AutoGraphIcon } from '@/components/icons';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { UUID } from 'crypto';
import { getMetricScopeIcon } from '@/constants/metric-scopes';

const RhesisAIIcon = () => (
  <SvgIcon fontSize="small" viewBox="0 0 390 371">
    <path
      d="M17.6419 272.939C72.0706 284.122 119.805 321.963 182.044 358.896C203.958 371.859 229.133 373.691 251.291 366.398C273.398 359.106 292.557 342.671 302.495 319.206C330.616 252.492 346.55 193.663 383.685 152.315C394.79 140.121 388.322 120.476 372.178 117.318C330.598 109.153 300.054 73.5806 298.171 31.2211C297.404 14.7518 278.976 5.48786 265.291 14.6646C258.213 19.4623 250.611 23.0911 242.819 25.6732C211.873 35.8618 177.127 29.0054 152.11 6.18571C146.06 0.655251 138.075 -0.513647 131.294 1.71947C124.512 3.95259 118.776 9.64007 117.172 17.7002C110.652 50.9004 86.7151 77.1221 55.7699 87.3108C47.9595 89.8928 39.6958 91.4804 31.1532 91.8293C14.6956 92.597 5.36845 110.985 14.591 124.681C38.1617 159.887 34.7097 206.678 6.11811 237.959C-5.00474 250.084 1.46325 269.746 17.6245 272.956L17.6419 272.939Z"
      fill="currentColor"
    />
  </SvgIcon>
);

const getBackendIcon = (backend: string) => {
  switch (backend.toLowerCase()) {
    case 'custom':
      return <FaceIcon fontSize="small" />;
    case 'deepeval':
    case 'ragas':
      return <HandymanIcon fontSize="small" />;
    case 'garak':
      return <BugReportIcon fontSize="small" />;
    case 'rhesis ai':
    case 'rhesis':
      return <RhesisAIIcon />;
    default:
      return <StorageIcon fontSize="small" />;
  }
};

const getScoreTypeIcon = (scoreType: string) => {
  switch (scoreType.toLowerCase()) {
    case 'numeric':
      return <NumbersIcon fontSize="small" />;
    case 'categorical':
      return <CategoryIcon fontSize="small" />;
    case 'binary':
      return <ToggleOnIcon fontSize="small" />;
    default:
      return <NumbersIcon fontSize="small" />;
  }
};

const capitalize = (s: string) =>
  s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();

interface SelectMetricsDialogProps {
  open: boolean;
  onClose: () => void;
  onSelect: (metricId: UUID) => void;
  sessionToken: string;
  excludeMetricIds?: UUID[];
  title?: string;
  subtitle?: string;
  /** Filter metrics by scope value (e.g. Single-Turn, Multi-Turn, Trace, …) */
  scopeFilter?: string;
}

export default function SelectMetricsDialog({
  open,
  onClose,
  onSelect,
  sessionToken,
  excludeMetricIds = [],
  title = 'Add Metric',
  subtitle = 'Select a metric to add',
  scopeFilter,
}: SelectMetricsDialogProps) {
  const searchRef = React.useRef<HTMLInputElement>(null);

  const [metrics, setMetrics] = React.useState<MetricDetail[]>([]);
  const [filteredMetrics, setFilteredMetrics] = React.useState<MetricDetail[]>(
    []
  );
  const [searchQuery, setSearchQuery] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const fetchMetrics = React.useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const metricsClient = new MetricsClient(sessionToken);
      const allMetrics = await metricsClient.getAllMetrics({
        sort_by: 'name',
        sort_order: 'asc',
      });

      // Filter out excluded metrics and apply scope filter
      const availableMetrics = allMetrics.filter(metric => {
        // Exclude already-selected metrics
        if (excludeMetricIds.includes(metric.id)) return false;
        // No scope filter requested — show everything
        if (!scopeFilter) return true;
        // Metrics with no defined scope are compatible with any test type
        if (!metric.metric_scope || metric.metric_scope.length === 0)
          return true;
        // Metric scope is an array — show the metric if it supports the requested scope
        return metric.metric_scope.some(
          scope => scope.toLowerCase() === scopeFilter.toLowerCase()
        );
      });

      setMetrics(availableMetrics);
      setFilteredMetrics(availableMetrics);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics');
    } finally {
      setIsLoading(false);
    }
  }, [sessionToken, excludeMetricIds, scopeFilter]);

  // Fetch metrics when dialog opens
  React.useEffect(() => {
    if (open) {
      fetchMetrics();
      setSearchQuery('');
    }
  }, [open, fetchMetrics]);

  // Filter metrics based on search query
  React.useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredMetrics(metrics);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = metrics.filter(
      metric =>
        metric.name?.toLowerCase().includes(query) ||
        metric.description?.toLowerCase().includes(query) ||
        metric.backend_type?.type_value?.toLowerCase().includes(query) ||
        metric.metric_type?.type_value?.toLowerCase().includes(query)
    );

    setFilteredMetrics(filtered);
  }, [searchQuery, metrics]);

  const handleSelect = (metricId: UUID) => {
    onSelect(metricId);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      TransitionProps={{ onEntered: () => searchRef.current?.focus() }}
      PaperProps={{
        sx: {
          maxHeight: '80vh',
        },
      }}
    >
      <DialogTitle>
        <Typography variant="h6" component="div">
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {subtitle}
        </Typography>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ mb: 2 }}>
          <TextField
            fullWidth
            placeholder="Search metrics..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            inputRef={searchRef}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
          />
        </Box>

        {isLoading ? (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              py: 4,
            }}
          >
            <CircularProgress size={24} sx={{ mr: 1 }} />
            <Typography>Loading metrics...</Typography>
          </Box>
        ) : error ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="error">{error}</Typography>
          </Box>
        ) : filteredMetrics.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="text.secondary">
              {metrics.length === 0
                ? 'No metrics available'
                : 'No metrics match your search'}
            </Typography>
          </Box>
        ) : (
          <Stack
            spacing={1.5}
            sx={{ maxHeight: theme => theme.spacing(50), overflowY: 'auto' }}
          >
            {filteredMetrics.map(metric => (
              <Paper
                key={metric.id}
                elevation={0}
                sx={{
                  p: 2,
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: 'divider',
                  transition: 'all 0.2s',
                  '&:hover': {
                    borderColor: 'primary.main',
                    backgroundColor: 'action.hover',
                    transform: 'translateY(-1px)',
                    boxShadow: 1,
                  },
                }}
                onClick={() => handleSelect(metric.id as UUID)}
              >
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1.5,
                  }}
                >
                  <AutoGraphIcon
                    sx={{ color: 'primary.main', mt: 0.5 }}
                    fontSize="medium"
                  />
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography
                      variant="subtitle2"
                      sx={{
                        fontWeight: 600,
                        mb: 0.5,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {metric.name}
                    </Typography>
                    {metric.description && (
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{
                          mb: 1,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {metric.description}
                      </Typography>
                    )}
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      {metric.backend_type?.type_value && (
                        <Chip
                          icon={getBackendIcon(metric.backend_type.type_value)}
                          label={capitalize(metric.backend_type.type_value)}
                          size="small"
                          variant="outlined"
                        />
                      )}
                      {metric.score_type && (
                        <Chip
                          icon={getScoreTypeIcon(metric.score_type)}
                          label={capitalize(metric.score_type)}
                          size="small"
                          variant="outlined"
                        />
                      )}
                      {metric.metric_scope?.map((scope, i) => (
                        <Chip
                          key={i}
                          icon={getMetricScopeIcon(scope)}
                          label={scope}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </Box>
                </Box>
              </Paper>
            ))}
          </Stack>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
}
