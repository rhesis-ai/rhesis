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
import { Alert, Box, Paper, Typography } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import DeleteIcon from '@mui/icons-material/Delete';
import IosShareOutlinedIcon from '@mui/icons-material/IosShareOutlined';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { formatDate } from '@/utils/date';
import { explorerKeys } from '@/constants/query-keys';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { UserAvatar } from '@/components/common/UserAvatar';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import type { UserReference } from '@/utils/api-client/interfaces/tests';
import { createRowActionsColumn } from '@/components/common/createRowActionsColumn';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';

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

/** Same name cascade the other grids use, so sorting and export match the cell. */
function userDisplayName(user?: UserReference): string {
  if (!user) return '';
  return (
    user.name ||
    `${user.given_name || ''} ${user.family_name || ''}`.trim() ||
    user.email ||
    ''
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
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const canDeleteSession = useCan(Capability.Explorer.DELETE);

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

  const handleRowDeleteAction = useCallback((id: string) => {
    setPendingDeleteId(id);
    setDeleteModalOpen(true);
  }, []);

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
        valueGetter: (_, row) => row.status?.name || '',
        renderCell: params => {
          if (!params.value) return '-';
          return <GridBadge label={params.value} />;
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
      {
        field: 'user',
        headerName: 'Creator',
        width: 160,
        minWidth: 120,
        valueGetter: (_, row) => userDisplayName(row.user),
        renderCell: params => {
          if (!params.value) return '-';
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <UserAvatar
                userName={params.value}
                userPicture={params.row.user?.picture}
                size={AVATAR_SIZES.SMALL}
              />
              <Typography variant="body2">{params.value}</Typography>
            </Box>
          );
        },
      },
      createRowActionsColumn({
        onDelete: id => handleRowDeleteAction(id),
        canDelete: () => canDeleteSession,
        deleteTooltip: 'Delete session',
        width: 56,
      }),
    ],
    [canDeleteSession, handleRowDeleteAction]
  );

  const handleRowClick = (params: GridRowParams) => {
    router.push(`/explorer/${params.id}`);
  };

  const handleDeleteTestSets = () => {
    setPendingDeleteId(null);
    setDeleteModalOpen(true);
  };

  const handleDeleteCancel = () => {
    setDeleteModalOpen(false);
    setPendingDeleteId(null);
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
    const idsToDelete = pendingDeleteId
      ? [pendingDeleteId]
      : selectedRows.map(String);
    if (idsToDelete.length === 0) return;

    try {
      setIsDeleting(true);
      const client = new ApiClientFactory().getExplorerClient();
      if (pendingDeleteId) {
        await client.deleteExplorerTestSet(pendingDeleteId);
      } else {
        await client.bulkDeleteExplorerTestSets(idsToDelete);
      }

      notifications.show(
        `Successfully deleted ${idsToDelete.length} ${idsToDelete.length === 1 ? 'session' : 'sessions'}`,
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
      // Clear here, not on success only: a stale id would retarget the next bulk delete.
      setPendingDeleteId(null);
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

    if (canDeleteSession) {
      buttons.push({
        label: selectedRows.length > 1 ? 'Delete sessions' : 'Delete session',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteTestSets,
      });
    }

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
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                Failed to load explorer sessions
              </Alert>
            )}
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
              title={
                pendingDeleteId || selectedRows.length === 1
                  ? 'Delete explorer session'
                  : 'Delete explorer sessions'
              }
              message={
                pendingDeleteId
                  ? 'Are you sure you want to delete this session? Its tests and topics are deleted with it.'
                  : `Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'session' : 'sessions'}? Their tests and topics are deleted with them.`
              }
              itemType="explorer sessions"
            />
          </Box>
        </ExplorerToolbarContext.Provider>
      </Paper>
    </GridStateGate>
  );
}
