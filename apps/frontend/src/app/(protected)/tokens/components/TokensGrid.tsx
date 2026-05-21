'use client';

import React, { useState } from 'react';
import {
  Box,
  IconButton,
  Tooltip,
  Paper,
  CircularProgress,
} from '@mui/material';
import {
  GridPaginationModel,
  type GridRenderCellParams,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Token } from '@/utils/api-client/interfaces/token';
import RefreshIcon from '@mui/icons-material/Refresh';
import { DeleteIcon } from '@/components/icons';
import { formatDistanceToNow } from 'date-fns';
import RefreshTokenModal from './RefreshTokenModal';
import GridBadge from '@/components/common/GridBadge';

interface TokensGridProps {
  tokens: Token[];
  onRefreshToken: (
    tokenId: string,
    expiresInDays: number | null
  ) => Promise<void>;
  onDeleteToken: (tokenId: string) => Promise<void>;
  loading: boolean;
  totalCount: number;
  onPaginationModelChange?: (model: GridPaginationModel) => void;
  paginationModel?: GridPaginationModel;
}

export default function TokensGrid({
  tokens,
  onRefreshToken,
  onDeleteToken,
  loading,
  totalCount,
  onPaginationModelChange,
  paginationModel = {
    page: 0,
    pageSize: 10,
  },
}: TokensGridProps) {
  const [refreshModalOpen, setRefreshModalOpen] = useState(false);
  const [selectedTokenId, setSelectedTokenId] = useState<string | null>(null);

  const handleRefreshClick = (tokenId: string) => {
    setSelectedTokenId(tokenId);
    setRefreshModalOpen(true);
  };

  const columns = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      renderCell: (params: GridRenderCellParams) => (
        <span style={{ fontWeight: 'medium' }}>{params.row.name}</span>
      ),
    },
    {
      field: 'token',
      headerName: 'Token',
      flex: 1.5,
      renderCell: (params: GridRenderCellParams) => params.row.token_obfuscated,
    },
    {
      field: 'last_used',
      headerName: 'Last Used',
      flex: 1,
      renderCell: (params: GridRenderCellParams) =>
        params.row.last_used_at
          ? formatDistanceToNow(new Date(params.row.last_used_at), {
              addSuffix: true,
            })
          : 'Never',
    },
    {
      field: 'expires',
      headerName: 'Expires',
      flex: 1,
      renderCell: (params: GridRenderCellParams) => (
        <GridBadge
          label={
            params.row.expires_at
              ? formatDistanceToNow(new Date(params.row.expires_at), {
                  addSuffix: true,
                })
              : 'Never'
          }
        />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      flex: 0.5,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Tooltip title="Invalidate and refresh">
            <IconButton
              size="small"
              onClick={e => {
                e.stopPropagation();
                handleRefreshClick(params.row.id);
              }}
            >
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete Token">
            <IconButton
              size="small"
              onClick={e => {
                e.stopPropagation();
                onDeleteToken(params.row.id);
              }}
            >
              <DeleteIcon />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  // Initial load spinner — only when we don't have any rows yet.
  if (loading && tokens.length === 0) {
    return (
      <Paper
        elevation={2}
        sx={{
          width: '100%',
          mb: 2,
          py: 8,
          px: 3,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <CircularProgress />
      </Paper>
    );
  }

  return (
    <>
      <Paper sx={{ width: '100%', mb: 2, overflow: 'hidden' }}>
        <Box sx={{ p: 2 }}>
          <BaseDataGrid
            columns={columns}
            rows={tokens}
            loading={loading}
            getRowId={row => (row as Token).id}
            density="standard"
            paginationModel={paginationModel}
            onPaginationModelChange={onPaginationModelChange}
            serverSidePagination={false}
            totalRows={totalCount}
            pageSizeOptions={[10, 25, 50]}
            disablePaperWrapper={true}
          />
        </Box>
      </Paper>
      <RefreshTokenModal
        open={refreshModalOpen}
        onClose={() => setRefreshModalOpen(false)}
        onRefresh={async expiresInDays => {
          if (selectedTokenId) {
            await onRefreshToken(selectedTokenId, expiresInDays);
            setRefreshModalOpen(false);
          }
        }}
        tokenName={tokens.find(t => t.id === selectedTokenId)?.name || ''}
      />
    </>
  );
}
