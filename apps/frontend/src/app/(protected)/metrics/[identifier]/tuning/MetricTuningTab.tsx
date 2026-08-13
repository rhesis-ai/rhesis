'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Tooltip,
  Typography,
} from '@mui/material';
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
import { AddIcon, PlayArrowIcon, TuneIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { UUID } from 'crypto';
import type { ScoreType } from '@/utils/api-client/interfaces/metric';
import type {
  MetricTuningCase,
  MetricTuningCaseCreate,
  MetricTuningRun,
} from '@/utils/api-client/interfaces/metric-tuning';
import MetricTuningCaseDialog from './MetricTuningCaseDialog';

/** How often to re-read a run that is still going. */
const RUN_POLL_INTERVAL_MS = 3000;

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

/**
 * What the metric said, to be read beside the verdict the author expected.
 *
 * A failed call is shown as an error rather than as a verdict — a flaky
 * provider must not read as a metric that disagrees.
 */
function MetricVerdictCell({
  params,
  scoreType,
}: {
  params: GridRenderCellParams;
  scoreType: ScoreType;
}) {
  const result = params.row.result as MetricTuningCase['result'];
  if (!result) return <span>—</span>;
  if (result.error) {
    return (
      <Tooltip title={result.error}>
        <Chip label="Error" size="small" color="warning" variant="outlined" />
      </Tooltip>
    );
  }
  if (!result.verdict) return <span>—</span>;
  if (scoreType !== 'binary') {
    return <Chip label={result.verdict} size="small" variant="outlined" />;
  }
  const isPass = result.verdict.toLowerCase() === 'pass';
  return (
    <Chip
      label={result.verdict}
      size="small"
      variant="outlined"
      color={isPass ? 'success' : 'error'}
    />
  );
}

/** The metric's own reasoning for the verdict it gave — what to edit against. */
function MetricReasoningCell({ params }: { params: GridRenderCellParams }) {
  const result = params.row.result as MetricTuningCase['result'];
  const value = result?.reasoning ?? '';
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

/** One line about the latest run, or nothing when there has not been one. */
function RunSummary({ run }: { run: MetricTuningRun | null }) {
  if (!run || run.status === 'never_run') return null;

  if (run.status === 'running') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <CircularProgress size={16} />
        <Typography variant="body2" color="text.secondary">
          Running the metric over {run.total_cases}{' '}
          {run.total_cases === 1 ? 'case' : 'cases'} — {run.completed_cases}{' '}
          done.
        </Typography>
      </Box>
    );
  }

  if (run.status === 'failed') {
    return (
      <Typography variant="body2" color="error" sx={{ mb: 1.5 }}>
        The last run failed{run.error ? `: ${run.error}` : '.'}
      </Typography>
    );
  }

  const finished = run.completed_at ? new Date(run.completed_at) : null;
  const errored =
    run.errored_cases > 0
      ? ` ${run.errored_cases} of them could not be reached.`
      : '';
  return (
    <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
      Last run {finished ? finished.toLocaleString() : ''} over{' '}
      {run.completed_cases} {run.completed_cases === 1 ? 'case' : 'cases'}.
      {errored}
    </Typography>
  );
}

/**
 * Marks a case that cannot be scored yet, and why. Shared visual language, but
 * kept apart: unlabelled is work to label, stale is work to re-label.
 */
function StatusCell({ params }: { params: GridRenderCellParams }) {
  if (params.row.is_stale === true) {
    return (
      <Tooltip title="This metric's score type changed after the case was written, so this verdict is no longer one the metric can return. Edit the case to fix it.">
        <Chip label="Stale" size="small" color="warning" variant="outlined" />
      </Tooltip>
    );
  }
  if (!params.row.expected) {
    return (
      <Tooltip title="This case has no expected verdict yet, so there is nothing to compare the metric against. Edit the case to give it one.">
        <Chip
          label="Unlabelled"
          size="small"
          color="warning"
          variant="outlined"
        />
      </Tooltip>
    );
  }
  return <span>—</span>;
}

export interface MetricTuningTabProps {
  metricId: string;
}

