'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Button, Chip, Tooltip } from '@mui/material';
import {
  GridColDef,
  GridRenderCellParams,
  GridRowModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import SectionCard from '@/components/common/SectionCard';
import SectionEmptyState from '@/components/common/SectionEmptyState';
import { BetaBadge } from '@/components/common/BetaBadge';
import { createRowActionsColumn } from '@/components/common/createRowActionsColumn';
import { useNotifications } from '@/components/common/NotificationContext';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { AddIcon, TuneIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { UUID } from 'crypto';
import type { ScoreType } from '@/utils/api-client/interfaces/metric';
import type {
  MetricTuningCase,
  MetricTuningCaseCreate,
} from '@/utils/api-client/interfaces/metric-tuning';
import MetricTuningCaseDialog from './MetricTuningCaseDialog';

/** Renders long free text on one line with the full value in a tooltip. */
function TruncatedCell({ params }: { params: GridRenderCellParams }) {
  const value = typeof params.value === 'string' ? params.value : '';
  return (
    <Box
      title={value}
      sx={{
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}
    >
      {value || '—'}
    </Box>
  );
}

/**
 * The expected verdict, rendered according to the metric's score type.
 *
 * Only a binary verdict is a pass/fail judgement worth colouring. Rendering a
 * numeric "0.8" as a red chip — which is what a blanket `=== 'pass'` check does
 * — says the opposite of what the number means.
 */
function ExpectedCell({
  params,
  scoreType,
}: {
  params: GridRenderCellParams;
  scoreType: ScoreType;
}) {
  const value = typeof params.value === 'string' ? params.value : '';
  if (!value) return <span>—</span>;
  if (scoreType !== 'binary') {
    return <Chip label={value} size="small" variant="outlined" />;
  }
  const isPass = value.toLowerCase() === 'pass';
  return (
    <Chip
      label={value}
      size="small"
      variant="outlined"
      color={isPass ? 'success' : 'error'}
    />
  );
}

/** Marks a case whose verdict no longer fits the metric's current score type. */
function StaleCell({ params }: { params: GridRenderCellParams }) {
  if (params.value !== true) return <span>—</span>;
  return (
    <Tooltip title="This metric's score type changed after the case was written, so this verdict is no longer one the metric can return. Edit the case to fix it.">
      <Chip label="Stale" size="small" color="warning" variant="outlined" />
    </Tooltip>
  );
}

export interface MetricTuningTabProps {
  metricId: string;
}

/**
 * Experimental: a metric's own set of labelled cases.
 *
 * Each case is an (input, output) pair plus the verdict a human expects from
 * this metric. Scoring the set against the metric is a later step; for now the
 * tab is about collecting the cases.
 *
 * The metric is fetched here rather than passed in: the tabs component holds
 * only the id, and threading the whole metric through it would couple this
 * feature to a component that otherwise knows nothing about it.
 */
export default function MetricTuningTab({ metricId }: MetricTuningTabProps) {
  const notifications = useNotifications();
  const canEdit = useCan(Capability.Metric.UPDATE);

  const [cases, setCases] = useState<MetricTuningCase[]>([]);
  const [scoreType, setScoreType] = useState<ScoreType>('binary');
  const [minScore, setMinScore] = useState<number | undefined>();
  const [maxScore, setMaxScore] = useState<number | undefined>();
  const [categories, setCategories] = useState<string[] | undefined>();
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<MetricTuningCase | null>(null);

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const factory = new ApiClientFactory();
      const [metric, tuningCases] = await Promise.all([
        factory.getMetricsClient().getMetric(metricId as UUID),
        factory.getMetricTuningClient().getTuningCases(metricId),
      ]);
      setScoreType(metric.score_type ?? 'binary');
      setMinScore(metric.min_score);
      setMaxScore(metric.max_score);
      setCategories(metric.categories);
      setCases(tuningCases);
    } catch (error) {
      notifications.show(
        error instanceof Error
          ? `Failed to load tuning cases: ${error.message}`
          : 'Failed to load tuning cases',
        { severity: 'error', autoHideDuration: 6000 }
      );
      setCases([]);
    } finally {
      setLoading(false);
    }
  }, [metricId, notifications]);

  useEffect(() => {
    fetchCases();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- notifications identity changes each render
  }, [metricId]);

  const handleSubmit = useCallback(
    async (data: MetricTuningCaseCreate) => {
      const client = new ApiClientFactory().getMetricTuningClient();
      if (editing) {
        await client.updateTuningCase(metricId, editing.id, data);
      } else {
        await client.createTuningCase(metricId, data);
      }
      await fetchCases();
      notifications.show(editing ? 'Case updated' : 'Case added', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    },
    [editing, metricId, fetchCases, notifications]
  );

  const handleDelete = useCallback(
    async (caseId: string) => {
      try {
        const client = new ApiClientFactory().getMetricTuningClient();
        await client.deleteTuningCase(metricId, caseId);
        setCases(prev => prev.filter(c => String(c.id) !== caseId));
        notifications.show('Case removed', {
          severity: 'success',
          autoHideDuration: 4000,
        });
      } catch (error) {
        notifications.show(
          error instanceof Error
            ? `Failed to remove case: ${error.message}`
            : 'Failed to remove case',
          { severity: 'error', autoHideDuration: 6000 }
        );
      }
    },
    [metricId, notifications]
  );

  const openAdd = useCallback(() => {
    setEditing(null);
    setDialogOpen(true);
  }, []);

  const openEdit = useCallback(
    (caseId: string) => {
      setEditing(cases.find(c => String(c.id) === caseId) ?? null);
      setDialogOpen(true);
    },
    [cases]
  );

  const columns = useMemo<GridColDef[]>(
    () => [
      {
        field: 'input',
        headerName: 'Input',
        flex: 1,
        minWidth: 180,
        renderCell: params => <TruncatedCell params={params} />,
      },
      {
        field: 'output',
        headerName: 'Output',
        flex: 2,
        minWidth: 220,
        renderCell: params => <TruncatedCell params={params} />,
      },
      {
        field: 'expected_output',
        headerName: 'Expected output',
        flex: 1,
        minWidth: 160,
        renderCell: params => <TruncatedCell params={params} />,
      },
      {
        field: 'expected',
        headerName: 'Verdict',
        width: 120,
        renderCell: params => (
          <ExpectedCell params={params} scoreType={scoreType} />
        ),
      },
      {
        field: 'is_stale',
        headerName: 'Status',
        width: 100,
        renderCell: params => <StaleCell params={params} />,
      },
      {
        field: 'rationale',
        headerName: 'Why',
        flex: 1.5,
        minWidth: 180,
        renderCell: params => <TruncatedCell params={params} />,
      },
      createRowActionsColumn({
        canEdit: () => canEdit,
        canDelete: () => canEdit,
        onEdit: id => openEdit(id),
        onDelete: id => handleDelete(id),
      }),
    ],
    [canEdit, openEdit, handleDelete, scoreType]
  );

  // The badge sits in `actions`, not `subtitle`: SectionCard wraps the subtitle
  // in a <Typography> (a <p>), and Chip renders a <div>.
  const actions = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
      <BetaBadge />
      {canEdit && (
        <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>
          Add case
        </Button>
      )}
    </Box>
  );

  return (
    <>
      <SectionCard
        title="Tuning"
        subtitle="Labelled cases for checking whether this metric scores the way you would."
        actions={actions}
      >
        {!loading && cases.length === 0 ? (
          <SectionEmptyState
            icon={TuneIcon}
            title="No tuning cases yet"
            description="Add an input, the answer it produced, and the verdict you expect from this metric."
            actionLabel={canEdit ? 'Add case' : undefined}
            onAction={canEdit ? openAdd : undefined}
            showAddIcon
          />
        ) : (
          <BaseDataGrid
            rows={cases as unknown as GridRowModel[]}
            columns={columns}
            loading={loading}
            getRowId={row => String(row.id)}
            showToolbar={false}
            disableMultipleRowSelection
          />
        )}
      </SectionCard>

      <MetricTuningCaseDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        tuningCase={editing}
        scoreType={scoreType}
        minScore={minScore}
        maxScore={maxScore}
        categories={categories}
        onSubmit={handleSubmit}
      />
    </>
  );
}
