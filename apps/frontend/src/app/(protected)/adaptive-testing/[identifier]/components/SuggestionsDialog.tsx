'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
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
} from '@mui/material';
import { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import CheckIcon from '@mui/icons-material/CheckOutlined';
import {
  SuggestedTest,
  TestNodeCreate,
} from '@/utils/api-client/interfaces/adaptive-testing';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';

interface SuggestionRow extends SuggestedTest {
  _id: string;
}

type PipelineStep = 'suggestions' | 'outputs' | 'evaluate' | null;

function getScoreColor(
  score: number | null
): 'success' | 'warning' | 'error' | 'default' {
  if (score === null) return 'default';
  if (score >= 0.7) return 'error';
  if (score >= 0.3) return 'warning';
  return 'success';
}

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
  onTestAccepted: () => void;
}

export default function SuggestionsDialog({
  open,
  onClose,
  testSetId,
  sessionToken,
  topic,
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

  const notifications = useNotifications();

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
      const suggestionsResult = await client.generateSuggestions(testSetId, {
        topic: topic ?? undefined,
        num_examples: 10,
        num_suggestions: 20,
      });
      const rows: SuggestionRow[] = suggestionsResult.suggestions.map((s, idx) => ({
        ...s,
        _id: `suggestion-${idx}-${Date.now()}`,
      }));
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
          const outputsResult = await client.generateSuggestionOutputs(testSetId, {
            suggestions: eligibleForOutputs.map(s => ({
              input: s.input,
              topic: s.topic,
            })),
          });

          const outputMap = new Map<string, string>();
          for (const r of outputsResult.results) {
            outputMap.set(r.input, r.output);
          }

          rowsWithOutputs = rows.map(s => {
            const output = outputMap.get(s.input);
            if (output !== undefined) {
              return { ...s, output };
            }
            return s;
          });
          setSuggestions(rowsWithOutputs);

          const failedCount = outputsResult.results.filter(r => r.error).length;
          if (failedCount > 0) {
            notifications.show(
              `Generated ${outputsResult.generated} outputs; ${failedCount} failed.`,
              { severity: 'warning' }
            );
          }
        } catch (err) {
          notifications.show(
            err instanceof Error
              ? err.message
              : 'Failed to generate suggestion outputs.',
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
          const evaluateResult = await client.evaluateSuggestions(testSetId, {
            suggestions: eligibleForEvaluation.map(s => ({
              input: s.input,
              output: s.output,
            })),
          });

          const evalMap = new Map<
            string,
            { label: string; labeler: string; model_score: number }
          >();
          for (const r of evaluateResult.results) {
            if (!r.error) {
              evalMap.set(r.input, {
                label: r.label,
                labeler: r.labeler,
                model_score: r.model_score,
              });
            }
          }

          setSuggestions(prev =>
            prev.map(s => {
              const evalResult = evalMap.get(s.input);
              if (evalResult) {
                return { ...s, ...evalResult };
              }
              return s;
            })
          );

          const failedCount = evaluateResult.results.filter(r => r.error).length;
          if (failedCount > 0) {
            notifications.show(
              `Evaluated ${evaluateResult.evaluated} suggestions; ${failedCount} failed.`,
              { severity: 'warning' }
            );
          }
        } catch (err) {
          notifications.show(
            err instanceof Error ? err.message : 'Failed to evaluate suggestions.',
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionToken, testSetId, topic]);

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
        const label = params.row.label;
        const score = params.value;
        if (!label) {
          return <Chip label="N/A" size="small" variant="outlined" />;
        }
        return (
          <Chip
            label={score != null ? score.toFixed(2) : 'N/A'}
            size="small"
            color={score != null ? getScoreColor(score) : 'default'}
            variant={score != null ? 'filled' : 'outlined'}
          />
        );
      },
    },
    {
      field: 'label',
      headerName: 'Label',
      width: 100,
      renderCell: (params: GridRenderCellParams) => {
        const label = params.value;
        if (!label) return <Chip label="N/A" size="small" variant="outlined" />;
        return (
          <Chip
            label={label}
            size="small"
            color={getLabelColor(label)}
            variant="outlined"
          />
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
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="lg"
      fullWidth
    >
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
              {currentStep === 'outputs' && 'Step 2/3: Generating outputs...'}
              {currentStep === 'evaluate' && 'Step 3/3: Evaluating...'}
            </Typography>
          </Box>
        )}

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
      <DialogActions>
        <Button onClick={handleClose} disabled={isProcessing}>
          Close
        </Button>
        <Button
          variant="outlined"
          onClick={handleGenerate}
          disabled={isProcessing}
        >
          Regenerate
        </Button>
      </DialogActions>
    </Dialog>
  );
}
