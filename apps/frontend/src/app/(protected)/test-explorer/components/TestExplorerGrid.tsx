'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  GridColDef,
  GridRowSelectionModel,
  GridPaginationModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Box, Typography, Avatar } from '@mui/material';
import InsertDriveFileOutlined from '@mui/icons-material/InsertDriveFileOutlined';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useSession } from 'next-auth/react';
import PersonIcon from '@mui/icons-material/Person';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import AdaptiveTestSetDrawer from './AdaptiveTestSetDrawer';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';

interface TestExplorerGridProps {
  testSets: TestSet[];
  loading: boolean;
  sessionToken?: string;
  initialTotalCount?: number;
}

export default function TestExplorerGrid({
  testSets: initialTestSets,
  loading: initialLoading,
  sessionToken,
  initialTotalCount,
}: TestExplorerGridProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const notifications = useNotifications();
  const [loading, setLoading] = useState(initialLoading);
  const [testSets, setTestSets] = useState<TestSet[]>(initialTestSets);
  const [totalCount, setTotalCount] = useState<number>(
    initialTotalCount || initialTestSets.length
  );
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

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

      const response = await testSetsClient.getTestSets({
        skip: 0,
        limit: 100,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      // Filter test sets that have "Adaptive Testing" behavior
      const adaptiveTestSets = response.data.filter(testSet => {
        const behaviors = testSet.attributes?.metadata?.behaviors || [];
        return behaviors.includes('Adaptive Testing');
      });

      setTestSets(adaptiveTestSets);
      setTotalCount(adaptiveTestSets.length);
    } catch (error) {
      console.error('Error fetching test sets:', error);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, session]);

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
      behaviors: testSet.attributes?.metadata?.behaviors || [],
      totalTests: testSet.attributes?.metadata?.total_tests || 0,
      creator: testSet.user,
      sources: testSet.attributes?.metadata?.sources || [],
    };
  });

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1.5,
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
  ];

  const handleRowClick = (params: any) => {
    router.push(`/test-explorer/${params.id}`);
  };

  const handleSelectionChange = (newSelection: GridRowSelectionModel) => {
    setSelectedRows(newSelection);
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
    ];

    if (selectedRows.length > 0) {
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
        serverSidePagination={false}
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
          <AdaptiveTestSetDrawer
            open={drawerOpen}
            onClose={handleDrawerClose}
            sessionToken={sessionToken || session?.session_token || ''}
            onSuccess={handleTestSetSaved}
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
