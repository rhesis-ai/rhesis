'use client';

import React, { useState, useCallback, useEffect, useContext } from 'react';
import {
  GridColDef,
  GridPaginationModel,
  GridRowParams,
  GridRowSelectionModel,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import GridToolbar from '@/components/common/GridToolbar';
import { useRouter } from 'next/navigation';
import { Box, Typography } from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import DeleteIcon from '@mui/icons-material/Delete';
import IosShareOutlinedIcon from '@mui/icons-material/IosShareOutlined';
import type { ExplorerTestSet } from '@/utils/api-client/interfaces/explorer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { formatDate } from '@/utils/date';

interface ExplorerGridProps {
  sessionToken: string;
  refreshKey?: number;
  onRefresh?: () => void;
  onTotalCountChange?: (count: number) => void;
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
  sessionToken,
  refreshKey = 0,
  onRefresh,
  onTotalCountChange,
}: ExplorerGridProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const [allRows, setAllRows] = useState<ExplorerTestSet[]>([]);
  const [rows, setRows] = useState<ExplorerTestSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const loadSessions = async () => {
      setLoading(true);
      try {
        const client = new ApiClientFactory(sessionToken).getExplorerClient();
        const sessions = await client.getExplorerTestSets();
        if (!cancelled) {
          setAllRows(sessions);
          onTotalCountChange?.(sessions.length);
        }
      } catch {
        if (!cancelled) {
          setAllRows([]);
          onTotalCountChange?.(0);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadSessions();
    return () => {
      cancelled = true;
    };
  }, [sessionToken, refreshKey]);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setRows(allRows);
      return;
    }
    const q = searchQuery.toLowerCase();
    setRows(
      allRows.filter(
        r =>
          r.name?.toLowerCase().includes(q) ||
          (r.description ?? '').toLowerCase().includes(q)
      )
    );
    setPaginationModel(prev => ({ ...prev, page: 0 }));
  }, [searchQuery, allRows]);

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const columns: GridColDef[] = [
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
  ];

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
      const client = new ApiClientFactory(sessionToken).getExplorerClient();
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
  }, [notifications, router, selectedRows, sessionToken]);

  const handleDeleteConfirm = async () => {
    if (selectedRows.length === 0) return;

    try {
      setIsDeleting(true);
      const client = new ApiClientFactory(sessionToken).getExplorerClient();
      await Promise.all(
        selectedRows.map(id => client.deleteExplorerTestSet(String(id)))
      );

      notifications.show(
        `Successfully deleted ${selectedRows.length} ${selectedRows.length === 1 ? 'session' : 'sessions'}`,
        { severity: 'success', autoHideDuration: 4000 }
      );

      const removed = new Set(selectedRows.map(String));
      setAllRows(prev => prev.filter(r => !removed.has(String(r.id))));
      setSelectedRows([]);
      onRefresh?.();
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
    <ExplorerToolbarContext.Provider value={{ searchQuery, setSearchQuery }}>
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
  );
}
