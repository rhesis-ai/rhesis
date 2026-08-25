'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Grid,
  IconButton,
  Tooltip,
  Typography,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  GridColDef,
  GridColumnGroupingModel,
  GridRenderCellParams,
  GridRowModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import SectionCard from '@/components/common/SectionCard';
import SectionEmptyState from '@/components/common/SectionEmptyState';
import GridBadge from '@/components/common/GridBadge';
import SummaryCard from '@/components/common/SummaryCard';
import {
  createRowActionsColumn,
  rowActionsHoverSx,
} from '@/components/common/createRowActionsColumn';
import { useNotifications } from '@/components/common/NotificationContext';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import {
  AddIcon,
  CancelIcon,
  CheckCircleIcon,
  PlayArrowIcon,
  ThumbDownFilledIcon,
  ThumbDownIcon,
  ThumbUpFilledIcon,
  ThumbUpIcon,
  TuneIcon,
  WarningAmberIcon,
} from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { UUID } from 'crypto';
import type { ScoreType } from '@/utils/api-client/interfaces/metric';
import type {
  MetricTuningAgreement,
  MetricTuningCase,
  MetricTuningCaseCreate,
  MetricTuningRun,
} from '@/utils/api-client/interfaces/metric-tuning';
import MetricTuningCaseDialog from './MetricTuningCaseDialog';
import MetricTuningRejectDialog from './MetricTuningRejectDialog';

/** How often to re-read a run that is still going. */
const RUN_POLL_INTERVAL_MS = 3000;

const ACCEPTED_HINT = 'You accepted this verdict. Press again to re-accept it.';

const REJECTED_HINT = 'You rejected this verdict.';

const INVALIDATED_HINT =
  "The metric's verdict crossed its threshold, or its score type changed, since this case was reviewed — the old judgement no longer applies, so it needs a fresh look.";

const ERRORED_HINT =
  'The metric call failed for this case, so there is no verdict to judge.';

const NO_AGREEMENT_HINT =
  'Agreement is the share of judged cases you accepted. Nothing has been judged yet, so there is no share to report — a set nobody has looked at is not a set the metric got right.';

/** Two-line clamp for free text in a grid cell, as the test run grids use. */
const CELL_TEXT_SX = {
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  display: '-webkit-box',
  WebkitLineClamp: 2,
  WebkitBoxOrient: 'vertical' as const,
};

/** Renders long free text clamped to two lines, in full in a tooltip. */
function TextCell({ value }: { value: string }) {
  if (!value) return <span>—</span>;
  return (
    <Tooltip title={value} enterDelay={500}>
      <Typography variant="body2" sx={CELL_TEXT_SX}>
        {value}
      </Typography>
    </Tooltip>
  );
}

function TruncatedCell({ params }: { params: GridRenderCellParams }) {
  return (
    <TextCell value={typeof params.value === 'string' ? params.value : ''} />
  );
}

/**
 * What the metric said, which is what the reviewer judges.
 *
 * A failed call is shown as an error rather than as a verdict — a flaky
 * provider must not read as a metric that got the case wrong. Only a binary
 * verdict is a pass/fail judgement worth colouring: rendering a numeric "0.8"
 * as a red chip says the opposite of what the number means.
 */
function MetricVerdictCell({
  params,
  scoreType,
}: {
  params: GridRenderCellParams;
  scoreType: ScoreType;
}) {
  const theme = useTheme();
  const result = params.row.result as MetricTuningCase['result'];
  if (!result) return <span>—</span>;

  const tinted = (label: string, tone: 'success' | 'error' | 'warning') => (
    <GridBadge
      label={label}
      sx={{
        bgcolor: alpha(theme.palette[tone].main, 0.12),
        color: `${tone}.dark`,
      }}
    />
  );

  if (result.error) {
    return (
      <Tooltip title={result.error}>
        <Box component="span" sx={{ display: 'inline-flex' }}>
          {tinted('Error', 'warning')}
        </Box>
      </Tooltip>
    );
  }
  if (!result.verdict) return <span>—</span>;
  // Untinted, so a numeric 0.8 is not painted red for being below 1.
  if (scoreType !== 'binary') {
    return <GridBadge label={result.verdict} />;
  }
  const isPass = result.verdict.toLowerCase() === 'pass';
  return tinted(result.verdict, isPass ? 'success' : 'error');
}

