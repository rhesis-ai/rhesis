'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Chip,
  CircularProgress,
  Alert,
  Link as MuiLink,
  IconButton,
  Tooltip,
  Button,
} from '@mui/material';
import { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import NumbersIcon from '@mui/icons-material/Numbers';
import CategoryIcon from '@mui/icons-material/Category';
import BugReportIcon from '@mui/icons-material/BugReport';
import HandymanIcon from '@mui/icons-material/Handyman';
import StorageIcon from '@mui/icons-material/Storage';
import CloseIcon from '@mui/icons-material/Close';
import AddIcon from '@mui/icons-material/Add';
import Link from 'next/link';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import { Project } from '@/utils/api-client/interfaces/project';
import { useNotifications } from '@/components/common/NotificationContext';
import SelectMetricsDialog from '@/components/common/SelectMetricsDialog';
import type { UUID } from 'crypto';

interface ProjectTraceMetricsProps {
  project: Project;
  sessionToken: string;
  onProjectUpdate: (updatedProject: Partial<Project>) => Promise<void>;
}

const getBackendIcon = (backendType?: string) => {
  if (!backendType) return <StorageIcon fontSize="small" />;

  switch (backendType.toLowerCase()) {
    case 'deepeval':
      return <BugReportIcon fontSize="small" />;
    case 'ragas':
      return <HandymanIcon fontSize="small" />;
    default:
      return <StorageIcon fontSize="small" />;
  }
};

export default function ProjectTraceMetrics({
  project,
  sessionToken,
  onProjectUpdate,
}: ProjectTraceMetricsProps) {
  const [metrics, setMetrics] = useState<MetricDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metricsDialogOpen, setMetricsDialogOpen] = useState(false);
  const notifications = useNotifications();

  const fetchMetrics = useCallback(async () => {
    if (!sessionToken || !project) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const metricIds = project.attributes?.trace_metrics || [];
      if (metricIds.length === 0) {
        setMetrics([]);
        return;
      }

      const apiFactory = new ApiClientFactory(sessionToken);
      const metricsClient = apiFactory.getMetricsClient();
      const fetchedMetrics: MetricDetail[] = [];

      // Fetch each metric's details
      for (const id of metricIds) {
        try {
          const metric = await metricsClient.getMetric(id);
          // Only include metrics that actually have the Trace scope
          if (metric.metric_scope?.includes('Trace')) {
            fetchedMetrics.push(metric);
          }
        } catch (err) {
          console.error(`Failed to fetch metric ${id}:`, err);
        }
      }

      setMetrics(fetchedMetrics);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'An unknown error occurred';
      setError(`Failed to load metrics: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  }, [project, sessionToken]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  const handleAddMetric = async (metricId: UUID) => {
    try {
      const currentMetricIds = project.attributes?.trace_metrics || [];
      if (currentMetricIds.includes(metricId)) {
        notifications.show('Metric is already added to this project', {
          severity: 'warning',
        });
        return;
      }

      const newMetricIds = [...currentMetricIds, metricId];
      const updatedAttributes = {
        ...(project.attributes || {}),
        trace_metrics: newMetricIds,
      };

      await onProjectUpdate({ attributes: updatedAttributes });
      setMetricsDialogOpen(false);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'An error occurred';
      notifications.show(`Failed to add metric: ${errorMessage}`, {
        severity: 'error',
      });
    }
  };

  const handleRemoveMetric = async (metricId: string) => {
    try {
      const currentMetricIds = project.attributes?.trace_metrics || [];
      const newMetricIds = currentMetricIds.filter(
        (id: string) => id !== metricId
      );

      const updatedAttributes = {
        ...(project.attributes || {}),
        trace_metrics: newMetricIds,
      };

      await onProjectUpdate({ attributes: updatedAttributes });
      notifications.show('Metric removed from project successfully', {
        severity: 'success',
      });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'An error occurred';
      notifications.show(`Failed to remove metric: ${errorMessage}`, {
        severity: 'error',
      });
    }
  };

  const excludeMetricIds = metrics.map(m => m.id as UUID);

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1.5,
      renderCell: (params: GridRenderCellParams<MetricDetail>) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, height: '100%' }}>
          <AutoGraphIcon color="primary" fontSize="small" />
          <MuiLink
            component={Link}
            href={`/metrics/${params.row.id}`}
            variant="body2"
            underline="hover"
            sx={{ fontWeight: 500, color: 'text.primary' }}
          >
            {params.row.name}
          </MuiLink>
          {params.row.description && (
            <Tooltip title={params.row.description} placement="top">
              <InfoOutlinedIcon sx={{ fontSize: '1rem', color: 'text.secondary' }} />
            </Tooltip>
          )}
        </Box>
      ),
    },
    {
      field: 'score_type',
      headerName: 'Score Type',
      flex: 1,
      renderCell: (params: GridRenderCellParams<MetricDetail>) => (
        <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
          <Chip
            size="small"
            label={
              params.row.score_type.charAt(0).toUpperCase() +
              params.row.score_type.slice(1)
            }
            icon={
              params.row.score_type === 'numeric' ? (
                <NumbersIcon fontSize="small" />
              ) : (
                <CategoryIcon fontSize="small" />
              )
            }
            sx={{
              height: 24,
              fontSize: 'caption.fontSize',
            }}
          />
        </Box>
      ),
    },
    {
      field: 'backend_type',
      headerName: 'Backend',
      flex: 1,
      renderCell: (params: GridRenderCellParams<MetricDetail>) => {
        const typeValue = params.row.backend_type?.type_value;
        if (!typeValue) return null;

        return (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <Chip
              size="small"
              label={typeValue}
              icon={getBackendIcon(typeValue)}
              sx={{
                height: 24,
                fontSize: 'caption.fontSize',
              }}
            />
          </Box>
        );
      },
    },
    {
      field: 'actions',
      headerName: '',
      width: 60,
      sortable: false,
      filterable: false,
      renderCell: (params: GridRenderCellParams<MetricDetail>) => (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              handleRemoveMetric(params.row.id as string);
            }}
            sx={{
              color: 'text.secondary',
              '&:hover': {
                color: 'error.main',
                bgcolor: 'error.50',
              },
            }}
            aria-label={`Remove metric ${params.row.name}`}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      ),
    },
  ];

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', p: 3, gap: 2 }}>
        <CircularProgress size={24} />
        <Typography color="text.secondary">Loading metrics...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ my: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          mb: 2,
        }}
      >
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          onClick={() => setMetricsDialogOpen(true)}
        >
          Add Metric
        </Button>
      </Box>

      {metrics.length === 0 ? (
        <Box
          sx={{
            py: 4,
            px: 2,
            border: '1px dashed',
            borderColor: 'divider',
            borderRadius: 1,
            textAlign: 'center',
            bgcolor: 'background.default',
          }}
        >
          <AutoGraphIcon
            sx={{
              fontSize: '40px',
              color: 'text.disabled',
              mb: 1,
              opacity: 0.5,
            }}
          />
          <Typography color="text.secondary" variant="body2" sx={{ mb: 2 }}>
            No trace metrics configured. Add metrics to evaluate traces
            automatically.
          </Typography>
        </Box>
      ) : (
        <Box sx={{ height: 400, width: '100%' }}>
          <BaseDataGrid
            rows={metrics}
            columns={columns}
            getRowId={(row) => row.id}
            disableRowSelectionOnClick
            hideFooter
          />
        </Box>
      )}

      <SelectMetricsDialog
        open={metricsDialogOpen}
        onClose={() => setMetricsDialogOpen(false)}
        onSelect={handleAddMetric}
        sessionToken={sessionToken}
        excludeMetricIds={excludeMetricIds}
        title="Add Trace Metric"
        subtitle="Select a trace metric to evaluate all traces in this project"
        scopeFilter="Trace"
        strictScope={true}
      />
    </Box>
  );
}
