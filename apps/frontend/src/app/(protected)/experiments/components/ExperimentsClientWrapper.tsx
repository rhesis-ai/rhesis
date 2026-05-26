'use client';

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Box, Button, Chip, Paper, Typography } from '@mui/material';
import {
  GridColDef,
  GridFilterModel,
  GridPaginationModel,
  GridRowSelectionModel,
} from '@mui/x-data-grid';
import { useRouter } from 'next/navigation';
import { PageContainer } from '@toolpad/core/PageContainer';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentRead,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { Project } from '@/utils/api-client/interfaces/project';
import { AddIcon, DeleteIcon, BiotechIcon } from '@/components/icons';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { combineExperimentFiltersToOData } from '@/utils/odata-filter';
import CreateExperimentDialog from './CreateExperimentDialog';
import { formatDate } from '@/utils/date';

interface ExperimentsClientWrapperProps {
  sessionToken: string;
}

export default function ExperimentsClientWrapper({
  sessionToken,
}: ExperimentsClientWrapperProps) {
  const isMounted = useRef(false);
  const router = useRouter();
  const notifications = useNotifications();

  const [projects, setProjects] = useState<Project[]>([]);
  const [experiments, setExperiments] = useState<ExperimentRead[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 25,
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const initialLoadDone = useRef(false);

  const fetchExperiments = useCallback(
    async (skip: number, limit: number) => {
      if (!sessionToken) return;

      try {
        // Only show loading overlay on the first load
        if (!initialLoadDone.current && isMounted.current) {
          setLoading(true);
        }

        const parametersClient = apiFactory.getParametersClient();
        const filterString = combineExperimentFiltersToOData(filterModel);

        const { data, totalCount: count } =
          await parametersClient.listExperiments({
            skip,
            limit,
            sort_by: 'created_at',
            sort_order: 'desc',
            ...(filterString && { filter: filterString }),
          });

        if (isMounted.current) {
          setExperiments(data);
          setTotalCount(count);
          initialLoadDone.current = true;
        }
      } catch {
        if (isMounted.current) {
          notifications.show('Failed to load experiments', {
            severity: 'error',
          });
          setExperiments([]);
        }
      } finally {
        if (isMounted.current) setLoading(false);
      }
    },
    [sessionToken, apiFactory, filterModel, notifications]
  );

  // Load projects for the create drawer
  useEffect(() => {
    if (!sessionToken) return;
    const projectsClient = apiFactory.getProjectsClient();
    projectsClient
      .getAllProjects({ sort_by: 'name', sort_order: 'asc' })
      .then(p => setProjects(p))
      .catch(() => {});
  }, [sessionToken, apiFactory]);

  useEffect(() => {
    isMounted.current = true;

    const skip = paginationModel.page * paginationModel.pageSize;
    fetchExperiments(skip, paginationModel.pageSize);

    return () => {
      isMounted.current = false;
    };
  }, [paginationModel, fetchExperiments]);

  const handleFilterModelChange = useCallback(
    (newFilterModel: GridFilterModel) => {
      setFilterModel(newFilterModel);
      setPaginationModel(prev => ({ ...prev, page: 0 }));
    },
    []
  );

  const handleDeleteExperiments = async () => {
    setDeleting(true);
    try {
      const parametersClient = apiFactory.getParametersClient();
      const ids = selectedRows as string[];
      await Promise.all(ids.map(id => parametersClient.deleteExperiment(id)));
      notifications.show(
        `Deleted ${ids.length} experiment${ids.length > 1 ? 's' : ''}`,
        { severity: 'success' }
      );
      setSelectedRows([]);
      setDeleteDialogOpen(false);
      const skip = paginationModel.page * paginationModel.pageSize;
      fetchExperiments(skip, paginationModel.pageSize);
    } catch {
      notifications.show('Failed to delete experiments', {
        severity: 'error',
      });
    } finally {
      setDeleting(false);
    }
  };

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1.5,
        minWidth: 200,
        filterable: true,
        renderCell: params => (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <BiotechIcon fontSize="small" color="action" />
            <Typography variant="body2">{params.row.name}</Typography>
          </Box>
        ),
      },
      {
        field: 'projectName',
        headerName: 'Project',
        flex: 1,
        minWidth: 140,
        filterable: true,
        valueGetter: (_value: unknown, row: ExperimentRead) =>
          row.project_name || '—',
      },
      {
        field: 'visibility',
        headerName: 'Visibility',
        flex: 0.6,
        minWidth: 100,
        filterable: true,
        type: 'singleSelect',
        valueOptions: ['private', 'shared'],
        renderCell: params => (
          <Chip
            size="small"
            label={params.value}
            color={params.value === 'shared' ? 'primary' : 'default'}
            variant="outlined"
          />
        ),
      },
      {
        field: 'versions_count',
        headerName: 'Versions',
        flex: 0.5,
        minWidth: 80,
        align: 'right',
        headerAlign: 'right',
        filterable: false,
      },
      {
        field: 'latest_version',
        headerName: 'Latest',
        flex: 0.6,
        minWidth: 100,
        filterable: false,
        sortable: false,
        renderCell: params =>
          params.value ? (
            <Chip
              size="small"
              label={shortVersion(params.value)}
              sx={{ fontFamily: 'monospace' }}
            />
          ) : (
            <Typography variant="caption" color="text.secondary">
              (no versions)
            </Typography>
          ),
      },
      {
        field: 'created_at',
        headerName: 'Created',
        flex: 0.8,
        minWidth: 120,
        filterable: false,
        renderCell: params => (
          <Typography variant="body2" color="text.secondary">
            {params.value ? formatDate(params.value) : '—'}
          </Typography>
        ),
      },
    ],
    []
  );

  const actionButtons = useMemo(() => {
    const buttons: {
      label: string;
      icon: React.ReactNode;
      variant: 'text' | 'outlined' | 'contained';
      color?:
        | 'inherit'
        | 'primary'
        | 'secondary'
        | 'success'
        | 'error'
        | 'info'
        | 'warning';
      onClick: () => void;
      disabled?: boolean;
    }[] = [
      {
        label: 'New Experiment',
        icon: <AddIcon />,
        variant: 'contained',
        onClick: () => setCreateOpen(true),
        disabled: projects.length === 0,
      },
    ];

    if (selectedRows.length > 0) {
      buttons.push({
        label: `Delete (${selectedRows.length})`,
        icon: <DeleteIcon />,
        variant: 'outlined',
        color: 'error',
        onClick: () => setDeleteDialogOpen(true),
      });
    }

    return buttons;
  }, [projects.length, selectedRows.length]);

  return (
    <PageContainer title="Experiments" breadcrumbs={[]}>
      <Box sx={{ mb: 3 }}>
        <Typography color="text.secondary">
          Experiments are named bundles of parameter values that can be pinned
          to test runs, ensuring reproducible and comparable executions across
          your project.
        </Typography>
      </Box>
      {!loading && experiments.length === 0 && !filterModel.items.length ? (
        <Paper
          elevation={2}
          sx={{
            p: theme => theme.spacing(6),
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
          }}
        >
          <BiotechIcon
            sx={{
              fontSize: theme => theme.spacing(8),
              color: 'text.disabled',
              mb: 2,
            }}
          />
          <Typography variant="h6" gutterBottom>
            No experiments yet
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ maxWidth: theme => theme.spacing(58), mb: 3 }}
          >
            Experiments let you bundle parameter values into versioned
            configurations. Create one to start tracking how different settings
            affect your test results.
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
            disabled={projects.length === 0}
          >
            New Experiment
          </Button>
        </Paper>
      ) : (
        <Paper elevation={2} sx={{ p: 2 }}>
          <BaseDataGrid
            rows={experiments}
            columns={columns}
            loading={loading}
            density="comfortable"
            actionButtons={actionButtons}
            linkPath="/experiments"
            linkField="id"
            paginationModel={paginationModel}
            onPaginationModelChange={setPaginationModel}
            filterModel={filterModel}
            onFilterModelChange={handleFilterModelChange}
            serverSideFiltering={true}
            serverSidePagination={true}
            totalRows={totalCount}
            pageSizeOptions={[10, 25, 50]}
            checkboxSelection
            disableRowSelectionOnClick
            rowSelectionModel={selectedRows}
            onRowSelectionModelChange={setSelectedRows}
            disablePaperWrapper
            persistState
            initialState={{
              columns: {
                columnVisibilityModel: {
                  versions_count: false,
                },
              },
            }}
          />
        </Paper>
      )}

      <CreateExperimentDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        sessionToken={sessionToken}
        projects={projects}
        defaultProjectId={undefined}
        onCreated={async experiment => {
          setCreateOpen(false);
          router.push(`/experiments/${experiment.id}`);
        }}
      />

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleDeleteExperiments}
        isLoading={deleting}
        title={`Delete Experiment${selectedRows.length > 1 ? 's' : ''}`}
        message={`Are you sure you want to delete ${selectedRows.length} experiment${selectedRows.length > 1 ? 's' : ''}? This action cannot be undone.`}
        itemType="experiments"
      />
    </PageContainer>
  );
}
