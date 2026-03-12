'use client';

import { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Autocomplete,
  TextField,
  CircularProgress,
  Alert,
  Chip,
  Tooltip,
  IconButton,
} from '@mui/material';
import { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import PlayArrowIcon from '@mui/icons-material/PlayArrowOutlined';
import GradingIcon from '@mui/icons-material/GradingOutlined';
import CheckIcon from '@mui/icons-material/CheckOutlined';
import {
  SuggestedTest,
  TestNodeCreate,
  Topic,
} from '@/utils/api-client/interfaces/adaptive-testing';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';

interface SuggestionRow extends SuggestedTest {
  _id: string;
}

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
  topics: Topic[];
  endpoints: Endpoint[];
  endpointsLoading: boolean;
  metrics: MetricDetail[];
  metricsLoading: boolean;
  defaultEndpoint: Endpoint | null;
  defaultMetric: MetricDetail | null;
  onTestAccepted: () => void;
}

export default function SuggestionsDialog({
  open,
  onClose,
  testSetId,
  sessionToken,
  topic,
  endpoints,
  endpointsLoading,
  metrics,
  metricsLoading,
  defaultEndpoint,
  defaultMetric,
  onTestAccepted,
}: SuggestionsDialogProps) {
  const [suggestions, setSuggestions] = useState<SuggestionRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generated, setGenerated] = useState(false);

  const [selectedEndpoint, setSelectedEndpoint] = useState<Endpoint | null>(
    null
  );
  const [selectedMetric, setSelectedMetric] = useState<MetricDetail | null>(
    null
  );
  const [outputsLoading, setOutputsLoading] = useState(false);
  const [evaluateLoading, setEvaluateLoading] = useState(false);
  const [acceptingIds, setAcceptingIds] = useState<Set<string>>(new Set());

  const notifications = useNotifications();

  const handleOpen = useCallback(() => {
    setSelectedEndpoint(defaultEndpoint);
    setSelectedMetric(defaultMetric);
    if (!generated) {
      setSuggestions([]);
      setError(null);
    }
  }, [defaultEndpoint, defaultMetric, generated]);

  const handleClose = () => {
    if (!loading && !outputsLoading && !evaluateLoading) {
      onClose();
    }
  };

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getAdaptiveTestingClient();
      const result = await client.generateSuggestions(testSetId, {
        topic: topic ?? undefined,
        num_examples: 10,
        num_suggestions: 20,
      });
      const rows: SuggestionRow[] = result.suggestions.map((s, idx) => ({
        ...s,
        _id: `suggestion-${idx}-${Date.now()}`,
      }));
      setSuggestions(rows);
      setGenerated(true);
      if (rows.length === 0) {
        setError('No suggestions were generated. The test set may be empty.');
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to generate suggestions.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateOutputs = async () => {
    if (!selectedEndpoint?.id) {
      notifications.show('Please select an endpoint first.', {
        severity: 'warning',
      });
      return;
    }
    const eligible = suggestions.filter(s => s.input.trim());
    if (eligible.length === 0) return;

    setOutputsLoading(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getAdaptiveTestingClient();
      const result = await client.generateSuggestionOutputs(testSetId, {
        endpoint_id: selectedEndpoint.id,
        suggestions: eligible.map(s => ({
          input: s.input,
          topic: s.topic,
        })),
      });

      const outputMap = new Map<string, string>();
      for (const r of result.results) {
        outputMap.set(r.input, r.output);
      }

      setSuggestions(prev =>
        prev.map(s => {
          const output = outputMap.get(s.input);
          if (output !== undefined) {
            return { ...s, output };
          }
          return s;
        })
      );

      const failedCount = result.results.filter(r => r.error).length;
      if (failedCount > 0) {
        notifications.show(
          `Generated ${result.generated} outputs; ${failedCount} failed.`,
          { severity: 'warning' }
        );
      } else {
        notifications.show(
          `Generated ${result.generated} output(s) successfully.`,
          { severity: 'success' }
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
  };

  const handleEvaluate = async () => {
    if (!selectedMetric?.name) {
      notifications.show('Please select a metric first.', {
        severity: 'warning',
      });
      return;
    }
    const eligible = suggestions.filter(
      s => s.input.trim() && s.output.trim() && s.output !== '[no output]'
    );
    if (eligible.length === 0) {
      notifications.show(
        'No suggestions with outputs to evaluate. Run "Generate Outputs" first.',
        { severity: 'warning' }
      );
      return;
    }

    setEvaluateLoading(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getAdaptiveTestingClient();
      const result = await client.evaluateSuggestions(testSetId, {
        metric_names: [selectedMetric.name],
        suggestions: eligible.map(s => ({
          input: s.input,
          output: s.output,
        })),
      });

      const evalMap = new Map<
        string,
        { label: string; labeler: string; model_score: number }
      >();
      for (const r of result.results) {
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

      const failedCount = result.results.filter(r => r.error).length;
      if (failedCount > 0) {
        notifications.show(
          `Evaluated ${result.evaluated} suggestions; ${failedCount} failed.`,
          { severity: 'warning' }
        );
      } else {
        notifications.show(
          `Evaluated ${result.evaluated} suggestion(s) successfully.`,
          { severity: 'success' }
        );
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
  };

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
      TransitionProps={{ onEnter: handleOpen }}
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
              <Chip
                label={suggestions.length}
                size="small"
                sx={{ ml: 1 }}
              />
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
          <Alert
            severity="error"
            sx={{ mb: 2 }}
            onClose={() => setError(null)}
          >
            {error}
          </Alert>
        )}

        {!generated && !loading && (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography
              variant="body1"
              color="text.secondary"
              sx={{ mb: 2 }}
            >
              Generate test suggestions using AI based on your existing tests
              {topic ? ` for topic "${topic}"` : ''}.
            </Typography>
            <Button
              variant="contained"
              onClick={handleGenerate}
              disabled={loading}
              startIcon={
                loading ? (
                  <CircularProgress size={16} color="inherit" />
                ) : undefined
              }
            >
              {loading ? 'Generating...' : 'Generate Suggestions'}
            </Button>
          </Box>
        )}

        {loading && (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <CircularProgress sx={{ mb: 2 }} />
            <Typography variant="body2" color="text.secondary">
              Generating test suggestions...
            </Typography>
          </Box>
        )}

        {generated && !loading && (
          <>
            <Box
              sx={{
                display: 'flex',
                gap: 2,
                mb: 2,
                flexWrap: 'wrap',
                alignItems: 'center',
              }}
            >
              <Autocomplete
                size="small"
                options={endpoints}
                getOptionLabel={option => option.name ?? ''}
                value={selectedEndpoint}
                onChange={(_, value) =>
                  setSelectedEndpoint(value ?? null)
                }
                loading={endpointsLoading}
                renderInput={params => (
                  <TextField
                    {...params}
                    label="Endpoint"
                    placeholder="Select endpoint"
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {endpointsLoading ? (
                            <CircularProgress
                              color="inherit"
                              size={20}
                            />
                          ) : null}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    }}
                  />
                )}
                sx={{ minWidth: 220, maxWidth: 320 }}
              />
              <Button
                size="small"
                startIcon={
                  outputsLoading ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    <PlayArrowIcon />
                  )
                }
                onClick={handleGenerateOutputs}
                disabled={
                  !selectedEndpoint ||
                  outputsLoading ||
                  suggestions.length === 0
                }
                sx={{ textTransform: 'none' }}
              >
                {outputsLoading ? 'Generating...' : 'Generate Outputs'}
              </Button>

              <Autocomplete
                size="small"
                options={metrics}
                getOptionLabel={option => option.name ?? ''}
                value={selectedMetric}
                onChange={(_, value) =>
                  setSelectedMetric(value ?? null)
                }
                loading={metricsLoading}
                renderInput={params => (
                  <TextField
                    {...params}
                    label="Metric"
                    placeholder="Select metric"
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {metricsLoading ? (
                            <CircularProgress
                              color="inherit"
                              size={20}
                            />
                          ) : null}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    }}
                  />
                )}
                sx={{ minWidth: 220, maxWidth: 320 }}
              />
              <Button
                size="small"
                startIcon={
                  evaluateLoading ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    <GradingIcon />
                  )
                }
                onClick={handleEvaluate}
                disabled={
                  !selectedMetric ||
                  evaluateLoading ||
                  suggestions.length === 0
                }
                sx={{ textTransform: 'none' }}
              >
                {evaluateLoading ? 'Evaluating...' : 'Evaluate'}
              </Button>
            </Box>

            {suggestions.length > 0 ? (
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
            ) : (
              <Box sx={{ textAlign: 'center', py: 3 }}>
                <Typography variant="body2" color="text.secondary">
                  All suggestions have been accepted.
                </Typography>
              </Box>
            )}
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={isProcessing}>
          Close
        </Button>
        {generated && (
          <Button
            variant="outlined"
            onClick={handleGenerate}
            disabled={isProcessing}
          >
            Regenerate
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
