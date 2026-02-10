'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Button,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Alert,
} from '@mui/material';
import { GridPaginationModel } from '@mui/x-data-grid';
import TokensGrid from './TokensGrid';
import CreateTokenModal from './CreateTokenModal';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Token, TokenResponse } from '@/utils/api-client/interfaces/token';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import TokenDisplay from './TokenDisplay';
import { DeleteModal } from '@/components/common/DeleteModal';

interface TokensPageClientProps {
  sessionToken: string;
}

export default function TokensPageClient({
  sessionToken,
}: TokensPageClientProps) {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newToken, setNewToken] = useState<TokenResponse | null>(null);
  const [refreshedToken, setRefreshedToken] = useState<TokenResponse | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteTokenId, setDeleteTokenId] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });

  // Use a ref to store the tokens client to prevent recreation on each render
  const tokensClientRef = useRef(
    new ApiClientFactory(sessionToken).getTokensClient()
  );

  const loadTokens = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const skip = paginationModel.page * paginationModel.pageSize;
      const response = await tokensClientRef.current.listTokens({
        skip,
        limit: paginationModel.pageSize,
        sort_by: 'created_at',
        sort_order: 'desc',
      });

      setTokens(response.data);
      setTotalCount(response.pagination.totalCount);
    } catch (error) {
      setError((error as Error).message || 'Failed to load tokens');
      setTokens([]);
    } finally {
      setLoading(false);
    }
  }, [paginationModel]);

  const handlePaginationModelChange = (newModel: GridPaginationModel) => {
    setPaginationModel(newModel);
  };

  const handleCreateToken = async (
    name: string,
    expiresInDays: number | null
  ) => {
    try {
      const response = await tokensClientRef.current.createToken(
        name,
        expiresInDays
      );
      setNewToken({
        ...response,
        name,
      });
      setIsCreateModalOpen(false);
      await loadTokens();
      return response;
    } catch (error) {
      setError((error as Error).message);
      throw error;
    }
  };

  const handleCloseNewToken = () => {
    setNewToken(null);
  };

  const handleOpenCreateModal = () => {
    setNewToken(null);
    setIsCreateModalOpen(true);
  };

  const handleRefreshToken = async (
    tokenId: string,
    expiresInDays: number | null
  ) => {
    try {
      const response = await tokensClientRef.current.refreshToken(
        tokenId,
        expiresInDays
      );
      await loadTokens(); // Reload tokens to get updated list
      setRefreshedToken(response);
    } catch (error) {
      setError((error as Error).message);
    }
  };

  const handleDeleteToken = async (tokenId: string) => {
    setDeleteTokenId(tokenId);
  };

  const confirmDelete = async () => {
    if (deleteTokenId) {
      try {
        await tokensClientRef.current.deleteToken(deleteTokenId);
        await loadTokens();
        setDeleteTokenId(null);
      } catch (error) {
        setError((error as Error).message);
        setDeleteTokenId(null);
      }
    }
  };

  // Use useEffect with an empty dependency array to load tokens only once on mount
  useEffect(() => {
    loadTokens();
  }, [loadTokens]);

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <TokensGrid
        tokens={tokens}
        onRefreshToken={handleRefreshToken}
        onDeleteToken={handleDeleteToken}
        loading={loading}
        onCreateToken={handleOpenCreateModal}
        totalCount={totalCount}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationModelChange}
      />

      <CreateTokenModal
        open={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreateToken={handleCreateToken}
      />

      <TokenDisplay
        open={newToken !== null}
        onClose={handleCloseNewToken}
        token={newToken}
      />

      <Dialog
        open={refreshedToken !== null}
        onClose={() => setRefreshedToken(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Your Refreshed API Token</DialogTitle>
        <DialogContent>
          <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'bold' }}>
            Token Name: {refreshedToken?.name}
          </Typography>
          <Typography variant="subtitle2" sx={{ mb: 2 }}>
            Expires:{' '}
            {refreshedToken?.expires_at
              ? new Date(refreshedToken.expires_at).toLocaleDateString()
              : 'Never'}
          </Typography>
          <Typography color="warning.main" sx={{ mb: 2 }}>
            Store this token securely - it won&apos;t be shown again. If you
            lose it, you&apos;ll need to generate a new one.
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TextField
              fullWidth
              value={refreshedToken?.access_token || ''}
              variant="outlined"
              InputProps={{
                readOnly: true,
              }}
            />
            <IconButton
              onClick={async () => {
                if (refreshedToken) {
                  await navigator.clipboard.writeText(
                    refreshedToken.access_token
                  );
                }
              }}
              color="primary"
            >
              <ContentCopyIcon />
            </IconButton>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRefreshedToken(null)}>Close</Button>
        </DialogActions>
      </Dialog>

      <DeleteModal
        open={deleteTokenId !== null}
        onClose={() => setDeleteTokenId(null)}
        onConfirm={confirmDelete}
        itemType="token"
        itemName={tokens.find(t => t.id === deleteTokenId)?.name}
        message={
          deleteTokenId && tokens.find(t => t.id === deleteTokenId)?.name
            ? `Are you sure you want to delete the token "${tokens.find(t => t.id === deleteTokenId)?.name}"? This action cannot be undone, and any applications using this token will no longer be able to authenticate.`
            : `Are you sure you want to delete this token? This action cannot be undone, and any applications using this token will no longer be able to authenticate.`
        }
      />
    </Box>
  );
}