/** The metric's own reasoning for the verdict it gave — what to edit against. */
function MetricReasoningCell({ params }: { params: GridRenderCellParams }) {
  const result = params.row.result as MetricTuningCase['result'];
  return <TextCell value={result?.reasoning ?? ''} />;
}

/**
 * The judgement that stands for this case, and the two buttons that change it.
 *
 * The thumbs are the state as well as the control: the one that was pressed is
 * filled and coloured, the other stays faint. A chip saying "Accepted" beside a
 * green thumb says the same thing twice.
 *
 * They stay on a judged row on purpose — reading a case and re-judging it are
 * the same moment, and a mis-click has to be correctable where it happened.
 */
function ReviewCell({
  params,
  canEdit,
  onAccept,
  onReject,
}: {
  params: GridRenderCellParams;
  canEdit: boolean;
  onAccept: (tuningCase: MetricTuningCase) => void;
  onReject: (tuningCase: MetricTuningCase) => void;
}) {
  const tuningCase = params.row as MetricTuningCase;
  const { result, outcome, review } = tuningCase;

  if (!result) return <span>—</span>;

  // Nothing to judge, and nothing the reviewer can do about it — the verdict
  // column already carries the error itself.
  if (outcome === 'errored') {
    return (
      <Box component="span" title={result.error ?? ERRORED_HINT}>
        —
      </Box>
    );
  }

  const accepted = outcome === 'accepted';
  const rejected = outcome === 'rejected';
  const invalidated = tuningCase.unreviewed_reason === 'invalidated';

  if (!canEdit || !result.verdict) {
    // Read-only: the mark alone, since there is no button to be the state.
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        {invalidated && <InvalidatedMark />}
        {accepted && <ThumbUpFilledIcon fontSize="small" color="success" />}
        {rejected && (
          <Tooltip title={review?.comment ?? ''}>
            <ThumbDownFilledIcon fontSize="small" color="error" />
          </Tooltip>
        )}
        {!accepted && !rejected && <span>—</span>}
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
      {invalidated && <InvalidatedMark />}
      <Tooltip title={accepted ? ACCEPTED_HINT : 'The metric got this right'}>
        <IconButton
          size="small"
          aria-label="Accept this verdict"
          // A toggle, so the recorded judgement is readable to a screen reader
          // as well as visible in the fill.
          aria-pressed={accepted}
          color={accepted ? 'success' : 'default'}
          sx={{ opacity: accepted ? 1 : 0.55 }}
          onClick={() => onAccept(tuningCase)}
        >
          {accepted ? (
            <ThumbUpFilledIcon fontSize="small" />
          ) : (
            <ThumbUpIcon fontSize="small" />
          )}
        </IconButton>
      </Tooltip>
      <Tooltip
        title={
          rejected
            ? (review?.comment ?? REJECTED_HINT)
            : 'The metric got this wrong — say why'
        }
      >
        <IconButton
          size="small"
          aria-label="Reject this verdict"
          aria-pressed={rejected}
          color={rejected ? 'error' : 'default'}
          sx={{ opacity: rejected ? 1 : 0.55 }}
          onClick={() => onReject(tuningCase)}
        >
          {rejected ? (
            <ThumbDownFilledIcon fontSize="small" />
          ) : (
            <ThumbDownIcon fontSize="small" />
          )}
        </IconButton>
      </Tooltip>
    </Box>
  );
}

/** Says a review was taken away, which is not the same as never having one. */
function InvalidatedMark() {
  return (
    <Tooltip title={INVALIDATED_HINT}>
      <WarningAmberIcon
        fontSize="small"
        color="warning"
        aria-label="Review invalidated"
      />
    </Tooltip>
  );
}

