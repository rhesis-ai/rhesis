'use client';

import React, { useContext, useState } from 'react';
import { Box, Tooltip, IconButton } from '@mui/material';
import {
  GridPaginationModel,
  type GridRenderCellParams,
  type GridColDef,
  GridToolbarColumnsButton,
  GridToolbarDensitySelector,
  GridToolbarExport,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import GridToolbar, { ToolbarPillTabs } from '@/components/common/GridToolbar';
import { Token } from '@/utils/api-client/interfaces/token';
import RefreshIcon from '@mui/icons-material/Refresh';
import { DeleteIcon } from '@/components/icons';
import { formatDistanceToNow } from 'date-fns';
import RefreshTokenModal from './RefreshTokenModal';
import GridBadge from '@/components/common/GridBadge';
import {
  ROW_ACTIONS_CLASS,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';

// ── Toolbar status filter options ────────────────────────────────────────────

export type TokenStatusFilter = 'all' | 'active' | 'expired';

export const STATUS_OPTIONS: { value: TokenStatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'expired', label: 'Expired' },
];

// ── Toolbar context (passes search/filter state into the DataGrid slot) ──────

export interface TokensToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  statusFilter: TokenStatusFilter;
  setStatusFilter: (v: TokenStatusFilter) => void;
  openFilterDrawer: () => void;
  hasActiveDrawerFilters: boolean;
  activeFilterCount: number;
}

export const TokensToolbarContext = React.createContext<TokensToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  statusFilter: 'all',
  setStatusFilter: () => {},
  openFilterDrawer: () => {},
  hasActiveDrawerFilters: false,
  activeFilterCount: 0,
});

function TokensUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    statusFilter,
    setStatusFilter,
    openFilterDrawer,
    hasActiveDrawerFilters,
    activeFilterCount,
  } = useContext(TokensToolbarContext);

  return (
    <GridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search tokens…"
      onFilterClick={openFilterDrawer}
      hasActiveFilters={hasActiveDrawerFilters}
      activeFilterCount={activeFilterCount}
      middleContent={
        <ToolbarPillTabs
          tabs={STATUS_OPTIONS}
          activeValue={statusFilter}
          onChange={v => setStatusFilter(v as TokenStatusFilter)}
        />
      }
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

// ── Grid component ────────────────────────────────────────────────────────────

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

  const columns: GridColDef[] = [
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
      headerName: '',
      width: 88,
      sortable: false,
      disableColumnMenu: true,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams) => (
        <Box
          className={ROW_ACTIONS_CLASS}
          sx={{
            display: 'flex',
            gap: '4px',
            justifyContent: 'center',
            alignItems: 'center',
            width: '100%',
          }}
        >
          <Tooltip title="Invalidate and refresh">
            <IconButton
              size="small"
              onClick={e => {
                e.stopPropagation();
                handleRefreshClick(params.row.id);
              }}
              sx={{
                p: 0.5,
                color: 'text.secondary',
                '&:hover': { color: 'primary.main', bgcolor: 'action.hover' },
              }}
            >
              <RefreshIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete Token">
            <IconButton
              size="small"
              onClick={e => {
                e.stopPropagation();
                onDeleteToken(params.row.id);
              }}
              sx={{
                p: 0.5,
                color: 'text.secondary',
                '&:hover': { color: 'error.main', bgcolor: 'action.hover' },
              }}
            >
              <DeleteIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    } as GridColDef,
  ];

  return (
    <>
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
        toolbarSlot={TokensUnifiedToolbar}
        persistState
        storageKey="tokens-grid"
        sx={rowActionsHoverSx}
      />
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
