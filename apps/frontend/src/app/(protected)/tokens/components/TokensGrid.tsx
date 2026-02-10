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
  CircularProgress,
} from '@mui/material';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { Token } from '@/utils/api-client/interfaces/token';
import RefreshIcon from '@mui/icons-material/Refresh';
import { DeleteIcon, VpnKeyIcon } from '@/components/icons';
import { formatDistanceToNow } from 'date-fns';
import RefreshTokenModal from './RefreshTokenModal';
import AddIcon from '@mui/icons-material/Add';
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
  const _theme = useTheme();
  const [refreshModalOpen, setRefreshModalOpen] = useState(false);
  const [selectedTokenId, setSelectedTokenId] = useState<string | null>(null);

  const handleRefreshClick = (tokenId: string) => {
    setSelectedTokenId(tokenId);
    setRefreshModalOpen(true);
  };

  // Custom toolbar with right-aligned button
  const customToolbar = (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'flex-end',
        width: '100%',
      }}
    >
      <Button
        variant="contained"
        startIcon={<AddIcon />}
        onClick={onCreateToken}
      >
        Create API Token
      </Button>
    </Box>
  );

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

  // Show loading state during initial load
  if (loading && tokens.length === 0) {
    return (
      <Paper
        elevation={2}
        sx={{
          width: '100%',
          mb: 2,
          textAlign: 'center',
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

  // Show empty state when not loading and no tokens exist
  if (tokens.length === 0) {
    return (
      <Paper
        elevation={2}
        sx={{
          width: '100%',
          mb: 2,
          textAlign: 'center',
          py: 8,
          px: 3,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            mb: 2,
          }}
        >
          <VpnKeyIcon
            sx={{
              fontSize: 60,
              color: 'primary.main',
              opacity: 0.7,
            }}
          />
        </Box>

        <Typography
          variant="h5"
          sx={{
            color: 'text.primary',
            fontWeight: 500,
          }}
        >
          No API tokens yet
        </Typography>

        <Typography
          variant="body1"
          color="text.secondary"
          sx={{
            maxWidth: 550,
            mx: 'auto',
          }}
        >
          Create your first API token to start interacting with the Rhesis API.
          Tokens allow you to authenticate your applications and build powerful
          integrations.
        </Typography>

        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={onCreateToken}
          size="large"
          sx={{ mt: 2 }}
        >
          Create API Token
        </Button>
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
            customToolbarContent={customToolbar}
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
