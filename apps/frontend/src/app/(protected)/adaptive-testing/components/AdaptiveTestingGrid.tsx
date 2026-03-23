'use client';

import React, { useState, useCallback, useEffect } from 'react';
import {
  GridColDef,
  GridPaginationModel,
  GridRowParams,
  GridRowSelectionModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useRouter } from 'next/navigation';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { AdaptiveTestSet } from '@/utils/api-client/interfaces/adaptive-testing';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { DeleteModal } from '@/components/common/DeleteModal';
import { useNotifications } from '@/components/common/NotificationContext';
import { useSession } from 'next-auth/react';

interface AdaptiveTestingGridProps {
  testSets: AdaptiveTestSet[];
  loading: boolean;
  sessionToken?: string;
}

export default function AdaptiveTestingGrid({
  testSets: initialTestSets,
  loading,
  sessionToken,
}: AdaptiveTestingGridProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const notifications = useNotifications();
  const [rows, setRows] = useState<AdaptiveTestSet[]>(initialTestSets);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setRows(initialTestSets);
  }, [initialTestSets]);

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
        return <Chip label={status} size="small" variant="outlined" />;
      },
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 160,
      renderCell: params => {
        if (!params.value) return '-';
        return (
          <Typography variant="body2">
            {new Date(params.value).toLocaleDateString()}
          </Typography>
        );
      },
    },
  ];

  const handleRowClick = (params: GridRowParams) => {
    router.push(`/adaptive-testing/${params.id}`);
  };

  const handleOpenDialog = () => {
    setName('');
    setDescription('');
    setSubmitError(null);
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    if (!submitting) setDialogOpen(false);
  };

  const handleCreate = async () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setSubmitError('Name is required');
      return;
    }
    const token = sessionToken || session?.session_token;
    if (!token) {
      setSubmitError('Not authenticated');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const client = new ApiClientFactory(token).getAdaptiveTestingClient();
      const created = await client.createAdaptiveTestSet(
        trimmedName,
        description.trim() || undefined
      );
      setDialogOpen(false);
      router.refresh();
      router.push(`/adaptive-testing/${created.id}`);
    } catch (err) {
      setSubmitError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteTestSets = () => {
    setDeleteModalOpen(true);
  };

  const handleDeleteCancel = () => {
    setDeleteModalOpen(false);
  };

  const handleDeleteConfirm = async () => {
    if (selectedRows.length === 0) return;

    const token = sessionToken || session?.session_token;
    if (!token) return;

    try {
      setIsDeleting(true);
      const client = new ApiClientFactory(token).getAdaptiveTestingClient();
      await Promise.all(
        selectedRows.map(id => client.deleteAdaptiveTestSet(String(id)))
      );

      notifications.show(
        `Successfully deleted ${selectedRows.length} ${selectedRows.length === 1 ? 'test set' : 'test sets'}`,
        { severity: 'success', autoHideDuration: 4000 }
      );

      const removed = new Set(selectedRows.map(String));
      setRows(prev => prev.filter(r => !removed.has(String(r.id))));
      setSelectedRows([]);
      router.refresh();
    } catch {
      notifications.show('Failed to delete test sets', {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsDeleting(false);
      setDeleteModalOpen(false);
    }
  };

  const authToken = sessionToken || session?.session_token;

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
      disabled?: boolean;
    }[] = [
      {
        label: 'Add test set',
        icon: <AddIcon />,
        variant: 'contained' as const,
        onClick: handleOpenDialog,
        disabled: !authToken,
      },
    ];

    if (selectedRows.length > 0) {
      buttons.push({
        label: selectedRows.length > 1 ? 'Delete test sets' : 'Delete test set',
        icon: <DeleteIcon />,
        variant: 'outlined' as const,
        color: 'error' as const,
        onClick: handleDeleteTestSets,
      });
    }

    return buttons;
  };

  return (
    <Box>
      {rows.length === 0 ? (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
            No adaptive testing test sets found. Create a test set with the
            &quot;Adaptive Testing&quot; behavior to get started.
          </Typography>
          <Button
            variant="contained"
            onClick={handleOpenDialog}
            disabled={!authToken}
            startIcon={<AddIcon />}
          >
            Add test set
          </Button>
        </Box>
      ) : (
        <BaseDataGrid
          columns={columns}
          rows={rows}
          loading={loading}
          getRowId={row => row.id}
          showToolbar={true}
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
      )}
      <DeleteModal
        open={deleteModalOpen}
        onClose={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        title="Delete adaptive test sets"
        message={`Are you sure you want to delete ${selectedRows.length} ${selectedRows.length === 1 ? 'test set' : 'test sets'}? Related tests in the tree will be removed with this record.`}
        itemType="adaptive test sets"
      />
      <Dialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Add test set</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Name"
            fullWidth
            required
            value={name}
            onChange={e => setName(e.target.value)}
            error={!!submitError && !name.trim()}
          />
          <TextField
            margin="dense"
            label="Description"
            fullWidth
            multiline
            minRows={2}
            value={description}
            onChange={e => setDescription(e.target.value)}
          />
          {submitError && (
            <Typography color="error" variant="body2" sx={{ mt: 1 }}>
              {submitError}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog} disabled={submitting}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            variant="contained"
            disabled={submitting}
          >
            {submitting ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
