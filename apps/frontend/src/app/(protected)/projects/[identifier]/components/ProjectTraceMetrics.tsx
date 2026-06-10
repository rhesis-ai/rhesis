'use client';

import React, {
  forwardRef,
  useCallback,
  useContext,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
} from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  IconButton,
  Link as MuiLink,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  alpha,
  useTheme,
  type SxProps,
  type Theme,
} from '@mui/material/styles';
import {
  GridColDef,
  GridRenderCellParams,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import Link from 'next/link';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import GridBadge from '@/components/common/GridBadge';
import GridToolbar, {
  linkedDataGridRowSx,
  linkedGridToolbarSx,
  sectionCardGridBleedSx,
} from '@/components/common/GridToolbar';
import {
  ROW_ACTIONS_CLASS,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
import { DeleteIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { MetricDetail } from '@/utils/api-client/interfaces/metric';
import { Project } from '@/utils/api-client/interfaces/project';
import { useNotifications } from '@/components/common/NotificationContext';
import SelectMetricsDialog from '@/components/common/SelectMetricsDialog';
import SectionEmptyState from '@/components/common/SectionEmptyState';
import { DeleteModal } from '@/components/common/DeleteModal';
import type { UUID } from 'crypto';

interface ProjectTraceMetricsProps {
  project: Project;
  sessionToken: string;
  onProjectUpdate: (updatedProject: Partial<Project>) => Promise<boolean>;
}

export interface ProjectTraceMetricsHandle {
  openAddDialog: () => void;
}

interface TraceMetricsToolbarState {
  searchQuery: string;
  setSearchQuery: (value: string) => void;
}

const TraceMetricsToolbarContext =
  React.createContext<TraceMetricsToolbarState>({
    searchQuery: '',
    setSearchQuery: () => {},
  });

function TraceMetricsToolbar() {
  const { searchQuery, setSearchQuery } = useContext(
    TraceMetricsToolbarContext
  );

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search metrics…"
      searchWidth={288}
      rightContent={
        <>
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
      sx={linkedGridToolbarSx}
    />
  );
}

function getTraceMetricIds(project: Project): string[] {
  const rawIds = project.attributes?.trace_metrics;
  return Array.isArray(rawIds) ? rawIds.map(String) : [];
}

export default forwardRef<ProjectTraceMetricsHandle, ProjectTraceMetricsProps>(
  function ProjectTraceMetrics(
    { project, sessionToken, onProjectUpdate },
    ref
  ) {
    const theme = useTheme();
    const [metrics, setMetrics] = useState<MetricDetail[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [metricsDialogOpen, setMetricsDialogOpen] = useState(false);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
    const [deleting, setDeleting] = useState(false);
    const notifications = useNotifications();

    useImperativeHandle(ref, () => ({
      openAddDialog: () => setMetricsDialogOpen(true),
    }));

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
        const currentMetricIds = getTraceMetricIds(project);
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

    const deleteTargetMetric = useMemo(
      () => metrics.find(metric => metric.id === deleteTargetId) ?? null,
      [deleteTargetId, metrics]
    );

    const handleDeleteRow = useCallback((metricId: string) => {
      setDeleteTargetId(metricId);
      setDeleteDialogOpen(true);
    }, []);

    const handleConfirmRemove = async () => {
      if (!deleteTargetId) return;

      try {
        setDeleting(true);
        const currentMetricIds = getTraceMetricIds(project);
        const newMetricIds = currentMetricIds.filter(
          (id: string) => id !== deleteTargetId
        );

        const updatedAttributes = {
          ...(project.attributes || {}),
          trace_metrics: newMetricIds,
        };

        await onProjectUpdate({ attributes: updatedAttributes });
        notifications.show('Metric removed from project successfully', {
          severity: 'success',
        });
        setDeleteDialogOpen(false);
        setDeleteTargetId(null);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'An error occurred';
        notifications.show(`Failed to remove metric: ${errorMessage}`, {
          severity: 'error',
        });
      } finally {
        setDeleting(false);
      }
    };

    const displayedRows = useMemo(() => {
      const query = searchQuery.trim().toLowerCase();
      if (!query) return metrics;

      return metrics.filter(metric => {
        return (
          metric.name.toLowerCase().includes(query) ||
          metric.score_type.toLowerCase().includes(query) ||
          (metric.description ?? '').toLowerCase().includes(query)
        );
      });
    }, [metrics, searchQuery]);

    const excludeMetricIds = metrics.map(m => m.id as UUID);

    const columns: GridColDef<MetricDetail>[] = useMemo(
      () => [
        {
          field: 'name',
          headerName: 'Name',
          flex: 1.5,
          minWidth: 200,
          sortable: false,
          renderCell: (params: GridRenderCellParams<MetricDetail>) => (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                height: '100%',
              }}
            >
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
          headerName: 'Type',
          flex: 1,
          minWidth: 120,
          sortable: false,
          renderCell: (params: GridRenderCellParams<MetricDetail>) => (
            <GridBadge
              label={
                params.row.score_type.charAt(0).toUpperCase() +
                params.row.score_type.slice(1)
              }
            />
          ),
        },
        {
          field: 'actions',
          headerName: '',
          width: 80,
          sortable: false,
          filterable: false,
          disableColumnMenu: true,
          align: 'center',
          headerAlign: 'center',
          renderCell: (params: GridRenderCellParams<MetricDetail>) => (
            <Box
              className={ROW_ACTIONS_CLASS}
              sx={{
                display: 'flex',
                gap: '4px',
                justifyContent: 'center',
                alignItems: 'center',
                width: '100%',
              }}
            >
              <Tooltip title="Remove metric">
                <IconButton
                  size="small"
                  onClick={e => {
                    e.stopPropagation();
                    handleDeleteRow(params.row.id as string);
                  }}
                  sx={{
                    p: 0.5,
                    color: 'text.secondary',
                    '&:hover': {
                      color: 'error.main',
                      bgcolor: alpha(theme.palette.error.main, 0.08),
                    },
                  }}
                  aria-label={`Remove metric ${params.row.name}`}
                >
                  <DeleteIcon sx={{ fontSize: 18 }} />
                </IconButton>
              </Tooltip>
            </Box>
          ),
        },
      ],
      [handleDeleteRow, theme]
    );

    if (loading) {
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', p: 2, gap: 2 }}>
          <CircularProgress size={20} />
          <Typography color="text.secondary">Loading metrics...</Typography>
        </Box>
      );
    }

    if (error) {
      return <Alert severity="error">{error}</Alert>;
    }

    return (
      <TraceMetricsToolbarContext.Provider
        value={{ searchQuery, setSearchQuery }}
      >
        <Box>
          {metrics.length === 0 ? (
            <SectionEmptyState
              icon={AutoGraphIcon}
              title="No trace metrics yet"
              description="Add metrics to evaluate traces automatically."
            />
          ) : (
            <Box
              sx={
                [sectionCardGridBleedSx, rowActionsHoverSx].filter(
                  Boolean
                ) as SxProps<Theme>
              }
            >
              <BaseDataGrid
                rows={displayedRows}
                columns={columns}
                getRowId={row => row.id}
                loading={loading}
                toolbarSlot={TraceMetricsToolbar}
                showToolbar
                disablePaperWrapper
                pageSizeOptions={[10, 25, 50]}
                initialState={{
                  pagination: {
                    paginationModel: { page: 0, pageSize: 10 },
                  },
                }}
                sx={linkedDataGridRowSx}
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
            variant="drawer"
          />

          <DeleteModal
            open={deleteDialogOpen}
            onClose={() => {
              setDeleteDialogOpen(false);
              setDeleteTargetId(null);
            }}
            onConfirm={handleConfirmRemove}
            isLoading={deleting}
            title="Remove metric"
            message={
              <>
                <Typography sx={{ mb: 1.5 }}>
                  Remove &ldquo;{deleteTargetMetric?.name ?? 'this metric'}
                  &rdquo;?
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  The metric itself will not be deleted — it will only be
                  removed from this project&apos;s trace evaluation.
                </Typography>
              </>
            }
            confirmButtonText="Remove"
            itemType="metric"
          />
        </Box>
      </TraceMetricsToolbarContext.Provider>
    );
  }
);
