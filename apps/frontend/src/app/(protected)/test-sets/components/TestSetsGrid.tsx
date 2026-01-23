'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  GridColDef,
  GridRowSelectionModel,
  GridPaginationModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Tag } from '@/utils/api-client/interfaces/tag';
import {
  Box,
  Chip,
  Tooltip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  Typography,
  Avatar,
} from '@mui/material';
import { ChatIcon, DescriptionIcon } from '@/components/icons';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useSession } from 'next-auth/react';
import AddIcon from '@mui/icons-material/Add';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DeleteIcon from '@mui/icons-material/Delete';
import PersonIcon from '@mui/icons-material/Person';
import SecurityIcon from '@mui/icons-material/Security';
import TestSetDrawer from './TestSetDrawer';
import TestRunDrawer from './TestRunDrawer';
import GarakImportDialog from './GarakImportDialog';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';

interface TestSetsGridProps {
  testSets: TestSet[];
  loading: boolean;
  sessionToken?: string;
  initialTotalCount?: number;
}

const ChipContainer = ({ items }: { items: string[] }) => {
  if (items.length === 0) return '-';

  // Simple approach: show first 2-3 chips and overflow
  const maxVisible = 3;
  const visibleItems = items.slice(0, maxVisible);
  const remainingCount = items.length - maxVisible;

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 0.5,
        alignItems: 'center',
        width: '100%',
        overflow: 'hidden',
      }}
    >
      {visibleItems.map((item: string) => (
        <Chip key={item} label={item} size="small" variant="outlined" />
      ))}
      {remainingCount > 0 && (
        <Tooltip title={items.slice(maxVisible).join(', ')} arrow>
          <Chip label={`+${remainingCount}`} size="small" variant="outlined" />
        </Tooltip>
      )}
    </Box>
  );
};

