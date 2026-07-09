'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Paper, Alert } from '@mui/material';
import TokensGrid, {
  TokensToolbarContext,
  type TokenStatusFilter,
  type TokensToolbarState,
} from './TokensGrid';
import CreateTokenDrawer from './CreateTokenDrawer';
import TokenDisplay from './TokenDisplay';
import TokenFilterDrawer, {
  type TokenFilters,
  EMPTY_TOKEN_FILTERS,
  hasActiveTokenFilters,
  countActiveTokenFilters,
} from './TokenFilterDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Token, TokenResponse } from '@/utils/api-client/interfaces/token';
import { DeleteModal } from '@/components/common/DeleteModal';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { VpnKeyIcon } from '@/components/icons';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { Can, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';

interface TokensPageClientProps {
  sessionToken: string;
}

export default function TokensPageClient({
  sessionToken,
}: TokensPageClientProps) {
  const { allowed: canManage, loading: permsLoading } = useCanWithStatus(
    Capability.Token.MANAGE
  );

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
    expiresInDays: number | null,
    scopes: string[] | null
  ) => {
    try {
      const response = await tokensClientRef.current.createToken(
        name,
        expiresInDays,
        scopes
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

  // ── Toolbar context value ────────────────────────────────────────────────────

  const toolbarContextValue: TokensToolbarState = useMemo(
    () => ({
      searchQuery: search,
      setSearchQuery: (v: string) => {
        setSearch(v);
        setPaginationModel(prev => ({ ...prev, page: 0 }));
      },
      statusFilter,
      setStatusFilter: (v: TokenStatusFilter) => {
        setStatusFilter(v);
        setPaginationModel(prev => ({ ...prev, page: 0 }));
      },
      openFilterDrawer: () => setFilterDrawerOpen(true),
      hasActiveDrawerFilters: hasActiveTokenFilters(drawerFilters),
      activeFilterCount: countActiveTokenFilters(drawerFilters),
    }),
    [search, statusFilter, drawerFilters]
  );

  // ── Render ──────────────────────────────────────────────────────────────────

  if (permsLoading) return <PageLoadingState />;
  if (!canManage) return <AccessDenied resource="API tokens" />;

  return (
    <PageLayout
      title="API Tokens"
      description="Create API tokens to authenticate with the Rhesis SDK and programmatically manage your testing workflows from your code."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Can capability={Capability.Token.MANAGE}>
            <Fab
              icon={<FabAddIcon />}
              tooltip="Create API token"
              aria-label="Create API token"
              onClick={handleOpenCreateModal}
            />
          </Can>
        </FabGroup>
      }
    >
      {/* Error state */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Empty state vs grid */}
      {!loading && tokens.length === 0 ? (
        <EntityEmptyState
          card
          icon={VpnKeyIcon}
          title="No API tokens yet"
          description="Create your first API token to start interacting with the Rhesis API. Tokens allow you to authenticate your applications and build powerful integrations."
          actionLabel={canManage ? 'Create API token' : undefined}
          onAction={canManage ? handleOpenCreateModal : undefined}
        />
      ) : !loading && filteredTokens.length === 0 && hasActiveFilters ? (
        <EntityEmptyState
          card
          showAddIcon={false}
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
        <Paper
          elevation={0}
          sx={{
            width: '100%',
            borderRadius: BORDER_RADIUS.md,
            boxShadow: ELEVATION.xs,
            border: theme => `1px solid ${theme.palette.greyscale.border}`,
            overflow: 'hidden',
          }}
        >
          <TokensToolbarContext.Provider value={toolbarContextValue}>
            <TokensGrid
              tokens={filteredTokens}
              onRefreshToken={handleRefreshToken}
              onDeleteToken={handleDeleteToken}
              loading={loading}
              totalCount={filteredTokens.length}
              paginationModel={paginationModel}
              onPaginationModelChange={setPaginationModel}
            />
          </TokensToolbarContext.Provider>
        </Paper>
      )}

      {/* Modals & dialogs */}
      <CreateTokenDrawer
        open={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        sessionToken={sessionToken}
        onCreateToken={handleCreateToken}
      />

      <TokenDisplay
        open={newToken !== null}
        onClose={() => setNewToken(null)}
        token={newToken}
      />

      <TokenDisplay
        title="Your Refreshed API Token"
        open={refreshedToken !== null}
        onClose={() => setRefreshedToken(null)}
        token={refreshedToken}
      />

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
