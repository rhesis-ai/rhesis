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
import {
  type AdaptiveMetricEvalDetail,
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

function getLabelColor(label: string): 'success' | 'error' | 'default' {
  if (label === 'pass') return 'success';
  if (label === 'fail') return 'error';
  return 'default';
}

interface SuggestionsDialogProps {
  open: boolean;
  onClose: () => void;
  testSetId: string;
  sessionToken: string;
  topic: string | null;
  /** Optional user guidance passed to generate_suggestions (LLM prompt). */
  userFeedback?: string | null;
  onTestAccepted: () => void;
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
  const hasStarted = useRef(false);
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

  const handleClose = () => {
    if (!loading && !outputsLoading && !evaluateLoading) {
      onClose();
    }
  };

  const handleGenerate = useCallback(async () => {
    setSuggestions([]);
    setLoading(true);
    setError(null);
    setCurrentStep('suggestions');
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getAdaptiveTestingClient();
      const trimmedFeedback = regenerationGuide.trim();
      const suggestionsResult = await client.generateSuggestions(testSetId, {
        topic: topic ?? undefined,
        num_examples: 10,
        num_suggestions: 20,
        ...(trimmedFeedback ? { user_feedback: trimmedFeedback } : {}),
      });
      const rows: SuggestionRow[] = suggestionsResult.suggestions.map(
        (s, idx) => ({
          ...s,
          _id: `suggestion-${idx}-${Date.now()}`,
        })
      );
      setSuggestions(rows);
      if (rows.length === 0) {
        setError('No suggestions were generated. The test set may be empty.');
        return;
      }
      setLoading(false);

      const eligibleForOutputs = rows.filter(s => s.input.trim());
      let rowsWithOutputs = rows;
      if (eligibleForOutputs.length > 0) {
        setCurrentStep('outputs');
        setOutputsLoading(true);
        try {
          const eligibleIds = eligibleForOutputs.map(s => s._id);
          const eligibleIdSet = new Set(eligibleIds);
          rowsWithOutputs = rowsWithOutputs.map(s =>
            eligibleIdSet.has(s._id) ? { ...s, output_pending: true } : s
          );
          setSuggestions(rowsWithOutputs);

          let streamedGenerated = 0;
          let streamedTotal = eligibleForOutputs.length;
          let streamedFailed = 0;

          await client.generateSuggestionOutputsStream(
            testSetId,
            {
              suggestions: eligibleForOutputs.map(s => ({
                input: s.input,
                topic: s.topic,
              })),
            },
            {
              onEvent: event => {
                if (event.type === 'item') {
                  const targetId = eligibleIds[event.index];
                  if (!targetId) return;
                  if (event.error) {
                    streamedFailed += 1;
                  }
                  rowsWithOutputs = rowsWithOutputs.map(s => {
                    if (s._id !== targetId) return s;
                    return {
                      ...s,
                      output: event.output,
                      output_error: event.error,
                      output_pending: false,
                    };
                  });
                  setSuggestions(rowsWithOutputs);
                } else if (event.type === 'summary') {
                  streamedGenerated = event.generated;
                  streamedTotal = event.total;
                }
              },
            }
          );

          if (streamedFailed > 0) {
            notifications.show(
              `Got ${streamedGenerated} outputs; ${streamedFailed} failed.`,
              { severity: 'warning' }
            );
          } else if (streamedGenerated === 0 && streamedTotal > 0) {
            notifications.show('No suggestion outputs were generated.', {
              severity: 'warning',
            });
          }
        } catch (err) {
          notifications.show(
            err instanceof Error
              ? err.message
              : 'Failed to get suggestion outputs.',
            { severity: 'error' }
          );
        } finally {
          setOutputsLoading(false);
        }
      }

      const eligibleForEvaluation = rowsWithOutputs.filter(
        s => s.input.trim() && s.output.trim() && s.output !== '[no output]'
      );
      if (eligibleForEvaluation.length > 0) {
        setCurrentStep('evaluate');
        setEvaluateLoading(true);
        try {
          const eligibleEvalIds = eligibleForEvaluation.map(s => s._id);
          const eligibleEvalIdSet = new Set(eligibleEvalIds);

          rowsWithOutputs = rowsWithOutputs.map(s =>
            eligibleEvalIdSet.has(s._id) ? { ...s, eval_pending: true } : s
          );
          setSuggestions(rowsWithOutputs);

          let streamedEvaluated = 0;
          let streamedTotal = eligibleForEvaluation.length;
          let streamedFailed = 0;

          await client.evaluateSuggestionsStream(
            testSetId,
            {
              suggestions: eligibleForEvaluation.map(s => ({
                input: s.input,
                output: s.output,
              })),
            },
            {
              onEvent: event => {
                if (event.type === 'item') {
                  const targetId = eligibleEvalIds[event.index];
                  if (!targetId) return;

                  if (event.error) {
                    streamedFailed += 1;
                  }

                  rowsWithOutputs = rowsWithOutputs.map(s => {
                    if (s._id !== targetId) return s;
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
                  setSuggestions(rowsWithOutputs);
                } else if (event.type === 'summary') {
                  streamedEvaluated = event.evaluated;
                  streamedTotal = event.total;
                }
              },
            }
          );

          if (streamedFailed > 0) {
            notifications.show(
              `Evaluated ${streamedEvaluated} suggestions; ${streamedFailed} failed.`,
              { severity: 'warning' }
            );
          } else if (streamedEvaluated === 0 && streamedTotal > 0) {
            notifications.show('No suggestions were evaluated.', {
              severity: 'warning',
            });
          }
        } catch (err) {
          notifications.show(
            err instanceof Error
              ? err.message
              : 'Failed to evaluate suggestions.',
            { severity: 'error' }
          );
        } finally {
          setEvaluateLoading(false);
        }
      } else {
        notifications.show('No suggestions with outputs to evaluate.', {
          severity: 'warning',
        });
      }
    } catch (err) {
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
    }
  }, [open, handleGenerate]);

  const handleAccept = async (row: SuggestionRow) => {
    setAcceptingIds(prev => new Set(prev).add(row._id));
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getAdaptiveTestingClient();
      const data: TestNodeCreate = {
        input: row.input,
        output: row.output || undefined,
        labeler: 'suggestion',
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
      await client.createTest(testSetId, data);
      setSuggestions(prev => prev.filter(s => s._id !== row._id));
      onTestAccepted();
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
    if (suggestions.length === 0) return;
    const toAccept = [...suggestions];
    for (const row of toAccept) {
      await handleAccept(row);
    }
  };

  const columns: GridColDef[] = [
    {
      field: 'input',
      headerName: 'Input',
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

  const isProcessing = loading || outputsLoading || evaluateLoading;

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
              disabled={isProcessing}
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

        {isProcessing && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <CircularProgress size={20} />
            <Typography variant="body2" color="text.secondary">
              {currentStep === 'suggestions' &&
                'Step 1/3: Generating suggestions...'}
              {currentStep === 'outputs' && 'Step 2/3: Getting outputs...'}
              {currentStep === 'evaluate' && 'Step 3/3: Evaluating...'}
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
              disabled={isProcessing}
            />
          </Box>
        </Collapse>

        <BaseDataGrid
          columns={columns}
          rows={suggestions}
          loading={false}
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
        <Button onClick={handleClose} disabled={isProcessing}>
          Close
        </Button>
        <Button
          variant="outlined"
          onClick={() => setGuideEditorOpen(v => !v)}
          disabled={isProcessing}
          sx={{ textTransform: 'none' }}
        >
          {guideEditorOpen ? 'Hide guide' : 'Generation guide'}
        </Button>
        <Button
          variant="outlined"
          onClick={handleGenerate}
          disabled={isProcessing}
          sx={{ textTransform: 'none' }}
        >
          Regenerate
        </Button>
      </DialogActions>
    </Dialog>
  );
}