export default function TestSetsGrid({
  testSets: initialTestSets,
  loading: initialLoading,
  sessionToken,
  initialTotalCount,
}: TestSetsGridProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const [filteredTestSets, setFilteredTestSets] =
    useState<TestSet[]>(initialTestSets);
  const [loading, setLoading] = useState(initialLoading);
  const [testSets, setTestSets] = useState<TestSet[]>(initialTestSets);
  const [totalCount, setTotalCount] = useState<number>(
    initialTotalCount || initialTestSets.length
  );
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [testRunDrawerOpen, setTestRunDrawerOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [garakImportDialogOpen, setGarakImportDialogOpen] = useState(false);
  const notifications = useNotifications();

  // Set initial data from props
  useEffect(() => {
    if (initialTestSets.length > 0) {
      setTestSets(initialTestSets);
      setTotalCount(initialTotalCount || initialTestSets.length);
    }
  }, [initialTestSets, initialTotalCount]);

  const fetchTestSets = useCallback(async () => {
    if (!sessionToken && !session?.session_token) return;

    try {
      setLoading(true);

      const token = sessionToken || session?.session_token;
      const clientFactory = new ApiClientFactory(token!);
      const testSetsClient = clientFactory.getTestSetsClient();

      const skip = paginationModel.page * paginationModel.pageSize;
      const limit = paginationModel.pageSize;

      const apiParams = {
        skip,
        limit,
        sort_by: 'created_at',
        sort_order: 'desc' as const,
      };

      const response = await testSetsClient.getTestSets(apiParams);

      setTestSets(response.data);
      setTotalCount(response.pagination.totalCount);
    } catch (error) {
    } finally {
      setLoading(false);
    }
  }, [sessionToken, session, paginationModel]);

  useEffect(() => {
    // Always fetch when pagination changes
    fetchTestSets();
  }, [fetchTestSets, paginationModel.page, paginationModel.pageSize]);

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  // Process test sets for display
  const processedTestSets = testSets.map(testSet => {
    return {
      id: testSet.id,
      name: testSet.name,
      testSetType: testSet.test_set_type?.type_value || 'Unknown',
      behaviors: testSet.attributes?.metadata?.behaviors || [],
      categories: testSet.attributes?.metadata?.categories || [],
      totalTests: testSet.attributes?.metadata?.total_tests || 0,
      creator: testSet.user,
      counts: testSet.counts,
      sources: testSet.attributes?.metadata?.sources || [],
      tags: testSet.tags || [],
    };
  });

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1.5,
    },
    {
      field: 'behaviors',
      headerName: 'Behaviors',
      flex: 1.0,
      renderCell: params => (
        <ChipContainer items={params.row.behaviors || []} />
      ),
    },
    {
      field: 'categories',
      headerName: 'Categories',
      flex: 1.0,
      renderCell: params => (
        <ChipContainer items={params.row.categories || []} />
      ),
    },
    {
      field: 'testSetType',
      headerName: 'Type',
      flex: 0.75,
      renderCell: params => (
        <Chip label={params.value} size="small" variant="outlined" />
      ),
    },
    {
      field: 'totalTests',
      headerName: 'Tests',
      flex: 0.5,
      valueGetter: (_, row) => row.totalTests,
    },
    {
      field: 'creator',
      headerName: 'Creator',
      flex: 0.75,
      sortable: true,
      valueGetter: (_, row) =>
        row.creator?.name ||
        `${row.creator?.given_name || ''} ${row.creator?.family_name || ''}`.trim() ||
        row.creator?.email ||
        '',
      renderCell: params => {
        const creator = params.row.creator;
        if (!creator) return '-';

        const displayName =
          creator.name ||
          `${creator.given_name || ''} ${creator.family_name || ''}`.trim() ||
          creator.email;

        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Avatar src={creator.picture} sx={{ width: 24, height: 24 }}>
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
      field: 'sources',
      headerName: 'Sources',
      width: 80,
      sortable: false,
      filterable: false,
      align: 'center',
      headerAlign: 'center',
      renderCell: params => {
        const sources = params.row.sources;
        const count = sources?.length || 0;
        if (count === 0) return null;
        return (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 0.5,
            }}
          >
            <InsertDriveFileOutlined
              sx={{ fontSize: 16, color: 'text.secondary' }}
            />
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
      renderCell: params => {
        const testSet = params.row;
        if (!testSet.tags || testSet.tags.length === 0) {
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
            {testSet.tags
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
            {testSet.tags.filter((tag: Tag) => tag && tag.id && tag.name)
              .length > 2 && (
              <Chip
                label={`+${testSet.tags.filter((tag: Tag) => tag && tag.id && tag.name).length - 2}`}
                size="small"
                variant="outlined"
              />
            )}
          </Box>
        );
      },
    },
  ];

  const handleRowClick = (params: any) => {
    router.push(`/test-sets/${params.id}`);
  };

  const handleNewTestSet = () => {
    setDrawerOpen(true);
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
  };

  const handleTestSetSaved = async () => {
    fetchTestSets();
  };

  const handleSelectionChange = (newSelection: GridRowSelectionModel) => {
    setSelectedRows(newSelection);
  };

  const handleRunTestSets = () => {
    setTestRunDrawerOpen(true);
  };

  const handleTestRunSuccess = () => {
    setTestRunDrawerOpen(false);
    // Optionally refresh the test sets list if needed
  };

  const handleDeleteTestSets = () => {
    setDeleteModalOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (selectedRows.length === 0) return;

    try {
      setIsDeleting(true);
      const token = sessionToken || session?.session_token;
      const clientFactory = new ApiClientFactory(token!);
      const testSetsClient = clientFactory.getTestSetsClient();

      // Delete all selected test sets
      await Promise.all(
        selectedRows.map(id => testSetsClient.deleteTestSet(id as string))
      );

      // Show success notification
      notifications.show(
        `Successfully deleted ${selectedRows.length} ${selectedRows.length === 1 ? 'test set' : 'test sets'}`,
        { severity: 'success', autoHideDuration: 4000 }
      );

      // Clear selection and refresh data
      setSelectedRows([]);
      fetchTestSets();
    } catch (error) {
      notifications.show('Failed to delete test sets', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteModalOpen(false);
  };

  const handleGarakImportSuccess = (testSetId: string) => {
    fetchTestSets();
    notifications.show('Garak probes imported successfully', {
      severity: 'success',
      autoHideDuration: 6000,
    });
    // Navigate to the new test set
    router.push(`/test-sets/${testSetId}`);
  };

  const getActionButtons = () => {
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
    }[] = [
      {
        label: 'New Test Set',
        icon: <AddIcon />,
        variant: 'contained' as const,
        onClick: handleNewTestSet,
      },
      {
        label: 'Import from Garak',
        icon: <SecurityIcon />,
        variant: 'outlined' as const,
        onClick: () => setGarakImportDialogOpen(true),
      },
    ];

    if (selectedRows.length > 0) {
      buttons.push({
        label: selectedRows.length > 1 ? 'Run Test Sets' : 'Run Test Set',
        icon: <PlayArrowIcon />,
        variant: 'contained' as const,
        onClick: handleRunTestSets,
      });

      buttons.push({
        label: 'Delete Test Sets',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteTestSets,
      });
    }

    return buttons;
  };

  return (
    <>
      {selectedRows.length > 0 && (
        <Box
          sx={{
            mb: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Typography variant="subtitle1" color="primary">
            {selectedRows.length} test sets selected
          </Typography>
        </Box>
      )}

      <BaseDataGrid
        columns={columns}
        rows={processedTestSets}
        loading={loading}
        getRowId={row => row.id}
        showToolbar={false}
        onRowClick={handleRowClick}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
        actionButtons={getActionButtons()}
        checkboxSelection
        disableRowSelectionOnClick
        onRowSelectionModelChange={handleSelectionChange}
        rowSelectionModel={selectedRows}
        serverSidePagination={true}
        totalRows={totalCount}
        pageSizeOptions={[10, 25, 50]}
        disablePaperWrapper={true}
        persistState
        initialState={{
          columns: {
            columnVisibilityModel: {
              sources: false,
            },
          },
        }}
      />

      {(sessionToken || session?.session_token) && (
        <>
          <TestSetDrawer
            open={drawerOpen}
            onClose={handleDrawerClose}
            sessionToken={sessionToken || session?.session_token || ''}
            onSuccess={handleTestSetSaved}
          />
          <TestRunDrawer
            open={testRunDrawerOpen}
            onClose={() => setTestRunDrawerOpen(false)}
            sessionToken={sessionToken || session?.session_token || ''}
            selectedTestSetIds={selectedRows as string[]}
            onSuccess={handleTestRunSuccess}
          />
          <GarakImportDialog
            open={garakImportDialogOpen}
            onClose={() => setGarakImportDialogOpen(false)}
            sessionToken={sessionToken || session?.session_token || ''}
            onSuccess={handleGarakImportSuccess}
          />
          <DeleteModal
            open={deleteModalOpen}
            onClose={handleDeleteCancel}
            onConfirm={handleDeleteConfirm}
            isLoading={isDeleting}
            title="Delete Test Sets"
            message={`Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'test set' : 'test sets'}? Don't worry, related data will not be deleted, only ${selectedRows.length === 1 ? 'this record' : 'these records'}.`}
            itemType="test sets"
          />
        </>
      )}
    </>
  );
}
