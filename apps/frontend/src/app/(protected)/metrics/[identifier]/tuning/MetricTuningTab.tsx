'use client';

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { fetchMetricTuning, type MetricTuningData } from '../metric-data';
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
  AutoFixHighIcon,
  CancelIcon,
  CheckCircleIcon,
  CheckIcon,
  CloseIcon,
  PlayArrowIcon,
  TuneIcon,
  WarningAmberIcon,
} from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { UUID } from 'crypto';
import type {
  Metric,
  MetricUpdate,
  ScoreType,
} from '@/utils/api-client/interfaces/metric';
import type {
  ImprovedMetricFields,
  MetricTuningAgreement,
  MetricTuningCase,
  MetricTuningCaseCreate,
  MetricTuningImprovement,
  MetricTuningRun,
} from '@/utils/api-client/interfaces/metric-tuning';
import MetricTuningCaseDialog from './MetricTuningCaseDialog';
import MetricTuningImproveDialog from './MetricTuningImproveDialog';
import MetricTuningRejectDialog from './MetricTuningRejectDialog';

/** How often to re-read a run that is still going. */
const RUN_POLL_INTERVAL_MS = 3000;

const ACCEPTED_HINT = 'You accepted this verdict. Press again to re-accept it.';

const REJECTED_HINT = 'You rejected this verdict.';

const INVALIDATED_HINT =
  "The metric's verdict crossed its threshold, or its score type changed, since this case was reviewed — the old judgement no longer applies, so it needs a fresh look.";

const ERRORED_HINT =
  'The metric call failed for this case, so there is no verdict to judge.';

const NO_REJECTIONS_HINT =
  'Reject a case with a comment first: Improve reads the comments.';

const IMPROVE_HINT =
  'Rewrite this metric from the comments on the cases it got wrong. Nothing is saved until you apply it.';

const IMPROVE_WHILE_RUNNING_HINT =
  'Wait for the run to finish: it is about to replace the verdicts those comments are about.';

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
 * The two marks: hollow while the judgement is open, solid once it stands.
 *
 * Neither glyph ships an outlined variant, so the outline is drawn from the same
 * path — its fill dropped and its edge stroked. That keeps the mark the same
 * shape in both states, which is what makes the fill read as the state rather
 * than as a different control. Colour alone did not carry it at this size: a
 * thin green tick and a thin grey one read alike until you look for the hue.
 */
const MARK_OPEN_SX = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinejoin: 'round' as const,
};

/** The same path kept filled and stroked, so the mark that stands reads bold. */
const MARK_SET_SX = {
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinejoin: 'round' as const,
};

/**
 * The judgement that stands for this case, and the two buttons that change it.
 *
 * The tick and the cross are the state as well as the control: the one that was
 * pressed is coloured green or red and drawn heavier, the other stays thin and
 * faint. A chip saying "Accepted" beside a green tick says the same thing twice.
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
        {accepted && (
          <CheckIcon fontSize="small" color="success" sx={MARK_SET_SX} />
        )}
        {rejected && (
          <Tooltip title={review?.comment ?? ''}>
            <CloseIcon fontSize="small" color="error" sx={MARK_SET_SX} />
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
          sx={{ opacity: accepted ? 1 : 0.6 }}
          onClick={() => onAccept(tuningCase)}
        >
          <CheckIcon
            fontSize="small"
            sx={accepted ? MARK_SET_SX : MARK_OPEN_SX}
          />
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
          sx={{ opacity: rejected ? 1 : 0.6 }}
          onClick={() => onReject(tuningCase)}
        >
          <CloseIcon
            fontSize="small"
            sx={rejected ? MARK_SET_SX : MARK_OPEN_SX}
          />
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
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
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
      <Typography variant="body2" color="error">
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
    <Box>
      <Typography variant="body2" color="text.secondary">
        Last run {finished ? finished.toLocaleString() : ''} over{' '}
        {run.completed_cases} {run.completed_cases === 1 ? 'case' : 'cases'}.
        {errored}
      </Typography>
      {/* Every verdict above came out of the metric as it was then, so the
          agreement is that metric's rather than this one's. */}
      {run.predates_metric && (
        <Typography variant="body2" color="warning.main">
          This metric has changed since that run, so the numbers above belong to
          the earlier version. Press Run metric to score it again.
        </Typography>
      )}
    </Box>
  );
}

