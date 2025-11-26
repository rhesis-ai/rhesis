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
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { AutoGraphIcon } from '@/components/icons';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import type { UUID } from 'crypto';

interface SelectMetricsDialogProps {
  open: boolean;
  onClose: () => void;
  onSelect: (metricId: UUID) => void;
  sessionToken: string;
  excludeMetricIds?: UUID[];
}

export default function SelectMetricsDialog({
  open,
  onClose,
  onSelect,
  sessionToken,
  excludeMetricIds = [],
}: SelectMetricsDialogProps) {
  const [metrics, setMetrics] = React.useState<MetricDetail[]>([]);
  const [filteredMetrics, setFilteredMetrics] = React.useState<MetricDetail[]>(
    []
  );
  const [searchQuery, setSearchQuery] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Fetch metrics when dialog opens
  React.useEffect(() => {
    if (open) {
      fetchMetrics();
      setSearchQuery('');
    }
  }, [open]);

  const fetchMetrics = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const metricsClient = new MetricsClient(sessionToken);
      const response = await metricsClient.getMetrics({
        skip: 0,
        limit: 100,
        sort_by: 'name',
        sort_order: 'asc',
      });

      // Filter out excluded metrics
      const availableMetrics = response.data.filter(
        metric => !excludeMetricIds.includes(metric.id)
      );

      setMetrics(availableMetrics);
      setFilteredMetrics(availableMetrics);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch metrics');
    } finally {
      setIsLoading(false);
    }
  };

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

  const getMetricTypeLabel = (metric: MetricDetail) => {
    const backend = metric.backend_type?.type_value;
    const type = metric.metric_type?.type_value;
    return backend || type || 'Unknown';
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          maxHeight: '80vh',
        },
      }}
    >
      <DialogTitle>
        <Typography variant="h6" component="div">
          Add Metrics
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Select a metric to add to this behavior
        </Typography>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ mb: 2 }}>
          <TextField
            fullWidth
            placeholder="Search metrics..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
            autoFocus
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
          <Stack spacing={1.5} sx={{ maxHeight: '400px', overflowY: 'auto' }}>
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
                      <Chip
                        label={getMetricTypeLabel(metric)}
                        size="small"
                        variant="outlined"
                      />
                      {metric.score_type && (
                        <Chip
                          label={
                            metric.score_type.charAt(0).toUpperCase() +
                            metric.score_type.slice(1)
                          }
                          size="small"
                          variant="outlined"
                        />
                      )}
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
