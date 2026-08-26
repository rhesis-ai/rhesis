'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { GridColDef } from '@mui/x-data-grid';
import { useRouter } from 'next/navigation';
import { Box, Typography } from '@mui/material';
import EntityGrid, {
  type EntityGridSelectionContext,
} from '@/components/common/EntityGrid';
import GridBadge from '@/components/common/GridBadge';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { AccountTreeIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { formatDate } from '@/utils/date';
import { UserAvatar } from '@/components/common/UserAvatar';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import type { ExplorerTestSetDetail } from '@/utils/api-client/interfaces/explorer';
import type { UserReference } from '@/utils/api-client/interfaces/tests';
import type { BulkDeleteActionsState } from '@/hooks/useBulkDelete';
import { explorerList } from './list';

export interface ExplorerBulkActionsState extends BulkDeleteActionsState {
  /** Export the selection to a regular test set; enabled for exactly one row. */
  onSave: () => void;
  saveDisabled: boolean;
}

interface ExplorerGridProps {
  canCreate?: boolean;
  onCreateClick?: () => void;
  onBulkActionsChange?: (actions: ExplorerBulkActionsState) => void;
  /** Bumped by the page after a create/import succeeds, to trigger a re-fetch. */
  refreshTrigger?: number;
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: ExplorerTestSetDetail[];
  initialTotalCount?: number;
}

function toFilters(state: { search: string }) {
  return { search: state.search };
}

/** Same name cascade the other grids use, so sorting and export match the cell. */
function userDisplayName(user?: UserReference): string {
  if (!user) return '';
  return (
    user.name ||
    `${user.given_name || ''} ${user.family_name || ''}`.trim() ||
    user.email ||
    ''
  );
}

export default function ExplorerGrid({
  canCreate,
  onCreateClick,
  onBulkActionsChange,
  refreshTrigger,
  initialData,
  initialTotalCount,
}: ExplorerGridProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const [isExporting, setIsExporting] = useState(false);

  const handleExportSelected = useCallback(
    async (selectedIds: string[]) => {
      if (selectedIds.length !== 1 || isExporting) return;

      setIsExporting(true);
      try {
        const client = new ApiClientFactory().getExplorerClient();
        const result = await client.exportRegularTestSetFromExplorer(
          selectedIds[0]
        );
        const { exported, skipped, test_set: created } = result;
        const parts = [
          `Created "${created.name}"`,
          `exported ${exported} test(s)`,
        ];
        if (skipped > 0) {
          parts.push(`skipped ${skipped}`);
        }
        notifications.show(parts.join('. '), {
          severity: 'success',
          autoHideDuration: 6000,
        });
        router.push(`/test-sets/${created.id}`);
      } catch (err) {
        notifications.show(
          err instanceof Error ? err.message : 'Failed to export test set.',
          { severity: 'error', autoHideDuration: 6000 }
        );
      } finally {
        setIsExporting(false);
      }
    },
    [notifications, router, isExporting]
  );

  const buildBulkActions = useCallback(
    (
      base: BulkDeleteActionsState,
      ctx: EntityGridSelectionContext<ExplorerTestSetDetail>
    ): ExplorerBulkActionsState => ({
      ...base,
      onSave: () => void handleExportSelected(ctx.selectedIds),
      saveDisabled: ctx.selectedIds.length !== 1,
    }),
    [handleExportSelected]
  );

  const columns = useMemo<GridColDef[]>(
    () => [
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
        sortable: false,
        valueGetter: (_, row) => row.status?.name || '',
        renderCell: params => {
          if (!params.value) return '-';
          return <GridBadge label={params.value} />;
        },
      },
      {
        field: 'created_at',
        headerName: 'Created',
        width: 160,
        renderCell: params => {
          if (!params.value) return '-';
          return (
            <Typography variant="body2">{formatDate(params.value)}</Typography>
          );
        },
      },
      {
        field: 'user',
        headerName: 'Creator',
        width: 160,
        minWidth: 120,
        sortable: false,
        valueGetter: (_, row) => userDisplayName(row.user),
        renderCell: params => {
          if (!params.value) return '-';
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <UserAvatar
                userName={params.value}
                userPicture={params.row.user?.picture}
                size={AVATAR_SIZES.SMALL}
              />
              <Typography variant="body2">{params.value}</Typography>
            </Box>
          );
        },
      },
    ],
    []
  );

  return (
    <EntityGrid<
      ExplorerTestSetDetail,
      typeof explorerList.filters,
      Record<string, never>,
      ExplorerBulkActionsState
    >
      descriptor={explorerList}
      columns={columns}
      toFilters={toFilters}
      emptyState={
        <EntityEmptyState
          card
          icon={AccountTreeIcon}
          title="No explorer sessions yet"
          description="Start a new session to explore requirements and generate tests, or load an existing test set."
          actionLabel={canCreate ? 'New session' : undefined}
          onAction={canCreate ? onCreateClick : undefined}
        />
      }
      initialData={initialData}
      initialTotalCount={initialTotalCount}
      refreshTrigger={refreshTrigger}
      searchPlaceholder="Search sessions…"
      selectionLabel="Select sessions"
      getRowUrl={row => `/explorer/${row.id}`}
      editAction={false}
      rowActionsWidth={56}
      onBulkActionsChange={onBulkActionsChange}
      buildBulkActions={buildBulkActions}
      pageSizeOptions={[10, 25, 50]}
    />
  );
}
