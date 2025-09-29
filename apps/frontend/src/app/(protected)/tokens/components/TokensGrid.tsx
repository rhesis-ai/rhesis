'use client';

import React, { useState } from 'react';
import {
  Chip,
  Box,
  IconButton,
  Tooltip,
  Typography,
  Button,
  Paper,
  useTheme,
} from '@mui/material';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Token } from '@/utils/api-client/interfaces/token';
import RefreshIcon from '@mui/icons-material/Refresh';
import { DeleteIcon } from '@/components/icons';
import { formatDistanceToNow } from 'date-fns';
import RefreshTokenModal from './RefreshTokenModal';
import AddIcon from '@mui/icons-material/Add';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import KeyIcon from '@mui/icons-material/Key';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import { GridPaginationModel } from '@mui/x-data-grid';

interface TokensGridProps {
  tokens: Token[];
  onRefreshToken: (
    tokenId: string,
    expiresInDays: number | null
  ) => Promise<void>;
  onDeleteToken: (tokenId: string) => Promise<void>;
  loading: boolean;
  onCreateToken?: () => void;
  totalCount: number;
  onPaginationModelChange?: (model: GridPaginationModel) => void;
  paginationModel?: GridPaginationModel;
}

export default function TokensGrid({
  tokens,
  onRefreshToken,
  onDeleteToken,
  loading,
  onCreateToken,
  totalCount,
  onPaginationModelChange,
  paginationModel = {
    page: 0,
    pageSize: 10,
  },
}: TokensGridProps) {
  const theme = useTheme();
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
      renderCell: (params: any) => (
        <span style={{ fontWeight: 'medium' }}>{params.row.name}</span>
      ),
    },
    {
      field: 'token',
      headerName: 'Token',
      flex: 1.5,
      renderCell: (params: any) => params.row.token_obfuscated,
    },
    {
      field: 'last_used',
      headerName: 'Last Used',
      flex: 1,
      renderCell: (params: any) =>
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
      renderCell: (params: any) =>
        params.row.expires_at ? (
          <Chip
            label={formatDistanceToNow(new Date(params.row.expires_at), {
              addSuffix: true,
            })}
            size="small"
            variant="outlined"
            sx={{
              borderColor:
                new Date(params.row.expires_at) > new Date()
                  ? 'success.light'
                  : 'error.light',
              color:
                new Date(params.row.expires_at) > new Date()
                  ? 'success.main'
                  : 'error.main',
              bgcolor: 'transparent',
            }}
          />
        ) : (
          <Chip
            label="Never"
            size="small"
            variant="outlined"
            sx={{
              borderColor: 'success.light',
              color: 'success.main',
              bgcolor: 'transparent',
            }}
          />
        ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      flex: 0.5,
      sortable: false,
      renderCell: (params: any) => (
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

  if (!loading && tokens.length === 0) {
    return (
      <Paper sx={{ width: '100%', mb: 2, overflow: 'hidden' }}>
        <Box
          sx={{
            textAlign: 'center',
            py: 8,
            px: 2,
            bgcolor: 'background.paper',
            borderRadius: theme => theme.shape.borderRadius * 0.25,
          }}
        >
          <Typography
            variant="h5"
            sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <RocketLaunchIcon color="primary" />
            Create your first Rhesis API token!
          </Typography>
          <Typography variant="body1" sx={{ mb: 1 }}>
            You haven&apos;t created any tokens yet. Get started by creating
            your first token
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            <Box
              component="span"
              sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
            >
              <KeyIcon fontSize="small" color="primary" />
              Create tokens to interact with the Rhesis API
            </Box>
            <Box
              component="span"
              sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
            >
              <SportsEsportsIcon fontSize="small" color="primary" />
              Build amazing integrations and have fun!
            </Box>
          </Typography>
        </Box>
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
            getRowId={(row: Token) => row.id}
            density="standard"
            paginationModel={paginationModel}
            onPaginationModelChange={onPaginationModelChange}
            serverSidePagination={true}
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