/**
 * Experimental: a metric's own set of labelled cases, and runs over them.
 *
 * Each case is an (input, output) pair plus the verdict a human expects from
 * this metric. Pressing Run metric runs it over every case and fills in what it
 * actually said, and why. One agreement number across the set is a later step;
 * seeing the divergence case by case is already what an author edits against.
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
  const [run, setRun] = useState<MetricTuningRun | null>(null);
  const [starting, setStarting] = useState(false);

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const factory = new ApiClientFactory();
      const [metric, tuningCases, tuningRun] = await Promise.all([
        factory.getMetricsClient().getMetric(metricId as UUID),
        factory.getMetricTuningClient().getTuningCases(metricId),
        factory.getMetricTuningClient().getTuningRun(metricId),
      ]);
      setScoreType(metric.score_type ?? 'binary');
      setMinScore(metric.min_score);
      setMaxScore(metric.max_score);
      setCategories(metric.categories);
      setCases(tuningCases);
      setRun(tuningRun);
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

  // A run in flight is polled until it stops. The cases are re-read with it,
  // since each finished case gains a verdict the grid should show.
  //
  // The interval keys off `run?.status` and nothing else. Depending on the whole
  // `run` object would restart the timer on every tick, and depending on
  // `fetchCases` — which polling itself replaces — would restart it on every
  // fetch. Nothing here ever starts a run: a poll that could start one would
  // turn opening the tab into an LLM bill.
  const runStatus = run?.status;
  useEffect(() => {
    if (runStatus !== 'running') return;

    const client = new ApiClientFactory().getMetricTuningClient();
    let cancelled = false;

    const poll = async () => {
      try {
        const [nextRun, nextCases] = await Promise.all([
          client.getTuningRun(metricId),
          client.getTuningCases(metricId),
        ]);
        if (cancelled) return;
        setRun(nextRun);
        setCases(nextCases);
      } catch {
        // A failed poll is not worth interrupting the author over — the next
        // tick tries again, and a genuinely broken run comes back as `failed`.
      }
    };

    const timer = setInterval(poll, RUN_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [metricId, runStatus]);

  const handleRun = useCallback(async () => {
    setStarting(true);
    try {
      const client = new ApiClientFactory().getMetricTuningClient();
      setRun(await client.startTuningRun(metricId));
    } catch (error) {
      notifications.show(
        error instanceof Error
          ? `Failed to start the run: ${error.message}`
          : 'Failed to start the run',
        { severity: 'error', autoHideDuration: 6000 }
      );
    } finally {
      setStarting(false);
    }
  }, [metricId, notifications]);

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
        headerName: 'Expected',
        width: 120,
        renderCell: params => (
          <ExpectedCell params={params} scoreType={scoreType} />
        ),
      },
      {
        // Sits next to `expected` on purpose: the two side by side are the
        // whole point of a run.
        field: 'metric_verdict',
        headerName: 'Metric said',
        width: 130,
        // Reads the nested `result`, which no single field sorts by.
        sortable: false,
        renderCell: params => (
          <MetricVerdictCell params={params} scoreType={scoreType} />
        ),
      },
      {
        field: 'metric_reasoning',
        headerName: 'Because',
        flex: 1.5,
        minWidth: 180,
        sortable: false,
        renderCell: params => <MetricReasoningCell params={params} />,
      },
      {
        field: 'is_stale',
        headerName: 'Status',
        width: 130,
        // Reads two fields, so no single one sorts it — sorting by `is_stale`
        // alone would scatter the unlabelled rows through the unmarked ones.
        sortable: false,
        renderCell: params => <StatusCell params={params} />,
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
  const isRunning = run?.status === 'running';
  const actions = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
      <BetaBadge />
      {canEdit && cases.length > 0 && (
        <Button
          variant="outlined"
          startIcon={<PlayArrowIcon />}
          onClick={handleRun}
          disabled={isRunning || starting}
        >
          {isRunning ? 'Running…' : 'Run metric'}
        </Button>
      )}
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
            description="Add an input and the answer it produced. The verdict you expect from this metric can come later."
            actionLabel={canEdit ? 'Add case' : undefined}
            onAction={canEdit ? openAdd : undefined}
            showAddIcon
          />
        ) : (
          <>
            <RunSummary run={run} />
            <BaseDataGrid
              rows={cases as unknown as GridRowModel[]}
              columns={columns}
              loading={loading}
              getRowId={row => String(row.id)}
              showToolbar={false}
              disableMultipleRowSelection
            />
          </>
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
