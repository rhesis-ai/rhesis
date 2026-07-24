'use client';

import React, {
  useState,
  useCallback,
  useEffect,
  useContext,
  useMemo,
} from 'react';
import {
  GridColDef,
  GridPaginationModel,
  GridRowParams,
  GridRowSelectionModel,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import BaseDataGrid, { GRID_PAPER_SX } from '@/components/common/BaseDataGrid';
import GridToolbar from '@/components/common/GridToolbar';
import GridStateGate from '@/components/common/GridStateGate';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { AccountTreeIcon } from '@/components/icons';
import { useRouter } from 'next/navigation';
import { Box, Paper, Typography } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import DeleteIcon from '@mui/icons-material/Delete';
import IosShareOutlinedIcon from '@mui/icons-material/IosShareOutlined';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { formatDate } from '@/utils/date';
import { explorerKeys } from '@/constants/query-keys';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface ExplorerGridProps {
  canCreate?: boolean;
  onCreateClick?: () => void;
}

interface ExplorerToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
}

const ExplorerToolbarContext = React.createContext<ExplorerToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
});

function ExplorerUnifiedToolbar() {
  const { searchQuery, setSearchQuery } = useContext(ExplorerToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search sessions…"
      rightContent={
        <>
          <GridToolbarColumnsButton />
          <GridToolbarDensitySelector />
          <GridToolbarExport />
        </>
      }
    />
  );
}

export default function ExplorerGrid({
  canCreate,
  onCreateClick,
}: ExplorerGridProps) {
  const router = useRouter();
  const { status } = useSession();
  const queryClient = useQueryClient();
  const notifications = useNotifications();
  const [searchQuery, setSearchQuery] = useState('');
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const {
    data,
    isLoading: loading,
    error,
  } = useQuery({
    queryKey: explorerKeys.all(),
    queryFn: () =>
      new ApiClientFactory().getExplorerClient().getExplorerTestSets(),
    enabled: isAuthenticated(status),
  });

  const allRows = data ?? [];

  useEffect(() => {
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [searchQuery]);

  const rows = searchQuery.trim()
    ? allRows.filter(r => {
        const q = searchQuery.toLowerCase();
        return (
          r.name?.toLowerCase().includes(q) ||
          (r.description ?? '').toLowerCase().includes(q)
        );
      })
    : allRows;

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const columns = useMemo<GridColDef[]>(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1.5,
        minWidth: 200,
      },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 200,
        renderCell: params => (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {params.value || '-'}
          </Typography>
        ),
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        renderCell: params => {
          const status = params.value;
          if (!status) return '-';
          return <GridBadge label={status} />;
        },
      },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 160,
        renderCell: params => {
          if (!params.value) return '-';
          return (
            <Typography variant="body2">{formatDate(params.value)}</Typography>
          );
        },
      },
    ],
    []
  );

  const handleRowClick = (params: GridRowParams) => {
    router.push(`/explorer/${params.id}`);
  };

  const handleDeleteTestSets = () => {
    setDeleteModalOpen(true);
  };

  const handleDeleteCancel = () => {
    setDeleteModalOpen(false);
  };

  const handleExportSelected = useCallback(async () => {
    if (selectedRows.length !== 1) return;

    setIsExporting(true);
    try {
      const client = new ApiClientFactory().getExplorerClient();
      const result = await client.exportRegularTestSetFromExplorer(
        String(selectedRows[0])
      );
      const { exported, skipped, test_set: created } = result;
      const parts = [
        `Created "${created.name}"`,
        `exported ${exported} test(s)`,
      ];
      if (skipped > 0) {
        parts.push(`skipped ${skipped}`);
      }
      notifications.show(parts.join('. '), {
        severity: 'success',
        autoHideDuration: 6000,
      });
      router.push(`/test-sets/${created.id}`);
    } catch (err) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to export test set.',
        { severity: 'error', autoHideDuration: 6000 }
      );
    } finally {
      setIsExporting(false);
    }
  }, [notifications, router, selectedRows]);

  const handleDeleteConfirm = async () => {
    if (selectedRows.length === 0) return;

    try {
      setIsDeleting(true);
      const client = new ApiClientFactory().getExplorerClient();
      await client.bulkDeleteExplorerTestSets(selectedRows.map(String));

      notifications.show(
        `Successfully deleted ${selectedRows.length} ${selectedRows.length === 1 ? 'session' : 'sessions'}`,
        { severity: 'success', autoHideDuration: 4000 }
      );

      setSelectedRows([]);
      queryClient.invalidateQueries({ queryKey: explorerKeys.all() });
    } catch {
      notifications.show('Failed to delete sessions', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  };

  const getActionButtons = () => {
    if (selectedRows.length === 0) return [];

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
    }[] = [];

    if (selectedRows.length === 1) {
      buttons.push({
        label: 'Save to Test Set',
        icon: <IosShareOutlinedIcon />,
        variant: 'outlined' as const,
        onClick: () => void handleExportSelected(),
        disabled: isExporting,
      });
    }

    buttons.push({
      label: selectedRows.length > 1 ? 'Delete sessions' : 'Delete session',
      icon: <DeleteIcon />,
      variant: 'outlined' as const,
      color: 'error' as const,
      onClick: handleDeleteTestSets,
    });

    return buttons;
  };

  return (
    <GridStateGate
      data={data}
      error={error ? 'Failed to load explorer sessions' : null}
      isEmpty={allRows.length === 0 && !searchQuery.trim()}
      emptyState={
        <EntityEmptyState
          card
          icon={AccountTreeIcon}
          title="No explorer sessions yet"
          description="Start a new session to explore behaviors and generate tests, or load an existing test set."
          actionLabel={canCreate ? 'New session' : undefined}
          onAction={canCreate ? onCreateClick : undefined}
        />
      }
    >
      <Paper sx={GRID_PAPER_SX}>
        <ExplorerToolbarContext.Provider
          value={{ searchQuery, setSearchQuery }}
        >
          <Box>
            <BaseDataGrid
              columns={columns}
              rows={rows}
              loading={loading}
              getRowId={row => row.id}
              showToolbar={true}
              toolbarSlot={ExplorerUnifiedToolbar}
              actionButtons={getActionButtons()}
              onRowClick={handleRowClick}
              paginationModel={paginationModel}
              onPaginationModelChange={handlePaginationModelChange}
              serverSidePagination={false}
              totalRows={rows.length}
              pageSizeOptions={[10, 25, 50]}
              disablePaperWrapper={true}
              persistState
              checkboxSelection
              disableRowSelectionOnClick
              onRowSelectionModelChange={setSelectedRows}
              rowSelectionModel={selectedRows}
            />
            <DeleteModal
              open={deleteModalOpen}
              onClose={handleDeleteCancel}
              onConfirm={handleDeleteConfirm}
              isLoading={isDeleting}
              title="Delete explorer sessions"
              message={`Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'session' : 'sessions'}? Related tests in the tree will be removed with this record.`}
              itemType="explorer sessions"
            />
          </Box>
        </ExplorerToolbarContext.Provider>
      </Paper>
    </GridStateGate>
  );
}
