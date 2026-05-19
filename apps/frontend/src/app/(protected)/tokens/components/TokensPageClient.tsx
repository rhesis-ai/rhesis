'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
import AddIcon from '@mui/icons-material/Add';
import TuneIcon from '@mui/icons-material/TuneOutlined';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import TokensGrid from './TokensGrid';
import CreateTokenModal from './CreateTokenModal';
import TokenDisplay from './TokenDisplay';
import TokenFilterDrawer, {
  type TokenFilters,
  type TokenStatusFilter,
  EMPTY_TOKEN_FILTERS,
  hasActiveTokenFilters,
} from './TokenFilterDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Token, TokenResponse } from '@/utils/api-client/interfaces/token';
import { DeleteModal } from '@/components/common/DeleteModal';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab } from '@/components/common/Fab';
import { SearchPill } from '@/components/common/SearchPill';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { VpnKeyIcon } from '@/components/icons';
import { BORDER_RADIUS } from '@/styles/theme';

const STATUS_OPTIONS: { value: TokenStatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'expired', label: 'Expired' },
];

interface TokensPageClientProps {
  sessionToken: string;
}

export default function TokensPageClient({
  sessionToken,
}: TokensPageClientProps) {
  // Data state
  const [tokens, setTokens] = useState<Token[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal/dialog state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newToken, setNewToken] = useState<TokenResponse | null>(null);
  const [refreshedToken, setRefreshedToken] = useState<TokenResponse | null>(
    null
  );
  const [deleteTokenId, setDeleteTokenId] = useState<string | null>(null);

  // Search & filter state
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<TokenStatusFilter>('all');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] =
    useState<TokenFilters>(EMPTY_TOKEN_FILTERS);

  // Pagination state (client-side)
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 10,
  });

  // Stable tokens client across renders
  const tokensClientRef = useRef(
    new ApiClientFactory(sessionToken).getTokensClient()
  );

  const loadTokens = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      // Pull a generous page so search/filter/pagination can work client-side.
      // Tokens per user/org are typically far below 100.
      const response = await tokensClientRef.current.listTokens({
        skip: 0,
        limit: 100,
        sort_by: 'created_at',
        sort_order: 'desc',
      });
      setTokens(response.data);
    } catch (err) {
      setError((err as Error).message || 'Failed to load tokens');
      setTokens([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTokens();
  }, [loadTokens]);

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleOpenCreateModal = () => {
    setNewToken(null);
    setIsCreateModalOpen(true);
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
      setNewToken({ ...response, name });
      setIsCreateModalOpen(false);
      await loadTokens();
      return response;
    } catch (err) {
      setError((err as Error).message);
      throw err;
    }
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
      await loadTokens();
      setRefreshedToken(response);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleDeleteToken = async (tokenId: string) => {
    setDeleteTokenId(tokenId);
  };

  const confirmDelete = async () => {
    if (!deleteTokenId) return;
    try {
      await tokensClientRef.current.deleteToken(deleteTokenId);
      await loadTokens();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setDeleteTokenId(null);
    }
  };

  // ── Derived data ────────────────────────────────────────────────────────────

  const isExpired = (token: Token) =>
    Boolean(token.expires_at) && new Date(token.expires_at) <= new Date();

  const filteredTokens = useMemo(() => {
    const query = search.trim().toLowerCase();

    return tokens.filter(token => {
      // Search by name or obfuscated token
      if (query) {
        const nameMatch = token.name?.toLowerCase().includes(query);
        const tokenMatch = token.token_obfuscated
          ?.toLowerCase()
          .includes(query);
        if (!nameMatch && !tokenMatch) return false;
      }

      // Center pill: status filter
      if (statusFilter === 'active' && isExpired(token)) return false;
      if (statusFilter === 'expired' && !isExpired(token)) return false;

      // Drawer: status (mirrors center pill, narrower)
      if (drawerFilters.status === 'active' && isExpired(token)) return false;
      if (drawerFilters.status === 'expired' && !isExpired(token)) return false;

      // Drawer: usage
      if (drawerFilters.usage === 'used' && !token.last_used_at) return false;
      if (drawerFilters.usage === 'never_used' && token.last_used_at)
        return false;

      return true;
    });
  }, [tokens, search, statusFilter, drawerFilters]);

  const hasActiveFilters =
    search.trim() !== '' ||
    statusFilter !== 'all' ||
    hasActiveTokenFilters(drawerFilters);

  // Clamp pagination when the filtered list shrinks
  useEffect(() => {
    const lastPage = Math.max(
      0,
      Math.ceil(filteredTokens.length / paginationModel.pageSize) - 1
    );
    if (paginationModel.page > lastPage) {
      setPaginationModel(prev => ({ ...prev, page: lastPage }));
    }
  }, [filteredTokens.length, paginationModel.page, paginationModel.pageSize]);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <PageLayout
      title="API Tokens"
      description="Create API tokens to authenticate with the Rhesis SDK and programmatically manage your testing workflows from your code."
      breadcrumbs={[]}
      actions={
        <Fab
          icon={<AddIcon />}
          tooltip="Create API token"
          aria-label="Create API token"
          onClick={handleOpenCreateModal}
        />
      }
    >
      {/* Toolbar — 3-col grid keeps pills truly centered */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: '1fr auto 1fr',
          alignItems: 'center',
          mb: 3,
          gap: 2,
        }}
      >
        {/* Left: Filter icon + Search pill */}
        <Box sx={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <IconButton
            aria-label="Filter"
            onClick={() => setFilterDrawerOpen(true)}
            sx={{
              bgcolor: 'primary.main',
              color: '#fff',
              borderRadius: BORDER_RADIUS.sm,
              p: '9px',
              '&:hover': { bgcolor: 'primary.dark' },
              '& .MuiSvgIcon-root': { fontSize: 20 },
            }}
          >
            <TuneIcon />
          </IconButton>

          <SearchPill
            value={search}
            onChange={v => {
              setSearch(v);
              setPaginationModel(prev => ({ ...prev, page: 0 }));
            }}
            placeholder="Search tokens…"
          />
        </Box>

        {/* Center: Status pill tabs */}
        <Box sx={{ display: 'flex', justifyContent: 'center' }}>
          {STATUS_OPTIONS.map(({ value, label }, idx) => {
            const selected = statusFilter === value;
            const isFirst = idx === 0;
            const isLast = idx === STATUS_OPTIONS.length - 1;
            return (
              <Box
                key={value}
                component="button"
                onClick={() => {
                  setStatusFilter(value);
                  setPaginationModel(prev => ({ ...prev, page: 0 }));
                }}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  px: '16px',
                  py: '8px',
                  fontSize: 14,
                  fontWeight: 700,
                  lineHeight: '22px',
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: 'primary.main',
                  borderLeft: isFirst ? '1px solid' : 'none',
                  borderRight: isLast ? '1px solid' : 'none',
                  borderRadius: isFirst
                    ? '999px 0 0 999px'
                    : isLast
                      ? '0 999px 999px 0'
                      : 0,
                  bgcolor: selected ? 'primary.main' : 'transparent',
                  color: selected ? '#fff' : 'primary.main',
                  transition: 'background-color 0.15s, color 0.15s',
                  '&:hover': {
                    bgcolor: selected ? 'primary.dark' : 'rgba(0,128,175,0.06)',
                  },
                  whiteSpace: 'nowrap',
                }}
              >
                {label}
              </Box>
            );
          })}
        </Box>
      </Box>

      {/* Error state */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Empty state vs grid */}
      {!loading && tokens.length === 0 ? (
        <EntityEmptyState
          icon={VpnKeyIcon}
          title="No API tokens yet"
          description="Create your first API token to start interacting with the Rhesis API. Tokens allow you to authenticate your applications and build powerful integrations."
          actionLabel="Create API token"
          onAction={handleOpenCreateModal}
        />
      ) : !loading && filteredTokens.length === 0 && hasActiveFilters ? (
        <EntityEmptyState
          icon={VpnKeyIcon}
          title="No tokens match your filters"
          description="Try adjusting your search or filters to find the tokens you're looking for."
          actionLabel="Reset filters"
          onAction={() => {
            setSearch('');
            setStatusFilter('all');
            setDrawerFilters(EMPTY_TOKEN_FILTERS);
          }}
        />
      ) : (
        <TokensGrid
          tokens={filteredTokens}
          onRefreshToken={handleRefreshToken}
          onDeleteToken={handleDeleteToken}
          loading={loading}
          totalCount={filteredTokens.length}
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
        />
      )}

      {/* Modals & dialogs */}
      <CreateTokenModal
        open={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreateToken={handleCreateToken}
      />

      <TokenDisplay
        open={newToken !== null}
        onClose={() => setNewToken(null)}
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
              InputProps={{ readOnly: true }}
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

      <TokenFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        onApply={f => {
          setDrawerFilters(f);
          setPaginationModel(prev => ({ ...prev, page: 0 }));
        }}
      />
    </PageLayout>
  );
}
