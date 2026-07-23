'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Typography } from '@mui/material';
import {
  GridColDef,
  GridRenderCellParams,
  GridRowModel,
} from '@mui/x-data-grid';
import GridBadge from '@/components/common/GridBadge';
import LinkedEntitiesGrid from '@/components/common/LinkedEntitiesGrid';
import { useNotifications } from '@/components/common/NotificationContext';
import type { ToolbarPillTab } from '@/components/common/GridToolbar';
import { DescriptionIcon, ErrorIcon } from '@/components/icons';
import { useRouter } from 'next/navigation';
import type { BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import { TestsClient } from '@/utils/api-client/tests-client';
import {
  getTestDisplayContent,
  renderTestContentCell,
} from '@/app/(protected)/tests/components/test-grid-helpers';
import { TEST_TYPE_PILL_TABS } from '@/constants/test-types';

interface BehaviorLinkedTestsProps {
  behavior: BehaviorWithMetrics;
}

function escapeODataValue(value: string): string {
  return value.replace(/'/g, "''");
}

export default function BehaviorLinkedTests({
  behavior,
}: BehaviorLinkedTestsProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const [tests, setTests] = useState<TestDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [typePill, setTypePill] = useState('all');

  const fetchLinked = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const client = new TestsClient();
      const result = await client.getAllTests({
        filter: `behavior_id eq '${escapeODataValue(String(behavior.id))}'`,
        sort_by: 'created_at',
        sort_order: 'desc',
      });
      setTests(result);
    } catch (error) {
      setLoadError(true);
      setTests([]);
      notifications.show(
        error instanceof Error
          ? `Failed to load linked tests: ${error.message}`
          : 'Failed to load linked tests',
        { severity: 'error', autoHideDuration: 6000 }
      );
    } finally {
      setLoading(false);
    }
  }, [behavior.id, notifications]);

  useEffect(() => {
    fetchLinked();
  }, [fetchLinked]);

  const rows = useMemo<GridRowModel[]>(
    () =>
      tests.map(test => ({
        ...test,
        // LinkedEntitiesGrid search matches `name` / `description`
        name: getTestDisplayContent(test),
      })),
    [tests]
  );

  const linkedColumns = useMemo<GridColDef[]>(
    () => [
      {
        field: 'content',
        headerName: 'Content',
        flex: 2,
        minWidth: 200,
        valueGetter: (_value: unknown, row: TestDetail) =>
          getTestDisplayContent(row),
        renderCell: renderTestContentCell,
      },
      {
        field: 'test_type',
        headerName: 'Test Type',
        width: 130,
        valueGetter: (_value: unknown, row: TestDetail) =>
          row.test_type?.type_value ?? '',
        renderCell: (params: GridRenderCellParams) =>
          typeof params.value === 'string' && params.value ? (
            <GridBadge size="detail" label={params.value} />
          ) : null,
      },
      {
        field: 'category',
        headerName: 'Category',
        width: 140,
        valueGetter: (_value: unknown, row: TestDetail) =>
          row.category?.name ?? '',
        renderCell: (params: GridRenderCellParams) =>
          typeof params.value === 'string' && params.value ? (
            <GridBadge size="detail" label={params.value} />
          ) : null,
      },
      {
        field: 'topic',
        headerName: 'Topic',
        width: 140,
        valueGetter: (_value: unknown, row: TestDetail) =>
          row.topic?.name ?? '',
        renderCell: (params: GridRenderCellParams) =>
          typeof params.value === 'string' && params.value ? (
            <GridBadge size="detail" label={params.value} />
          ) : null,
      },
    ],
    []
  );

  const pillTabs: ToolbarPillTab[] = TEST_TYPE_PILL_TABS;

  const rowFilter = useCallback(
    (row: GridRowModel) => {
      if (typePill === 'all') return true;
      const testType =
        (row.test_type as { type_value?: string } | null | undefined)
          ?.type_value ?? '';
      return testType === typePill;
    },
    [typePill]
  );

  return (
    <LinkedEntitiesGrid
      title="Linked Tests"
      rows={rows}
      columns={linkedColumns}
      loading={loading}
      getRowId={row => String(row.id)}
      onRowClick={params => router.push(`/tests/${String(params.id)}`)}
      searchPlaceholder="Search tests…"
      rowFilter={rowFilter}
      pillTabs={pillTabs}
      activePill={typePill}
      onPillChange={setTypePill}
      emptyState={
        loadError ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              py: 5,
              gap: 2,
              textAlign: 'center',
            }}
          >
            <ErrorIcon sx={{ fontSize: 32, color: 'error.main' }} />
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              Couldn't load linked tests
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Something went wrong while loading tests for this behavior. Try
              refreshing the page.
            </Typography>
          </Box>
        ) : (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              py: 5,
              gap: 2,
              textAlign: 'center',
            }}
          >
            <DescriptionIcon sx={{ fontSize: 32, color: 'primary.main' }} />
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              No tests linked yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              No tests have this behavior assigned yet. Assign this behavior
              when creating or editing a test to see it here.
            </Typography>
          </Box>
        )
      }
    />
  );
}