/**
 * The improvement as a metric update: every field it showed that has a value.
 *
 * A metric update cannot clear a field — the API drops a null rather than
 * writing it — so a null sent here would be a field the dialog showed and the
 * save quietly skipped. The API refuses to propose blanking anything the metric
 * has, so every null left is a field the metric does not have either, and
 * leaving it out writes exactly what was on screen.
 */
function toMetricUpdate(fields: ImprovedMetricFields): MetricUpdate {
  const update: MetricUpdate = {
    name: fields.name,
    description: fields.description,
    evaluation_prompt: fields.evaluation_prompt,
    evaluation_steps: fields.evaluation_steps,
    reasoning: fields.reasoning,
    explanation: fields.explanation,
    score_type: fields.score_type,
  };
  if (fields.min_score !== null) update.min_score = fields.min_score;
  if (fields.max_score !== null) update.max_score = fields.max_score;
  if (fields.threshold !== null) update.threshold = fields.threshold;
  if (fields.threshold_operator !== null) {
    update.threshold_operator = fields.threshold_operator;
  }
  if (fields.categories !== null) update.categories = fields.categories;
  if (fields.passing_categories !== null) {
    update.passing_categories = fields.passing_categories;
  }
  return update;
}

/**
 * One line saying a rewrite is being written, while it is being written.
 *
 * Deliberately the same shape as ``RunSummary``'s in-progress line: both are a
 * slow thing the tab started, and a second visual language for the second one
 * would be two ways of saying "wait". The label on the button alone is too quiet
 * for a call that can take most of a minute.
 *
 * The rejection count is in it because that is what makes the wait legible --
 * three comments is quick, forty is not.
 */
function ImprovingSummary({ rejections }: { rejections: number }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <CircularProgress size={16} />
      <Typography variant="body2" color="text.secondary">
        Rewriting this metric from {rejections}{' '}
        {rejections === 1 ? 'rejection' : 'rejections'} — this takes a moment,
        the model is reading every comment.
      </Typography>
    </Box>
  );
}

