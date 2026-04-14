'use client';

import {
  useState,
  useCallback,
  useRef,
  useEffect,
  useLayoutEffect,
} from 'react';
import {
  Box,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Alert,
  Chip,
  Tooltip,
  IconButton,
  TextField,
  Collapse,
} from '@mui/material';
import { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import CheckIcon from '@mui/icons-material/CheckOutlined';
import { useTheme } from '@mui/material/styles';
import {
  type AdaptiveMetricEvalDetail,
  type SuggestionPipelineEvent,
  SuggestedTest,
  TestNodeCreate,
} from '@/utils/api-client/interfaces/adaptive-testing';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { ScoreMetricsTooltip } from './scoreMetricsTooltip';

interface SuggestionRow extends SuggestedTest {
  _id: string;
  metrics?: Record<string, AdaptiveMetricEvalDetail> | null;
  output_error?: string | null;
  output_pending?: boolean;
  eval_error?: string | null;
  eval_pending?: boolean;
}

type PipelineStep = 'suggestions' | 'outputs' | 'evaluate' | null;

type PhaseStatus = 'idle' | 'running' | 'done';

function clamp01(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function SegmentedProgressBar({
  segments,
}: {
  segments: Array<{
    label: string;
    fraction: number;
    active?: boolean;
  }>;
}) {
  const theme = useTheme();

  return (
    <Box sx={{ width: '100%', pt: '2px' }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          height: 8,
          width: '100%',
        }}
        aria-label="Adaptive testing generation progress"
      >
        {segments.map(seg => (
          <Box
            key={seg.label}
            sx={{
              position: 'relative',
              flex: 1,
              height: '100%',
              borderRadius: theme.spacing(1),
              overflow: 'hidden',
              backgroundColor: theme.palette.action.disabledBackground,
              // Inset ring so focus/active state is not clipped by DialogContent overflow
              boxShadow: seg.active
                ? `inset 0 0 0 1px ${theme.palette.primary.main}`
                : 'none',
            }}
            aria-label={seg.label}
          >
            <Box
              sx={{
                height: '100%',
                width: `${clamp01(seg.fraction) * 100}%`,
                backgroundColor: theme.palette.primary.main,
                transition: 'width 120ms linear',
              }}
            />
          </Box>
        ))}
      </Box>
      <Box
        sx={{
          mt: 0.5,
          display: 'flex',
          justifyContent: 'space-between',
          gap: 2,
        }}
      >
        {segments.map(seg => (
          <Typography
            key={`${seg.label}-caption`}
            variant="caption"
            color={seg.active ? 'text.primary' : 'text.secondary'}
            sx={{ flex: 1, minWidth: 0, whiteSpace: 'nowrap' }}
          >
            {seg.label}
          </Typography>
        ))}
      </Box>
    </Box>
  );
}

function getLabelColor(label: string): 'success' | 'error' | 'default' {
  if (label === 'pass') return 'success';
  if (label === 'fail') return 'error';
  return 'default';
}

function buildTestNodeCreateFromSuggestion(row: SuggestionRow): TestNodeCreate {
  const data: TestNodeCreate = {
    input: row.input,
    output: row.output || undefined,
    labeler: 'suggestion',
    generate_embedding: true,
  };
  if (row.topic) {
    data.topic = row.topic;
  }
  if (
    (row.label === 'pass' || row.label === 'fail') &&
    row.model_score != null
  ) {
    data.label = row.label;
    data.model_score = row.model_score;
  }
  return data;
}

interface SuggestionsDialogProps {
  open: boolean;
  onClose: () => void;
  testSetId: string;
  sessionToken: string;
  topic: string | null;
  /** Optional user guidance passed to generate_suggestions (LLM prompt). */
  userFeedback?: string | null;
  /** Refresh tree/topics after tests are persisted (await for batch flows). */
  onTestAccepted: () => Promise<void>;
}

export default function SuggestionsDialog({
  open,
  onClose,
  testSetId,
  sessionToken,
  topic,
  userFeedback = null,
  onTestAccepted,
}: SuggestionsDialogProps) {
  const [suggestions, setSuggestions] = useState<SuggestionRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [outputsLoading, setOutputsLoading] = useState(false);
  const [evaluateLoading, setEvaluateLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState<PipelineStep>(null);
  const [acceptingIds, setAcceptingIds] = useState<Set<string>>(new Set());
  const [acceptAllInProgress, setAcceptAllInProgress] = useState(false);
  const hasStarted = useRef(false);
  const [testGenStatus, setTestGenStatus] = useState<PhaseStatus>('idle');
  const [testGenCompleted, setTestGenCompleted] = useState(0);
  const [testGenTotal, setTestGenTotal] = useState(0);

  const [outputsStatus, setOutputsStatus] = useState<PhaseStatus>('idle');
  const [outputsCompleted, setOutputsCompleted] = useState(0);
  const [outputsTotal, setOutputsTotal] = useState(0);
  const seenOutputIndices = useRef<Set<number>>(new Set());

  const [metricsStatus, setMetricsStatus] = useState<PhaseStatus>('idle');
  const [metricsCompleted, setMetricsCompleted] = useState(0);
  const [metricsTotal, setMetricsTotal] = useState(0);
  const seenMetricIndices = useRef<Set<number>>(new Set());
  /** Guide text used for generate + regenerate (editable without closing dialog). */
  const [regenerationGuide, setRegenerationGuide] = useState('');
  const [guideEditorOpen, setGuideEditorOpen] = useState(false);

  const notifications = useNotifications();

  useLayoutEffect(() => {
    if (open) {
      setRegenerationGuide(userFeedback ?? '');
      setGuideEditorOpen(false);
    }
  }, [open, userFeedback]);

  const pipelineProcessing = loading || outputsLoading || evaluateLoading;
  const acceptInFlight = acceptAllInProgress || acceptingIds.size > 0;
  const isBusy = pipelineProcessing || acceptInFlight;

  const handleClose = () => {
    if (!isBusy) {
      onClose();
    }
  };

  const handleGenerate = useCallback(async () => {
    setSuggestions([]);
    setLoading(true);
    setError(null);
    setCurrentStep('suggestions');
    setTestGenStatus('running');
    setTestGenCompleted(0);
    setTestGenTotal(20);
    setOutputsStatus('idle');
    setOutputsCompleted(0);
    setOutputsTotal(0);
    seenOutputIndices.current = new Set();
    setMetricsStatus('idle');
    setMetricsCompleted(0);
    setMetricsTotal(0);
    seenMetricIndices.current = new Set();

    let rows: SuggestionRow[] = [];
    let outputsFailed = 0;
    let evalsFailed = 0;

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getAdaptiveTestingClient();
      const trimmedFeedback = regenerationGuide.trim();

      await client.suggestionPipeline(
        testSetId,
        {
          topic: topic ?? undefined,
          num_examples: 10,
          num_suggestions: 20,
          generate_embeddings: true,
          ...(trimmedFeedback ? { user_feedback: trimmedFeedback } : {}),
        },
        {
          onEvent: (event: SuggestionPipelineEvent) => {
            switch (event.type) {
              // ── Streaming: individual suggestion from LLM ──
              case 'suggestion': {
                const hasInput = event.input.trim().length > 0;
                const newRow: SuggestionRow = {
                  topic: event.topic,
                  input: event.input,
                  output: '',
                  label: '',
                  labeler: '',
                  model_score: 0,
                  _id: `suggestion-${event.index}-${Date.now()}`,
                  output_pending: hasInput,
                };
                rows = [...rows, newRow];
                setSuggestions(rows);
                setTestGenCompleted(rows.length);

                if (hasInput) {
                  setOutputsTotal(prev => prev + 1);
                  setOutputsStatus('running');
                  setOutputsLoading(true);
                }
                break;
              }

              // ── Streaming: embedding result for a suggestion ──
              case 'embedding': {
                rows = rows.map((s, idx) => {
                  if (idx !== event.index) return s;
                  return {
                    ...s,
                    embedding: event.embedding,
                  };
                });
                setSuggestions(rows);
                break;
              }

              // ── Streaming: all suggestions + embeddings done ──
              case 'suggestions_done': {
                setTestGenTotal(event.total);
                setTestGenCompleted(event.total);

                if (event.diversity_order) {
                  const reordered = event.diversity_order.map(i => rows[i]).filter(Boolean);
                  if (reordered.length === rows.length) {
                    rows = reordered;
                    setSuggestions(rows);
                  }
                }

                if (rows.length === 0) {
                  setTestGenStatus('idle');
                  setError(
                    'No suggestions were generated. The test set may be empty.'
                  );
                  return;
                }

                setTestGenStatus('done');
                setLoading(false);
                break;
              }

              // ── Bulk suggestions (legacy / non-streaming fallback) ──
              case 'suggestions': {
                const newRows: SuggestionRow[] = event.suggestions.map(
                  (s, idx) => ({
                    ...s,
                    _id: `suggestion-${idx}-${Date.now()}`,
                  })
                );
                rows = newRows;
                setSuggestions(rows);

                if (rows.length === 0) {
                  setTestGenStatus('idle');
                  setError(
                    'No suggestions were generated. The test set may be empty.'
                  );
                  return;
                }

                setTestGenStatus('done');
                setLoading(false);

                const eligible = rows.filter(s => s.input.trim());
                setOutputsTotal(eligible.length);
                setOutputsStatus(eligible.length > 0 ? 'running' : 'done');
                setCurrentStep('outputs');
                setOutputsLoading(true);

                rows = rows.map(s =>
                  s.input.trim()
                    ? { ...s, output_pending: true }
                    : s
                );
                setSuggestions(rows);
                break;
              }

              case 'output': {
                if (!seenOutputIndices.current.has(event.index)) {
                  seenOutputIndices.current.add(event.index);
                  setOutputsCompleted(prev => prev + 1);
                }
                if (event.error) outputsFailed += 1;

                rows = rows.map((s, idx) => {
                  if (idx !== event.index) return s;
                  return {
                    ...s,
                    output: event.output,
                    output_error: event.error,
                    output_pending: false,
                    eval_pending:
                      !event.error &&
                      !!event.output &&
                      event.output !== '[no output]',
                  };
                });
                setSuggestions(rows);

                if (
                  !event.error &&
                  event.output &&
                  event.output !== '[no output]'
                ) {
                  setMetricsTotal(prev => prev + 1);
                  setMetricsStatus('running');
                  setCurrentStep('evaluate');
                  setEvaluateLoading(true);
                }
                break;
              }

              case 'evaluation': {
                if (!seenMetricIndices.current.has(event.index)) {
                  seenMetricIndices.current.add(event.index);
                  setMetricsCompleted(prev => prev + 1);
                }
                if (event.error) evalsFailed += 1;

                rows = rows.map((s, idx) => {
                  if (idx !== event.index) return s;
                  return {
                    ...s,
                    label: event.label,
                    labeler: event.labeler,
                    model_score: event.model_score,
                    metrics: event.metrics,
                    eval_error: event.error,
                    eval_pending: false,
                  };
                });
                setSuggestions(rows);
                break;
              }

              case 'output_summary': {
                setOutputsStatus('done');
                setOutputsLoading(false);
                if (outputsFailed > 0) {
                  notifications.show(
                    `Got ${event.generated} outputs; ${outputsFailed} failed.`,
                    { severity: 'warning' }
                  );
                } else if (event.generated === 0 && event.total > 0) {
                  notifications.show(
                    'No suggestion outputs were generated.',
                    { severity: 'warning' }
                  );
                }
                break;
              }

              case 'eval_summary': {
                setMetricsStatus('done');
                setEvaluateLoading(false);
                if (evalsFailed > 0) {
                  notifications.show(
                    `Evaluated ${event.evaluated} suggestions; ${evalsFailed} failed.`,
                    { severity: 'warning' }
                  );
                } else if (event.evaluated === 0 && event.total > 0) {
                  notifications.show('No suggestions were evaluated.', {
                    severity: 'warning',
                  });
                }
                break;
              }

              case 'done': {
                break;
              }
            }
          },
        }
      );
    } catch (err) {
      setTestGenStatus('idle');
      setError(
        err instanceof Error ? err.message : 'Failed to generate suggestions.'
      );
    } finally {
      setCurrentStep(null);
      setLoading(false);
      setOutputsLoading(false);
      setEvaluateLoading(false);
    }
    // notifications.show is stable; omit to avoid unnecessary effect churn
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionToken, testSetId, topic, regenerationGuide]);

  useEffect(() => {
    if (open && !hasStarted.current) {
      hasStarted.current = true;
      handleGenerate();
    }
    if (!open) {
      hasStarted.current = false;
      setTestGenStatus('idle');
      setTestGenCompleted(0);
      setTestGenTotal(0);
      setOutputsStatus('idle');
      setOutputsCompleted(0);
      setOutputsTotal(0);
      seenOutputIndices.current = new Set();
      setMetricsStatus('idle');
      setMetricsCompleted(0);
      setMetricsTotal(0);
      seenMetricIndices.current = new Set();
    }
  }, [open, handleGenerate]);

  const handleAccept = async (row: SuggestionRow) => {
    setAcceptingIds(prev => new Set(prev).add(row._id));
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getAdaptiveTestingClient();
      await client.createTest(
        testSetId,
        buildTestNodeCreateFromSuggestion(row)
      );
      setSuggestions(prev => prev.filter(s => s._id !== row._id));
      await onTestAccepted();
      notifications.show('Test added successfully.', { severity: 'success' });
    } catch (err) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to accept test.',
        { severity: 'error' }
      );
    } finally {
      setAcceptingIds(prev => {
        const next = new Set(prev);
        next.delete(row._id);
        return next;
      });
    }
  };

  const handleAcceptAll = async () => {
    if (suggestions.length === 0 || acceptAllInProgress) return;
    const toAccept = [...suggestions];
    setAcceptAllInProgress(true);
    setAcceptingIds(prev => {
      const next = new Set(prev);
      toAccept.forEach(r => next.add(r._id));
      return next;
    });
    let shouldCloseAfterAcceptAll = false;
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getAdaptiveTestingClient();
      const results = await Promise.allSettled(
        toAccept.map(row =>
          client.createTest(testSetId, buildTestNodeCreateFromSuggestion(row))
        )
      );
      const succeededIds = new Set<string>();
      let failCount = 0;
      let firstRejection: unknown;
      results.forEach((result, index) => {
        const row = toAccept[index];
        if (result.status === 'fulfilled') {
          succeededIds.add(row._id);
        } else {
          failCount += 1;
          if (firstRejection === undefined) {
            firstRejection = result.reason;
          }
        }
      });
      setSuggestions(prev => prev.filter(s => !succeededIds.has(s._id)));
      setAcceptingIds(prev => {
        const next = new Set(prev);
        toAccept.forEach(r => next.delete(r._id));
        return next;
      });
      const successCount = succeededIds.size;
      if (successCount > 0) {
        await onTestAccepted();
      }
      if (failCount === 0) {
        notifications.show(
          successCount === 1
            ? 'Test added successfully.'
            : `Added ${successCount} tests successfully.`,
          { severity: 'success' }
        );
        shouldCloseAfterAcceptAll = successCount > 0;
      } else if (successCount > 0) {
        notifications.show(
          `Added ${successCount} test(s). ${failCount} failed.`,
          { severity: 'warning' }
        );
      } else {
        const message =
          firstRejection instanceof Error
            ? firstRejection.message
            : 'Failed to accept tests.';
        notifications.show(message, { severity: 'error' });
      }
    } finally {
      setAcceptAllInProgress(false);
      // Only auto-close when all accepts succeeded, so failures remain retryable.
      if (shouldCloseAfterAcceptAll) {
        onClose();
      }
    }
  };

  const columns: GridColDef[] = [
    {
      field: 'input',
      headerName: 'Input',
      flex: 2,
      minWidth: 200,
      renderCell: (params: GridRenderCellParams) => {
        const row = params.row as SuggestionRow;
        const tooltipContent =
          row.diversity_score != null
            ? `Diversity: ${row.diversity_score.toFixed(3)}\n\n${params.value || ''}`
            : params.value || '';
        return (
          <Tooltip
            title={
              <Box component="span" sx={{ whiteSpace: 'pre-line', display: 'block' }}>
                {tooltipContent}
              </Box>
            }
            arrow
            placement="top"
          >
            <Typography
              variant="body2"
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {params.value || '-'}
            </Typography>
          </Tooltip>
        );
      },
    },
    {
      field: 'output',
      headerName: 'Output',
      flex: 2,
      minWidth: 200,
      renderCell: (params: GridRenderCellParams) => (
        <Tooltip title={params.value || ''} arrow placement="top">
          <Typography
            variant="body2"
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {params.value || '-'}
          </Typography>
        </Tooltip>
      ),
    },
    {
      field: 'model_score',
      headerName: 'Score',
      width: 100,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params: GridRenderCellParams) => {
        const row = params.row as SuggestionRow;
        const label = row.label;
        const score = params.value;
        if (!label) {
          return <Chip label="N/A" size="small" variant="outlined" />;
        }
        return (
          <ScoreMetricsTooltip metrics={row.metrics}>
            <Chip
              label={score != null ? score.toFixed(2) : 'N/A'}
              size="small"
              color={getLabelColor(label)}
              variant={score != null ? 'filled' : 'outlined'}
            />
          </ScoreMetricsTooltip>
        );
      },
    },
    {
      field: 'actions',
      headerName: '',
      width: 70,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      renderCell: (params: GridRenderCellParams) => {
        const isAccepting = acceptingIds.has(params.row._id);
        return (
          <Tooltip title="Accept and save this test">
            <span>
              <IconButton
                size="small"
                onClick={() => handleAccept(params.row)}
                disabled={isAccepting}
                color="primary"
              >
                {isAccepting ? (
                  <CircularProgress size={16} />
                ) : (
                  <CheckIcon fontSize="small" />
                )}
              </IconButton>
            </span>
          </Tooltip>
        );
      },
    },
  ];

  const progressSegments = [
    {
      label:
        testGenStatus !== 'idle' && testGenTotal > 0
          ? `Test generation (${testGenCompleted}/${testGenTotal})`
          : 'Test generation',
      active: testGenStatus === 'running',
      fraction:
        testGenStatus === 'idle'
          ? 0
          : testGenStatus === 'done'
            ? 1
            : testGenTotal > 0
              ? testGenCompleted / testGenTotal
              : 0,
    },
    {
      label:
        outputsStatus !== 'idle' && outputsTotal > 0
          ? `Output generation (${outputsCompleted}/${outputsTotal})`
          : 'Output generation',
      active: outputsStatus === 'running',
      fraction:
        outputsStatus === 'idle'
          ? 0
          : outputsStatus === 'done'
            ? 1
            : outputsTotal > 0
              ? outputsCompleted / outputsTotal
              : 1,
    },
    {
      label:
        metricsStatus !== 'idle' && metricsTotal > 0
          ? `Metric generation (${metricsCompleted}/${metricsTotal})`
          : 'Metric generation',
      active: metricsStatus === 'running',
      fraction:
        metricsStatus === 'idle'
          ? 0
          : metricsStatus === 'done'
            ? 1
            : metricsTotal > 0
              ? metricsCompleted / metricsTotal
              : 1,
    },
  ];

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="lg" fullWidth>
      <DialogTitle>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Box>
            Suggested Tests
            {suggestions.length > 0 && (
              <Chip label={suggestions.length} size="small" sx={{ ml: 1 }} />
            )}
          </Box>
          {suggestions.length > 0 && (
            <Button
              size="small"
              variant="outlined"
              onClick={handleAcceptAll}
              disabled={
                pipelineProcessing ||
                acceptAllInProgress ||
                acceptingIds.size > 0
              }
              startIcon={<CheckIcon />}
              sx={{ textTransform: 'none' }}
            >
              Accept all
            </Button>
          )}
        </Box>
      </DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {pipelineProcessing && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 2,
              mb: 2,
              pt: 0.5,
            }}
          >
            <CircularProgress size={20} sx={{ mt: 0.25 }} />
            <SegmentedProgressBar segments={progressSegments} />
          </Box>
        )}

        {acceptAllInProgress && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              mb: 2,
              pt: 0.5,
            }}
          >
            <CircularProgress size={20} />
            <Typography variant="body2" color="text.secondary">
              Accepting suggestions…
            </Typography>
          </Box>
        )}

        <Collapse in={guideEditorOpen}>
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Optional text sent to the model with your examples. Used for the
              next generate / regenerate run.
            </Typography>
            <TextField
              multiline
              minRows={3}
              fullWidth
              label="Generation guide"
              placeholder="e.g., Focus on edge cases for date parsing..."
              value={regenerationGuide}
              onChange={e => setRegenerationGuide(e.target.value)}
              inputProps={{ maxLength: 1000 }}
              helperText="Up to 1000 characters."
              disabled={pipelineProcessing}
            />
          </Box>
        </Collapse>

        <BaseDataGrid
          columns={columns}
          rows={suggestions}
          loading={acceptAllInProgress}
          getRowId={row => row._id}
          showToolbar={false}
          paginationModel={{ page: 0, pageSize: 25 }}
          serverSidePagination={false}
          totalRows={suggestions.length}
          pageSizeOptions={[10, 25, 50]}
          disablePaperWrapper={true}
          persistState={false}
        />
      </DialogContent>
      <DialogActions sx={{ flexWrap: 'wrap', gap: 1 }}>
        <Button onClick={handleClose} disabled={isBusy}>
          Close
        </Button>
        <Button
          variant="outlined"
          onClick={() => setGuideEditorOpen(v => !v)}
          disabled={isBusy}
          sx={{ textTransform: 'none' }}
        >
          {guideEditorOpen ? 'Hide guide' : 'Generation guide'}
        </Button>
        <Button
          variant="outlined"
          onClick={handleGenerate}
          disabled={isBusy}
          sx={{ textTransform: 'none' }}
        >
          Regenerate
        </Button>
      </DialogActions>
    </Dialog>
  );
}