/**
 * The metric's agreement, and the counts that stop it being read as more than
 * it is.
 *
 * The denominator is the whole point. Unreviewed and errored cases are counted
 * out of the ratio and reported in their own tile: counting either one in
 * produces a plausible figure meaning something other than what its reader
 * thinks — a set nobody looked at reading as perfect, or a flaky provider
 * reading as a bad metric. The judged count sits under the number for the same
 * reason, so three out of three does not read like a solved problem.
 */
function AgreementSummary({ agreement }: { agreement: MetricTuningAgreement }) {
  const { ratio, judged, accepted, rejected, unreviewed, errored } = agreement;
  const total = judged + unreviewed + errored;
  const percent = ratio === null ? null : Math.round(ratio * 100);

  const outstanding = [
    unreviewed > 0 ? `${unreviewed} unreviewed` : null,
    errored > 0 ? `${errored} the metric could not be reached on` : null,
  ].filter(Boolean);

  return (
    <Grid container spacing={3} sx={{ mb: 3 }}>
      <Grid size={{ xs: 12, sm: 6, md: 4 }}>
        <Box title={percent === null ? NO_AGREEMENT_HINT : undefined}>
          <SummaryCard
            title="Agreement"
            value={percent === null ? '—' : `${percent}%`}
            subtitle={
              percent === null
                ? 'Nothing judged yet'
                : `${accepted} of ${judged} ${judged === 1 ? 'case' : 'cases'} accepted`
            }
            icon={
              percent === null ? (
                <TuneIcon />
              ) : percent > 66 ? (
                <CheckCircleIcon />
              ) : percent >= 33 ? (
                <WarningAmberIcon />
              ) : (
                <CancelIcon />
              )
            }
            color={
              percent === null
                ? 'info'
                : percent > 66
                  ? 'success'
                  : percent >= 33
                    ? 'warning'
                    : 'error'
            }
          />
        </Box>
      </Grid>
      <Grid size={{ xs: 12, sm: 6, md: 4 }}>
        <SummaryCard
          title="Rejected"
          value={rejected}
          subtitle={`of ${judged} judged`}
          icon={<CancelIcon />}
          color="error"
        />
      </Grid>
      <Grid size={{ xs: 12, sm: 6, md: 4 }}>
        <SummaryCard
          title="Cases"
          value={total}
          subtitle={
            outstanding.length > 0 ? outstanding.join(' · ') : 'All judged'
          }
          icon={<TuneIcon />}
          color="primary"
        />
      </Grid>
    </Grid>
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

export interface MetricTuningTabProps {
  metricId: string;
}

/**
 * Experimental: a metric's own set of cases, runs over them, and the reviews.
 *
 * Each case is an input plus the answer the metric has to judge — it records no
 * expected verdict, because nothing is compared for equality. Pressing Run
 * metric fills in what the metric said and why; a reviewer then goes down the
 * rows accepting what it got right and rejecting the rest with a comment. Those
 * comments are what someone reads when rewriting the evaluation prompt.
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
  const [groundTruthRequired, setGroundTruthRequired] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<MetricTuningCase | null>(null);
  const [rejecting, setRejecting] = useState<MetricTuningCase | null>(null);
  const [run, setRun] = useState<MetricTuningRun | null>(null);
  const [starting, setStarting] = useState(false);
  const [acceptingRest, setAcceptingRest] = useState(false);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });

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
      setGroundTruthRequired(metric.ground_truth_required === true);
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

  // Agreement is derived from the reviews, so judging a case moves it without a
  // run. Re-read rather than recomputed here: one fold, on the server, is what
  // stops the number and the rows it is folded from ever disagreeing.
  const refreshRun = useCallback(async () => {
    try {
      const client = new ApiClientFactory().getMetricTuningClient();
      setRun(await client.getTuningRun(metricId));
    } catch {
      // The line keeps its last value; the next review or poll corrects it.
    }
  }, [metricId]);

  /** Swaps in the case the review endpoint returns, leaving the rest alone. */
  const replaceCase = useCallback((updated: MetricTuningCase) => {
    setCases(prev =>
      prev.map(c => (String(c.id) === String(updated.id) ? updated : c))
    );
  }, []);

  const handleAccept = useCallback(
    async (tuningCase: MetricTuningCase) => {
      try {
        const client = new ApiClientFactory().getMetricTuningClient();
        replaceCase(
          await client.reviewTuningCase(metricId, tuningCase.id, {
            decision: 'accepted',
          })
        );
        await refreshRun();
      } catch (error) {
        notifications.show(
          error instanceof Error
            ? `Failed to save the review: ${error.message}`
            : 'Failed to save the review',
          { severity: 'error', autoHideDuration: 6000 }
        );
      }
    },
    [metricId, notifications, refreshRun, replaceCase]
  );

  // Throws on failure so the dialog keeps the comment on screen — a rejection
  // whose text is lost to a network blip is the one thing that must not happen.
  const handleReject = useCallback(
    async (comment: string) => {
      if (!rejecting) return;
      const client = new ApiClientFactory().getMetricTuningClient();
      replaceCase(
        await client.reviewTuningCase(metricId, rejecting.id, {
          decision: 'rejected',
          comment,
        })
      );
      await refreshRun();
    },
    [metricId, refreshRun, rejecting, replaceCase]
  );

  const handleAcceptRest = useCallback(async () => {
    setAcceptingRest(true);
    try {
      const client = new ApiClientFactory().getMetricTuningClient();
      setCases(await client.acceptRemainingTuningCases(metricId));
      await refreshRun();
      notifications.show('Accepted every case left unreviewed', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (error) {
      notifications.show(
        error instanceof Error
          ? `Failed to accept the rest: ${error.message}`
          : 'Failed to accept the rest',
        { severity: 'error', autoHideDuration: 6000 }
      );
    } finally {
      setAcceptingRest(false);
    }
  }, [metricId, notifications, refreshRun]);

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

  // A column nothing fills is a column nobody can read anything from, so it is
  // left out rather than shown empty down every row.
  const hasReferenceAnswer = cases.some(c => Boolean(c.reference_answer));
  const hasReasoning = cases.some(c => Boolean(c.result?.reasoning));
  const hasResults = cases.some(c => c.result !== null);

  const columns = useMemo<GridColDef[]>(() => {
    const caseColumns: GridColDef[] = [
      {
        field: 'input',
        headerName: 'Input',
        flex: 1,
        minWidth: 180,
        disableColumnMenu: true,
        renderCell: params => <TruncatedCell params={params} />,
      },
      {
        field: 'output',
        headerName: 'Output',
        flex: 2,
        minWidth: 220,
        disableColumnMenu: true,
        renderCell: params => <TruncatedCell params={params} />,
      },
    ];
    if (hasReferenceAnswer) {
      caseColumns.push({
        field: 'reference_answer',
        headerName: 'Reference answer',
        flex: 1,
        minWidth: 160,
        disableColumnMenu: true,
        renderCell: params => <TruncatedCell params={params} />,
      });
    }

    const runColumns: GridColDef[] = [];
    if (hasResults) {
      runColumns.push({
        field: 'metric_verdict',
        headerName: 'Metric verdict',
        width: 140,
        // Reads the nested `result`, which no single field sorts by.
        sortable: false,
        disableColumnMenu: true,
        align: 'center',
        headerAlign: 'center',
        renderCell: params => (
          <MetricVerdictCell params={params} scoreType={scoreType} />
        ),
      });
      if (hasReasoning) {
        runColumns.push({
          field: 'metric_reasoning',
          headerName: 'Reasoning',
          flex: 1.5,
          minWidth: 180,
          sortable: false,
          disableColumnMenu: true,
          renderCell: params => <MetricReasoningCell params={params} />,
        });
      }
    }

    const reviewColumns: GridColDef[] = hasResults
      ? [
          {
            field: 'review',
            headerName: 'Review',
            width: 120,
            // The cell reads `outcome`, `review` and `result` together.
            sortable: false,
            disableColumnMenu: true,
            align: 'center',
            headerAlign: 'center',
            renderCell: params => (
              <ReviewCell
                params={params}
                canEdit={canEdit}
                onAccept={handleAccept}
                onReject={setRejecting}
              />
            ),
          },
        ]
      : [];

    return [
      ...caseColumns,
      ...runColumns,
      ...reviewColumns,
      createRowActionsColumn({
        canEdit: () => canEdit,
        canDelete: () => canEdit,
        onEdit: id => openEdit(id),
        onDelete: id => handleDelete(id),
      }),
    ];
  }, [
    canEdit,
    openEdit,
    handleDelete,
    handleAccept,
    scoreType,
    hasReferenceAnswer,
    hasReasoning,
    hasResults,
  ]);

  // Three groups, read left to right: the case, what this run said about it,
  // and what the reviewer made of that.
  const columnGroupingModel = useMemo<GridColumnGroupingModel>(() => {
    const groups: GridColumnGroupingModel = [
      {
        groupId: 'case',
        headerName: 'Case',
        children: [
          { field: 'input' },
          { field: 'output' },
          ...(hasReferenceAnswer ? [{ field: 'reference_answer' }] : []),
        ],
      },
    ];
    if (hasResults) {
      groups.push({
        groupId: 'metric_output',
        // "Output" also names the answer being judged, one band to the left —
        // a deliberate departure from the spec's `This run`, chosen on review.
        headerName: 'Metric output',
        children: [
          { field: 'metric_verdict' },
          ...(hasReasoning ? [{ field: 'metric_reasoning' }] : []),
        ],
      });
      // No group over the review column: a band reading "Review" above a column
      // reading "Review" labels one thing twice.
    }
    return groups;
  }, [hasReferenceAnswer, hasReasoning, hasResults]);

  const unreviewedWithVerdict = cases.some(
    c => c.outcome === 'unreviewed' && Boolean(c.result?.verdict)
  );

  const isRunning = run?.status === 'running';
  const actions = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
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
        <Button
          variant="outlined"
          startIcon={<ThumbUpIcon />}
          onClick={handleAcceptRest}
          disabled={!unreviewedWithVerdict || acceptingRest}
        >
          Accept the rest
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
        subtitle="Cases for checking whether this metric judges the way you would."
        actions={actions}
      >
        {!loading && cases.length === 0 ? (
          <SectionEmptyState
            icon={TuneIcon}
            title="No tuning cases yet"
            description="Add an input and the answer this metric has to judge. Run the metric, then say whether what it came back with was right."
            actionLabel={canEdit ? 'Add case' : undefined}
            onAction={canEdit ? openAdd : undefined}
            showAddIcon
          />
        ) : (
          <>
            {/* Nothing while a run is going: until the worker has cleared the
                last run's results, the number is the previous run's, and one
                sitting above a progress line reads as this run's. The progress
                line says what is happening instead. */}
            {hasResults && run && !isRunning && (
              <AgreementSummary agreement={run.agreement} />
            )}
            <RunSummary run={run} />
            <BaseDataGrid
              rows={cases as unknown as GridRowModel[]}
              columns={columns}
              columnGroupingModel={columnGroupingModel}
              loading={loading}
              getRowId={row => String(row.id)}
              paginationModel={paginationModel}
              onPaginationModelChange={setPaginationModel}
              pageSizeOptions={[10, 25, 50, 100]}
              showToolbar={false}
              disableMultipleRowSelection
              sx={rowActionsHoverSx}
            />
          </>
        )}
      </SectionCard>

      <MetricTuningCaseDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        tuningCase={editing}
        groundTruthRequired={groundTruthRequired}
        onSubmit={handleSubmit}
      />

      <MetricTuningRejectDialog
        open={rejecting !== null}
        onClose={() => setRejecting(null)}
        verdict={rejecting?.result?.verdict ?? null}
        onSubmit={handleReject}
      />
    </>
  );
}
