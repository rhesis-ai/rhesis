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
import {
  GridColDef,
  GridRenderCellParams,
  GridRowSelectionModel,
} from '@mui/x-data-grid';
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
import DeleteIcon from '@mui/icons-material/Delete';
import Link from 'next/link';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import { Project } from '@/utils/api-client/interfaces/project';
import { useNotifications } from '@/components/common/NotificationContext';
import SelectMetricsDialog from '@/components/common/SelectMetricsDialog';
import { DeleteModal } from '@/components/common/DeleteModal';
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
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const notifications = useNotifications();

  const fetchMetrics = useCallback(async () => {
    if (!sessionToken || !project) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const rawIds = project.attributes?.trace_metrics;
      const metricIds = Array.isArray(rawIds) ? rawIds : [];
      if (metricIds.length === 0) {
        setMetrics([]);
        return;
      }

      const apiFactory = new ApiClientFactory(sessionToken);
      const metricsClient = apiFactory.getMetricsClient();

      const results = await Promise.allSettled(
        metricIds.map((id: string) =>
          metricsClient.getMetric(
            id as `${string}-${string}-${string}-${string}-${string}`
          )
        )
      );

      const fetchedMetrics = results
        .filter(
          (r): r is PromiseFulfilledResult<MetricDetail> =>
            r.status === 'fulfilled'
        )
        .map(r => r.value)
        .filter(m => m.metric_scope?.includes('Trace'));

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

  const handleBulkRemoveMetrics = async () => {
    if (selectedRows.length === 0) return;

    try {
      setDeleting(true);
      const currentMetricIds = project.attributes?.trace_metrics || [];
      const newMetricIds = currentMetricIds.filter(
        (id: string) => !selectedRows.includes(id)
      );

      const updatedAttributes = {
        ...(project.attributes || {}),
        trace_metrics: newMetricIds,
      };

      await onProjectUpdate({ attributes: updatedAttributes });
      notifications.show(
        `Successfully removed ${selectedRows.length} metric${selectedRows.length > 1 ? 's' : ''}`,
        { severity: 'success' }
      );
      setSelectedRows([]);
      setDeleteDialogOpen(false);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'An error occurred';
      notifications.show(`Failed to remove metrics: ${errorMessage}`, {
        severity: 'error',
      });
    } finally {
      setDeleting(false);
    }
  };

  const handleRowSelectionModelChange = (
    newSelection: GridRowSelectionModel
  ) => {
    setSelectedRows(newSelection);
  };

  const excludeMetricIds = metrics.map(m => m.id as UUID);

  const customToolbar = (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        width: '100%',
        gap: 2,
      }}
    >
      {/* Action buttons - shown when rows are selected */}
      {selectedRows.length > 0 ? (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            color="error"
            startIcon={<DeleteIcon />}
            onClick={() => setDeleteDialogOpen(true)}
            disabled={deleting}
          >
            Remove {selectedRows.length} metric
            {selectedRows.length > 1 ? 's' : ''}
          </Button>
        </Box>
      ) : (
        <Box /> // Placeholder when no rows are selected
      )}

      {/* Spacer to push buttons to the right */}
      <Box sx={{ flexGrow: 1 }} />

      <Box sx={{ display: 'flex', gap: 2 }}>
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          onClick={() => setMetricsDialogOpen(true)}
        >
          Add Metric
        </Button>
      </Box>
    </Box>
  );

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1.5,
      renderCell: (params: GridRenderCellParams<MetricDetail>) => (
        <Box
          sx={{ display: 'flex', alignItems: 'center', gap: 1, height: '100%' }}
        >
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
              <InfoOutlinedIcon
                sx={{ fontSize: '1rem', color: 'text.secondary' }}
              />
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
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
          }}
        >
          <IconButton
            size="small"
            onClick={e => {
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
      {metrics.length === 0 ? (
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
          <Box
            sx={{
              py: 4,
              px: 2,
              border: '1px dashed',
              borderColor: 'divider',
              borderRadius: theme => theme.shape.borderRadius,
              textAlign: 'center',
              bgcolor: 'background.default',
            }}
          >
            <AutoGraphIcon
              sx={{
                fontSize: theme => theme.typography.h3.fontSize,
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
        </Box>
      ) : (
        <Box sx={{ height: 400, width: '100%' }}>
          <BaseDataGrid
            rows={metrics}
            columns={columns}
            getRowId={row => row.id}
            checkboxSelection
            disableRowSelectionOnClick
            rowSelectionModel={selectedRows}
            onRowSelectionModelChange={handleRowSelectionModelChange}
            customToolbarContent={customToolbar}
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

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleBulkRemoveMetrics}
        isLoading={deleting}
        title={`Remove Metric${selectedRows.length > 1 ? 's' : ''}`}
        message={`Are you sure you want to remove ${selectedRows.length} metric${selectedRows.length > 1 ? 's' : ''} from this project? The metrics themselves will not be deleted, they will just be removed from this project's trace evaluation.`}
        itemType="metrics"
      />
    </Box>
  );
}
