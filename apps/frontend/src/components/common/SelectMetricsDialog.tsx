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
import BaseDrawer from '@/components/common/BaseDrawer';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import { PrimarySegmentedPills } from '@/components/common/GridToolbar';
import {
  drawerFieldsSx,
  drawerOutlinedFieldSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';

const METRICS_SELECT_DRAWER_WIDTH = 640;

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
  excludeMetricIds?: UUID[];
  title?: string;
  subtitle?: string;
  /** Filter metrics by scope value (e.g. Single-Turn, Multi-Turn, Trace, …) */
  scopeFilter?: string;
  /** If true, strictly requires the scope to match (ignores metrics with no scope defined) */
  strictScope?: boolean;
  /** Presentation shell — drawer is used on project detail configuration sections. */
  variant?: 'dialog' | 'drawer';
}

export default function SelectMetricsDialog({
  open,
  onClose,
  onSelect,
  excludeMetricIds = [],
  title = 'Add Metric',
  subtitle = 'Select a metric to add',
  scopeFilter,
  strictScope = false,
  variant = 'dialog',
}: SelectMetricsDialogProps) {
  const searchRef = React.useRef<HTMLInputElement>(null);

  const [metrics, setMetrics] = React.useState<MetricDetail[]>([]);
  const [filteredMetrics, setFilteredMetrics] = React.useState<MetricDetail[]>(
    []
  );
  const [searchQuery, setSearchQuery] = React.useState('');
  const [backendFilter, setBackendFilter] = React.useState<string[]>([]);
  const [isLoading, setIsLoading] = React.useState(open);
  const [error, setError] = React.useState<string | null>(null);

  const fetchMetrics = React.useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const metricsClient = new MetricsClient();
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
        // Metrics with no defined scope are compatible with any test type, UNLESS strictScope is true
        if (!metric.metric_scope || metric.metric_scope.length === 0)
          return !strictScope;
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
  }, [excludeMetricIds, scopeFilter, strictScope]);

  // Fetch metrics when dialog opens
  React.useEffect(() => {
    if (open) {
      setIsLoading(true);
      setMetrics([]);
      setFilteredMetrics([]);
      setError(null);
      setSearchQuery('');
      setBackendFilter([]);
      fetchMetrics();
    }
  }, [open, fetchMetrics]);

  const backendFilterOptions = React.useMemo(() => {
    const unique = new Map<string, string>();
    metrics.forEach(metric => {
      if (metric.backend_type?.type_value) {
        const raw = metric.backend_type.type_value;
        const display =
          raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase();
        unique.set(raw.toLowerCase(), display);
      }
    });
    return Array.from(unique.entries())
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [metrics]);

  // Filter metrics based on search query and backend pills
  React.useEffect(() => {
    let filtered = metrics;

    if (backendFilter.length > 0) {
      filtered = filtered.filter(
        metric =>
          metric.backend_type &&
          backendFilter.includes(metric.backend_type.type_value.toLowerCase())
      );
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        metric =>
          metric.name?.toLowerCase().includes(query) ||
          metric.description?.toLowerCase().includes(query) ||
          metric.backend_type?.type_value?.toLowerCase().includes(query) ||
          metric.metric_type?.type_value?.toLowerCase().includes(query)
      );
    }

    setFilteredMetrics(filtered);
  }, [searchQuery, backendFilter, metrics]);

  const handleSelect = (metricId: UUID) => {
    onSelect(metricId);
    onClose();
  };

  React.useEffect(() => {
    if (open && variant === 'drawer') {
      const timer = window.setTimeout(() => searchRef.current?.focus(), 100);
      return () => window.clearTimeout(timer);
    }
  }, [open, variant]);

  const hasActiveFilters =
    searchQuery.trim().length > 0 || backendFilter.length > 0;

  const pickerContent = (
    <>
      <Box sx={{ mb: variant === 'drawer' ? 0 : 2 }}>
        <TextField
          fullWidth
          label={variant === 'drawer' ? 'Search' : undefined}
          placeholder="Search metrics..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          inputRef={searchRef}
          sx={variant === 'drawer' ? drawerOutlinedFieldSx : undefined}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
      </Box>

      {backendFilterOptions.length > 0 && (
        <Box
          sx={{
            overflowX: 'auto',
            width: '100%',
            mb: variant === 'drawer' ? 2 : 2,
            '& > div': {
              flex: 'none',
              justifyContent: 'flex-start',
            },
          }}
        >
          <PrimarySegmentedPills
            mode="multi"
            tabs={[
              { value: '', label: 'All' },
              ...backendFilterOptions.map(option => ({
                value: option.value,
                label: option.label,
              })),
            ]}
            selectedValues={backendFilter}
            onMultiChange={setBackendFilter}
            clearValue=""
          />
        </Box>
      )}

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
              : hasActiveFilters
                ? 'No metrics match your search or filters'
                : 'No metrics match your search'}
          </Typography>
        </Box>
      ) : (
        <Stack
          spacing={1.5}
          sx={
            variant === 'dialog'
              ? { maxHeight: theme => theme.spacing(50), overflowY: 'auto' }
              : undefined
          }
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
                    {metric.metric_scope?.map(scope => (
                      <Chip
                        key={scope}
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
    </>
  );

  if (variant === 'drawer') {
    return (
      <BaseDrawer
        open={open}
        onClose={onClose}
        title={title}
        closeButtonText="Cancel"
        width={METRICS_SELECT_DRAWER_WIDTH}
      >
        <Box sx={drawerSectionSx}>
          {subtitle ? (
            <FormSectionDivider
              headline="Available metrics"
              descriptiveText={subtitle}
            />
          ) : null}
          <Box sx={drawerFieldsSx}>{pickerContent}</Box>
        </Box>
      </BaseDrawer>
    );
  }

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

      <DialogContent>{pickerContent}</DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
}