export interface MetricTuningTabProps {
  metricId: string;
  /**
   * Called after an improvement is applied, so the rest of the page re-reads the
   * metric. Applying writes the evaluation prompt every other tab is showing.
   */
  onMetricChanged?: () => void;
  /** Server-prefetched metric, cases and run; skips the mount fetch. */
  initialData?: MetricTuningData;
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
export default function MetricTuningTab({
  metricId,
  onMetricChanged,
  initialData,
}: MetricTuningTabProps) {
  const notifications = useNotifications();
  const canEdit = useCan(Capability.Metric.UPDATE);

  const [cases, setCases] = useState<MetricTuningCase[]>(
    initialData?.cases ?? []
  );
  // The whole metric, because the Improve dialog shows the current fields beside
  // the proposed ones and the grid needs the score type to render a verdict.
  const [metric, setMetric] = useState<Metric | null>(
    initialData?.metric ?? null
  );
  const [loading, setLoading] = useState(!initialData);
  // The metric id the server-rendered data belongs to: no mount fetch for it.
  const seededMetricIdRef = useRef(initialData ? metricId : null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<MetricTuningCase | null>(null);
  const [rejecting, setRejecting] = useState<MetricTuningCase | null>(null);
  const [run, setRun] = useState<MetricTuningRun | null>(
    initialData?.run ?? null
  );
  const [starting, setStarting] = useState(false);
  const [acceptingRest, setAcceptingRest] = useState(false);
  const [improving, setImproving] = useState(false);
  const [improvement, setImprovement] =
    useState<MetricTuningImprovement | null>(null);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const tuning = await fetchMetricTuning(new ApiClientFactory(), metricId);
      setMetric(tuning.metric);
      setCases(tuning.cases);
      setRun(tuning.run);
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
    if (seededMetricIdRef.current === metricId) return;
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

  // Read off the metric rather than kept beside it, so there is one answer to
  // "what score type is this" while the metric is being reloaded.
  const scoreType: ScoreType = metric?.score_type ?? 'binary';
  const groundTruthRequired = metric?.ground_truth_required === true;

  const handleImprove = useCallback(async () => {
    setImproving(true);
    try {
      const client = new ApiClientFactory().getMetricTuningClient();
      // The dialog opens on the answer, not on the click — there is nothing to
      // show until the rewrite is back, and no cancelling a call this short.
      setImprovement(await client.improveFromReviews(metricId));
    } catch (error) {
      notifications.show(
        error instanceof Error
          ? `Failed to improve the metric: ${error.message}`
          : 'Failed to improve the metric',
        { severity: 'error', autoHideDuration: 6000 }
      );
    } finally {
      setImproving(false);
    }
  }, [metricId, notifications]);

  // Throws on failure so the dialog keeps the proposal on screen: losing a
  // rewrite to a network blip would mean asking the model again for a different
  // one. Re-reads everything afterwards — the metric has changed, so the run on
  // screen now predates it.
  const handleApplyImprovement = useCallback(
    async (fields: ImprovedMetricFields) => {
      const client = new ApiClientFactory().getMetricsClient();
      await client.updateMetric(metricId as UUID, toMetricUpdate(fields));
      await fetchCases();
      // The evaluation prompt just changed, and the tabs beside this one are
      // still showing the copy they read when the page loaded.
      onMetricChanged?.();
      notifications.show(
        'Applied the improvement. Run the metric again to score it.',
        {
          severity: 'success',
          autoHideDuration: 6000,
        }
      );
    },
    [metricId, fetchCases, notifications, onMetricChanged]
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
        flex: 0,
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
            flex: 0,
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
  // Improve reads the comments on rejections, so without one there is nothing
  // for it to read. Only rejections that still stand count — the API refuses on
  // the same rule, and it is the outcome the grid is already showing.
  const standingRejections = cases.filter(c => c.outcome === 'rejected').length;
  const hasStandingRejection = standingRejections > 0;
  const canImprove = hasStandingRejection && !isRunning && !improving;
  // Keyed off why it is off, not off one of the reasons: a tooltip that explains
  // what Improve does while the button is disabled explains the wrong thing.
  const improveHint = !hasStandingRejection
    ? NO_REJECTIONS_HINT
    : isRunning
      ? IMPROVE_WHILE_RUNNING_HINT
      : IMPROVE_HINT;
  // Right above the grid rather than in the card header: every one of these
  // acts on the table below it, and the header sits three summary blocks away.
  //
  // The status line shares this row instead of sitting above it. It comes and
  // goes as runs start and finish, and a line that appears above the buttons
  // pushes the whole grid down every time it does; beside them it changes only
  // its own text. The row keeps the height of a button either way, so an empty
  // status slot is the same height as a full one.
  const actions = (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 2,
        mb: 2,
        minHeight: 40,
      }}
    >
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {improving ? (
          <ImprovingSummary rejections={standingRejections} />
        ) : (
          <RunSummary run={run} />
        )}
      </Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          flexShrink: 0,
        }}
      >
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
            startIcon={<CheckIcon />}
            onClick={handleAcceptRest}
            disabled={!unreviewedWithVerdict || acceptingRest}
          >
            Accept the rest
          </Button>
        )}
        {/* The tooltip sits on a span because MUI drops pointer events on a
          disabled button, and the disabled state is the one whose reason a
          reader actually needs. */}
        {canEdit && (
          <Tooltip title={improveHint}>
            <span>
              <Button
                variant="outlined"
                startIcon={
                  improving ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    <AutoFixHighIcon />
                  )
                }
                onClick={handleImprove}
                disabled={!canImprove}
              >
                {improving ? 'Improving…' : 'Improve'}
              </Button>
            </span>
          </Tooltip>
        )}
        {canEdit && (
          <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>
            Add case
          </Button>
        )}
      </Box>
    </Box>
  );

  return (
    <>
      <SectionCard
        title="Improve this metric"
        subtitle="Cases for checking whether this metric judges the way you would."
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
            {/* Kept on screen through a run rather than pulled out from under
                the reviewer: it is the number they pressed Run to move, and a
                dashboard that vanishes on the press takes the whole page up
                with it. A run clears the verdicts it is about to replace, so
                the tiles empty out on their own while it goes — the progress
                line beside the buttons says why. */}
            {run && <AgreementSummary agreement={run.agreement} />}
            {/* Not while the list is still loading: a toolbar that appears and
                then goes away again when the metric turns out to have no cases
                is worse than one that arrives with the rows it acts on. */}
            {cases.length > 0 && actions}
            <BaseDataGrid
              rows={cases as unknown as GridRowModel[]}
              columns={columns}
              columnGroupingModel={columnGroupingModel}
              loading={loading}
              getRowId={row => String(row.id)}
              paginationModel={paginationModel}
              onPaginationModelChange={setPaginationModel}
              pageSizeOptions={[10, 25, 50, 100]}
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

      <MetricTuningImproveDialog
        open={improvement !== null}
        onClose={() => setImprovement(null)}
        improvement={improvement}
        metric={metric}
        onApply={handleApplyImprovement}
      />
    </>
  );
}
