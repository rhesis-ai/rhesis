'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { type GridRenderCellParams, type GridColDef } from '@mui/x-data-grid';
import RefreshIcon from '@mui/icons-material/Refresh';
import { formatDistanceToNow } from 'date-fns';
import EntityGrid, {
  type EntityGridDrawerAdapter,
  type EntityGridFilterState,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { VpnKeyIcon } from '@/components/icons';
import { Token } from '@/utils/api-client/interfaces/token';
import type { BulkDeleteActionsState } from '@/hooks/useBulkDelete';
import RefreshTokenModal from './RefreshTokenModal';
import { tokensList } from './list';
import TokenFilterDrawer, {
  type TokenFilters,
  EMPTY_TOKEN_FILTERS,
  countActiveTokenFilters,
} from './TokenFilterDrawer';

const STATUS_PILL_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'active' },
  { label: 'Expired', value: 'expired' },
];

// The pill wins over the drawer's status for the one field they overlap on.
function toFilters(state: EntityGridFilterState<TokenFilters>) {
  return {
    search: state.search,
    status:
      state.pill || (state.drawer.status === 'all' ? '' : state.drawer.status),
    usage: state.drawer.usage === 'all' ? '' : state.drawer.usage,
  };
}

const drawerAdapter: EntityGridDrawerAdapter<TokenFilters> = {
  empty: EMPTY_TOKEN_FILTERS,
  countActive: countActiveTokenFilters,
  render: props => (
    <TokenFilterDrawer
      open={props.open}
      onClose={props.onClose}
      filters={props.filters}
      onApply={props.onApply}
    />
  ),
};

interface TokensGridProps {
  canCreate?: boolean;
  onCreateClick?: () => void;
  /** Called with the refreshed token so the page can show it once. */
  onRefreshToken: (
    tokenId: string,
    expiresInDays: number | null
  ) => Promise<void>;
  onBulkActionsChange?: (actions: BulkDeleteActionsState) => void;
  /** Bumped by the page after a create succeeds, to trigger a re-fetch. */
  refreshTrigger?: number;
}

export default function TokensGrid({
  canCreate,
  onCreateClick,
  onRefreshToken,
  onBulkActionsChange,
  refreshTrigger,
}: TokensGridProps) {
  const [refreshTarget, setRefreshTarget] = useState<Token | null>(null);

  const extraRowActions = useMemo(
    () => [
      {
        key: 'refresh',
        icon: RefreshIcon,
        tooltip: 'Invalidate and refresh',
        onClick: (_id: string, row: Record<string, unknown>) =>
          setRefreshTarget(row as unknown as Token),
        hoverColor: 'primary.main' as const,
      },
    ],
    []
  );

  const handleRefreshClose = useCallback(() => setRefreshTarget(null), []);

  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Name',
        flex: 1,
        renderCell: (params: GridRenderCellParams) => (
          <span style={{ fontWeight: 500 }}>{params.row.name}</span>
        ),
      },
      {
        field: 'token',
        headerName: 'Token',
        flex: 1.5,
        sortable: false,
        renderCell: (params: GridRenderCellParams) =>
          params.row.token_obfuscated,
      },
      {
        field: 'last_used_at',
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
        field: 'expires_at',
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
    ],
    []
  );

  return (
    <EntityGrid<Token, typeof tokensList.filters, TokenFilters>
      descriptor={tokensList}
      columns={columns}
      toFilters={toFilters}
      emptyState={
        <EntityEmptyState
          card
          icon={VpnKeyIcon}
          title="No API tokens yet"
          description="Create your first API token to start interacting with the Rhesis API. Tokens allow you to authenticate your applications and build powerful integrations."
          actionLabel={canCreate ? 'Create API token' : undefined}
          onAction={canCreate ? onCreateClick : undefined}
        />
      }
      refreshTrigger={refreshTrigger}
      searchPlaceholder="Search tokens…"
      pills={{ tabs: STATUS_PILL_TABS }}
      drawer={drawerAdapter}
      selectionLabel="Select tokens"
      editAction={false}
      extraRowActions={extraRowActions}
      onBulkActionsChange={onBulkActionsChange}
      density="standard"
      storageKey="tokens-grid"
      pageSizeOptions={[10, 25, 50]}
      renderSelectionExtras={ctx => (
        <RefreshTokenModal
          open={refreshTarget !== null}
          onClose={handleRefreshClose}
          onRefresh={async expiresInDays => {
            if (refreshTarget) {
              await onRefreshToken(refreshTarget.id, expiresInDays);
              setRefreshTarget(null);
              ctx.refresh();
            }
          }}
          tokenName={refreshTarget?.name || ''}
        />
      )}
    />
  );
}
