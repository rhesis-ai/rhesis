'use client';

import React, {
  useEffect,
  useState,
  useCallback,
  useRef,
  useMemo,
} from 'react';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import {
  getTestRunStatusColor,
  getTestRunStatusIcon,
} from '@/components/common/TestRunStatus';
import {
  GridColDef,
  GridRowSelectionModel,
  GridPaginationModel,
  GridFilterModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { Typography, Box, Alert, Avatar, Chip } from '@mui/material';
import { ChatIcon, DescriptionIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import PersonIcon from '@mui/icons-material/Person';
import { useNotifications } from '@/components/common/NotificationContext';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Tag } from '@/utils/api-client/interfaces/tag';
import TestRunDrawer from './TestRunDrawer';
import { DeleteModal } from '@/components/common/DeleteModal';
import { combineTestRunFiltersToOData } from '@/utils/odata-filter';

interface ProjectCache {
  [key: string]: string;
}

interface TestRunsTableProps {
  sessionToken: string;
  onRefresh?: () => void;
  onTotalCountChange?: (count: number) => void;
}

function TestRunsTable({
  sessionToken,
  onRefresh,
  onTotalCountChange,
}: TestRunsTableProps) {
  const isMounted = useRef(false);
  const router = useRouter();
  const notifications = useNotifications();
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [testRuns, setTestRuns] = useState<TestRunDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [projectNames, setProjectNames] = useState<ProjectCache>({});
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 50,
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });

  const fetchTestRuns = useCallback(
    async (skip: number, limit: number) => {
      if (!sessionToken) return;

      try {
        if (isMounted.current) {
          setLoading(true);
        }

        const clientFactory = new ApiClientFactory(sessionToken);
        const testRunsClient = clientFactory.getTestRunsClient();

        // Convert filter model to OData filter string (handles both column filters and quick search)
        const filterString = combineTestRunFiltersToOData(filterModel);

        const apiParams = {
          skip,
          limit,
          sort_by: 'created_at',
          sort_order: 'desc' as const,
          ...(filterString && { filter: filterString }),
        };

        const response = await testRunsClient.getTestRuns(apiParams);

        if (isMounted.current) {
          setTestRuns(response.data);
          setTotalCount(response.pagination.totalCount);
          onTotalCountChange?.(response.pagination.totalCount);
          setError(null);

          // Fetch project names for new test runs in batch to avoid multiple state updates
          const projectIds = response.data
            .map(run => run.test_configuration?.endpoint?.project_id)
            .filter((id): id is string => !!id);

          const uniqueProjectIds = [...new Set(projectIds)];

          if (uniqueProjectIds.length > 0) {
            // Use functional update to check cache and fetch only uncached projects
            // This avoids circular dependency on projectNames
            setProjectNames(prev => {
              const uncachedProjectIds = uniqueProjectIds.filter(
                id => !prev[id]
              );

              if (uncachedProjectIds.length > 0) {
                // Fetch all uncached project names in parallel
                Promise.all(
                  uncachedProjectIds.map(async projectId => {
                    try {
                      const clientFactory = new ApiClientFactory(sessionToken);
                      const projectsClient = clientFactory.getProjectsClient();
                      const project =
                        await projectsClient.getProject(projectId);
                      return { projectId, name: project.name };
                    } catch (_err) {
                      return null;
                    }
                  })
                ).then(results => {
                  if (isMounted.current) {
                    const newProjects = results
                      .filter(
                        (
                          result
                        ): result is { projectId: string; name: string } =>
                          result !== null
                      )
                      .reduce(
                        (acc, { projectId, name }) => {
                          acc[projectId] = name;
                          return acc;
                        },
                        {} as Record<string, string>
                      );

                    if (Object.keys(newProjects).length > 0) {
                      setProjectNames(current => ({
                        ...current,
                        ...newProjects,
                      }));
                    }
                  }
                });
              }

              // Return current state unchanged (actual update happens in Promise.then)
              return prev;
            });
          }
        }
      } catch (_error) {
        if (isMounted.current) {
          setError('Failed to load test runs');
          setTestRuns([]);
        }
      } finally {
        if (isMounted.current) {
          setLoading(false);
        }
      }
    },
    [sessionToken, filterModel, onTotalCountChange]
  );

  useEffect(() => {
    isMounted.current = true;

    const loadData = async () => {
      if (!sessionToken) return;

      const skip = paginationModel.page * paginationModel.pageSize;
      await fetchTestRuns(skip, paginationModel.pageSize);
    };

    loadData();

    return () => {
      isMounted.current = false;
    };
  }, [sessionToken, paginationModel, fetchTestRuns]);

  // Memoized helper function to format execution time in a user-friendly way
  const formatExecutionTime = useMemo(
    () =>
      (timeMs: number): string => {
        const seconds = timeMs / 1000;

        if (seconds < 60) {
          return `${Math.round(seconds)}s`;
        } else if (seconds < 3600) {
          // Less than 1 hour
          const minutes = seconds / 60;
          return `${Math.round(minutes * 10) / 10}m`; // Round to 1 decimal place
        } else {
          const hours = seconds / 3600;
          return `${Math.round(hours * 10) / 10}h`; // Round to 1 decimal place
        }
      },
    []
  );

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1,
        filterable: true,
        valueGetter: (_, row) => row.name || '',
      },
      {
        field: 'test_configuration.test_set.name',
        headerName: 'Test Sets',
        flex: 1,
        filterable: true,
        valueGetter: (_, row) => {
          const testSet = row.test_configuration?.test_set;
          return testSet?.name || '';
        },
      },
      {
        field: 'total_tests',
        headerName: 'Total Tests',
        flex: 1,
        align: 'right',
        headerAlign: 'right',
        valueGetter: (_, row) => {
          const attributes = row?.attributes;
          return attributes?.total_tests || 0;
        },
      },
      {
        field: 'test_set_type',
        headerName: 'Type',
        flex: 1,
        filterable: true,
        valueGetter: (_, row) => {
          return (
            row.test_configuration?.test_set?.test_set_type?.type_value || ''
          );
        },
        renderCell: params => {
          const testSetType =
            params.row.test_configuration?.test_set?.test_set_type?.type_value;

          if (!testSetType) return null;

          return (
            <Chip
              label={testSetType}
              size="small"
              variant="outlined"
              sx={{ fontWeight: 500 }}
            />
          );
        },
      },
      {
        field: 'status',
        headerName: 'Status',
        flex: 1,
        renderCell: params => {
          const status = params.row.status?.name;
          if (!status) return null;

          const color = getTestRunStatusColor(status);
          const icon = getTestRunStatusIcon(status, 'small');

          return (
            <Chip
              label={status}
              size="small"
              color={color}
              icon={icon}
              sx={{ fontWeight: 500 }}
            />
          );
        },
      },
      {
        field: 'user.name',
        headerName: 'Executor',
        flex: 1,
        filterable: true,
        valueGetter: (_, row) => {
          const executor = row.user;
          if (!executor) return '';
          return (
            executor.name ||
            `${executor.given_name || ''} ${executor.family_name || ''}`.trim() ||
            executor.email
          );
        },
        renderCell: params => {
          const executor = params.row.user;
          if (!executor) return null;

          const displayName =
            executor.name ||
            `${executor.given_name || ''} ${executor.family_name || ''}`.trim() ||
            executor.email;

          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Avatar src={executor.picture} sx={{ width: 24, height: 24 }}>
                <PersonIcon />
              </Avatar>
              <Typography variant="body2">{displayName}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'counts.comments',
        headerName: 'Comments',
        width: 100,
        sortable: false,
        filterable: false,
        renderCell: params => {
          const count = params.row.counts?.comments || 0;
          if (count === 0) return null;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <ChatIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
              <Typography variant="body2">{count}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'counts.tasks',
        headerName: 'Tasks',
        width: 100,
        sortable: false,
        filterable: false,
        renderCell: params => {
          const count = params.row.counts?.tasks || 0;
          if (count === 0) return null;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <DescriptionIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
              <Typography variant="body2">{count}</Typography>
            </Box>
          );
        },
      },
      {
        field: 'tags',
        headerName: 'Tags',
        flex: 1.5,
        minWidth: 140,
        sortable: false,
        filterable: true,
        valueGetter: (_, row) => {
          if (!row.tags || !Array.isArray(row.tags)) {
            return '';
          }
          // Return comma-separated tag names for filtering
          return row.tags
            .filter((tag: Tag) => tag && tag.name)
            .map((tag: Tag) => tag.name)
            .join(', ');
        },
        renderCell: params => {
          const testRun = params.row as TestRunDetail;
          if (!testRun.tags || testRun.tags.length === 0) {
            return null;
          }

          return (
            <Box
              sx={{
                display: 'flex',
                gap: 0.5,
                flexWrap: 'nowrap',
                overflow: 'hidden',
              }}
            >
              {testRun.tags
                .filter((tag: Tag) => tag && tag.id && tag.name)
                .slice(0, 2)
                .map((tag: Tag) => (
                  <Chip
                    key={tag.id}
                    label={tag.name}
                    size="small"
                    variant="outlined"
                  />
                ))}
              {testRun.tags.filter((tag: Tag) => tag && tag.id && tag.name)
                .length > 2 && (
                <Chip
                  label={`+${testRun.tags.filter((tag: Tag) => tag && tag.id && tag.name).length - 2}`}
                  size="small"
                  variant="outlined"
                />
              )}
            </Box>
          );
        },
      },
    ],
    [formatExecutionTime]
  );

  // Handle row click to navigate to test run details
  const handleRowClick = useCallback(
    (params: any) => {
      const testRunId = params.id;
      router.push(`/test-runs/${testRunId}`);
    },
    [router]
  );

  // Handle row selection change
  const handleSelectionChange = useCallback(
    (newSelection: GridRowSelectionModel) => {
      setSelectedRows(newSelection);
    },
    []
  );

  // Handle new test run
  const handleCreateTestRun = useCallback(() => {
    setIsDrawerOpen(true);
  }, []);

  const handleDrawerClose = useCallback(() => {
    setIsDrawerOpen(false);
  }, []);

  const handleDrawerSuccess = useCallback(() => {
    const skip = paginationModel.page * paginationModel.pageSize;
    fetchTestRuns(skip, paginationModel.pageSize);
    onRefresh?.();
  }, [fetchTestRuns, onRefresh, paginationModel]);

  // Stable pagination handler
  const handlePaginationModelChange = useCallback(
    (model: GridPaginationModel) => {
      setPaginationModel(model);
      const skip = model.page * model.pageSize;
      fetchTestRuns(skip, model.pageSize);
    },
    [fetchTestRuns]
  );

  // Handle delete selected test runs - opens confirmation modal
  const handleDeleteSelected = useCallback(() => {
    const validSelectedRows = Array.isArray(selectedRows) ? selectedRows : [];
    if (validSelectedRows.length === 0) return;
    setDeleteModalOpen(true);
  }, [selectedRows]);

  // Confirm deletion and perform the actual delete
  const handleDeleteConfirm = useCallback(async () => {
    const validSelectedRows = Array.isArray(selectedRows) ? selectedRows : [];
    if (validSelectedRows.length === 0) return;

    try {
      setIsDeleting(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testRunsClient = clientFactory.getTestRunsClient();

      await Promise.all(
        validSelectedRows.map(id => testRunsClient.deleteTestRun(id.toString()))
      );

      notifications.show(
        `Successfully deleted ${validSelectedRows.length} test run${validSelectedRows.length === 1 ? '' : 's'}`,
        { severity: 'success' }
      );

      // Refresh the data
      const skip = paginationModel.page * paginationModel.pageSize;
      await fetchTestRuns(skip, paginationModel.pageSize);

      // Clear selection
      setSelectedRows([]);
    } catch (_error) {
      notifications.show('Failed to delete test runs', { severity: 'error' });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  }, [
    selectedRows,
    sessionToken,
    notifications,
    paginationModel,
    fetchTestRuns,
  ]);

  // Cancel deletion
  const handleDeleteCancel = useCallback(() => {
    setDeleteModalOpen(false);
  }, []);

  // Filter change handler
  const handleFilterModelChange = useCallback(
    (newFilterModel: GridFilterModel) => {
      setFilterModel(newFilterModel);
      // Reset to first page when filter changes
      setPaginationModel(prev => ({ ...prev, page: 0 }));
    },
    []
  );

  // Memoized action buttons based on selection
  const actionButtons = useMemo(() => {
    const buttons = [];
    const validSelectedRows = Array.isArray(selectedRows) ? selectedRows : [];

    buttons.push({
      label: 'New Test Run',
      icon: <AddIcon />,
      variant: 'contained' as const,
      onClick: handleCreateTestRun,
    });

    if (validSelectedRows.length > 0) {
      buttons.push({
        label: 'Delete Test Runs',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteSelected,
      });
    }

    return buttons;
  }, [selectedRows, handleCreateTestRun, handleDeleteSelected]);

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {Array.isArray(selectedRows) && selectedRows.length > 0 && (
        <Box
          sx={{
            mb: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Typography variant="subtitle1" color="primary">
            {selectedRows.length} test runs selected
          </Typography>
        </Box>
      )}

      <BaseDataGrid
        rows={testRuns}
        columns={columns}
        loading={loading}
        getRowId={row => row.id}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        filterModel={filterModel}
        onFilterModelChange={handleFilterModelChange}
        serverSideFiltering={true}
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={Array.isArray(selectedRows) ? selectedRows : []}
        onRowClick={handleRowClick}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        checkboxSelection
        disableRowSelectionOnClick
        actionButtons={actionButtons}
        disablePaperWrapper={true}
        persistState
      />

      <TestRunDrawer
        open={isDrawerOpen}
        onClose={handleDrawerClose}
        sessionToken={sessionToken}
        onSuccess={handleDrawerSuccess}
      />

      <DeleteModal
        open={deleteModalOpen}
        onClose={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        title="Delete Test Runs"
        message={`Are you sure you want to delete ${Array.isArray(selectedRows) ? selectedRows.length : 0} test run${Array.isArray(selectedRows) && selectedRows.length === 1 ? '' : 's'}? Don't worry, related data will not be deleted, only ${Array.isArray(selectedRows) && selectedRows.length === 1 ? 'this record' : 'these records'}.`}
        itemType="test runs"
      />
    </>
  );
}

// Export memoized component to prevent unnecessary re-renders
export default React.memo(TestRunsTable);
