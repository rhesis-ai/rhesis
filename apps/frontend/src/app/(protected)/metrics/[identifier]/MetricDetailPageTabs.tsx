'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Box, Paper, Typography } from '@mui/material';
import { useSession } from 'next-auth/react';
import { GridColDef } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import DetailTabNav from '@/components/common/DetailTabNav';
import {
  createRowActionsColumn,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
import { RouteIcon } from '@/components/icons';
import { MetricDetailView } from './MetricDetailView';
import { MetricsClient } from '@/utils/api-client/metrics-client';
import type { BehaviorReference } from '@/utils/api-client/interfaces/behavior';
import type { UUID } from 'crypto';

const TAB_KEYS = ['basic', 'linked-behaviors'] as const;

const NAV_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  basic: 'Basic Information',
  'linked-behaviors': 'Linked Behaviors',
};

export default function MetricDetailPageTabs() {
  const params = useParams();
  const { data: session } = useSession();

  const metricId = params.identifier as string;
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label: NAV_LABELS[key],
    id: `metric-detail-tab-${index}`,
    'aria-controls': `metric-detail-tabpanel-${index}`,
  }));

  const sessionToken = session?.session_token ?? '';

  const tabNav = (
    <DetailTabNav
      tabs={navTabs}
      activeIndex={activeTab}
      onChange={handleTabChange}
      aria-label="Metric detail tabs"
    />
  );

  return (
    <MetricDetailView
      metricId={metricId}
      mode="page"
      tabNav={tabNav}
      tabBody={
        activeTab === 1 ? (
          <MetricLinkedBehaviors
            metricId={metricId}
            sessionToken={sessionToken}
          />
        ) : undefined
      }
    />
  );
}

function MetricLinkedBehaviors({
  metricId,
  sessionToken,
}: {
  metricId: string;
  sessionToken: string;
}) {
  const router = useRouter();
  const [behaviors, setBehaviors] = useState<BehaviorReference[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionToken) return;
    const fetchData = async () => {
      try {
        setLoading(true);
        const client = new MetricsClient(sessionToken);
        const result = await client.getMetricBehaviors(metricId as UUID);
        const data =
          (result as unknown as { data: BehaviorReference[] }).data ?? [];
        setBehaviors(data);
      } catch {
        setBehaviors([]);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [metricId, sessionToken]);

  const handleUnassign = useCallback(
    async (behaviorId: string) => {
      try {
        const client = new MetricsClient(sessionToken);
        await client.removeBehaviorFromMetric(
          metricId as UUID,
          behaviorId as UUID
        );
        setBehaviors(prev => prev.filter(b => b.id !== behaviorId));
      } catch {
        // ignore
      }
    },
    [metricId, sessionToken]
  );

  const columns: GridColDef<BehaviorReference>[] = useMemo(
    () => [
      { field: 'name', headerName: 'Name', flex: 1, minWidth: 160 },
      {
        field: 'description',
        headerName: 'Description',
        flex: 2,
        minWidth: 200,
        renderCell: params => (
          <Box
            title={params.value ?? ''}
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {params.value || '—'}
          </Box>
        ),
      },
      createRowActionsColumn({
        onDelete: id => handleUnassign(id),
        deleteTooltip: 'Unassign',
      }),
    ],
    [handleUnassign]
  );

  const isEmpty = !loading && behaviors.length === 0;

  return (
    <>
      {isEmpty ? (
        <Paper elevation={1} sx={{ p: 3 }}>
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
            <RouteIcon sx={{ fontSize: 32, color: 'primary.main' }} />
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              No behaviors assigned yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              No behaviors have been assigned to this metric yet. Navigate to
              Behaviors to assign a behavior to start linking it to this metric.
            </Typography>
          </Box>
        </Paper>
      ) : (
        <Paper elevation={1} sx={{ p: 3 }}>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: 2,
            }}
          >
            <Typography
              variant="h6"
              sx={{ fontWeight: 600, color: 'primary.main' }}
            >
              Linked Behaviors ({behaviors.length})
            </Typography>
          </Box>
          <BaseDataGrid
            rows={behaviors}
            columns={columns}
            loading={loading}
            getRowId={row => row.id}
            onRowClick={params =>
              router.push(`/behaviors/${String(params.id)}`)
            }
            pageSizeOptions={[5, 10, 25]}
            disableRowSelectionOnClick
            disablePaperWrapper={true}
            sx={rowActionsHoverSx}
          />
        </Paper>
      )}
    </>
  );
}
