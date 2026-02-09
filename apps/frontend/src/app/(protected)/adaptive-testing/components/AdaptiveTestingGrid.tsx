'use client';

import React, { useState, useCallback } from 'react';
import {
  GridColDef,
  GridPaginationModel,
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
import { AdaptiveTestSet } from '@/utils/api-client/interfaces/adaptive-testing';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface AdaptiveTestingGridProps {
  testSets: AdaptiveTestSet[];
  loading: boolean;
  sessionToken?: string;
}

export default function AdaptiveTestingGrid({
  testSets,
  loading,
  sessionToken,
}: AdaptiveTestingGridProps) {
  const router = useRouter();
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

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
        return (
          <Chip
            label={status}
            size="small"
            variant="outlined"
          />
        );
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

  const handleRowClick = (params: any) => {
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
    if (!sessionToken) {
      setSubmitError('Not authenticated');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const client = new ApiClientFactory(sessionToken).getAdaptiveTestingClient();
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

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
        <Button
          variant="contained"
          onClick={handleOpenDialog}
          disabled={!sessionToken}
        >
          Add test set
        </Button>
      </Box>
      {testSets.length === 0 ? (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <Typography
            variant="body1"
            color="text.secondary"
          >
            No adaptive testing test sets found. Create a
            test set with the &quot;Adaptive Testing&quot;
            behavior to get started.
          </Typography>
        </Box>
      ) : (
        <BaseDataGrid
          columns={columns}
          rows={testSets}
          loading={loading}
          getRowId={row => row.id}
          showToolbar={false}
          onRowClick={handleRowClick}
          paginationModel={paginationModel}
          onPaginationModelChange={
            handlePaginationModelChange
          }
          serverSidePagination={false}
          totalRows={testSets.length}
          pageSizeOptions={[10, 25, 50]}
          disablePaperWrapper={true}
          persistState
        />
      )}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
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
          <Button onClick={handleCreate} variant="contained" disabled={submitting}>
            {submitting ? 'Creating…' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
