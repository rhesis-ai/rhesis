import { useState, useEffect } from 'react';
import {
  Box,
  CircularProgress,
  Stack,
  FormControl,
  Divider,
  Typography,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Button,
  IconButton,
  TextField,
} from '@mui/material';
import { TEST_TYPES } from '@/constants/test-types';
import {
  Add as AddIcon,
  Close as CloseIcon,
  AutoGraph as AutoGraphIcon,
  Tune as TuneIcon,
  Psychology as PsychologyIcon,
  Edit as EditIcon,
  Bolt as BoltIcon,
  Replay as ReplayIcon,
  ArrowForward as ArrowForwardIcon,
  CallSplit as CallSplitIcon,
} from '@mui/icons-material';
import BaseDrawer from '@/components/common/BaseDrawer';
import ModelSelector from '@/components/common/ModelSelector';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { UUID } from 'crypto';
import BaseTag from '@/components/common/BaseTag';
import { EntityType, TagCreate } from '@/utils/api-client/interfaces/tag';
import { TagsClient } from '@/utils/api-client/tags-client';
import { pollForTestRun } from '@/utils/test-run-utils';
import { getApiErrorMessage } from '@/utils/error-utils';
import tagStyles from '@/styles/BaseTag.module.css';
import SelectMetricsDialog from '@/components/common/SelectMetricsDialog';
import SelectExperimentsDialog from '@/components/common/SelectExperimentsDialog';
import type { TestSetMetric } from '@/utils/api-client/interfaces/test-set';
import { shortVersion } from '@/utils/api-client/interfaces/parameters';
import {
  executeBatchedTestRuns,
  type SelectedExperiment,
} from '@/utils/test-run-batch';
import { BiotechIcon } from '@/components/icons';

type MetricMode = 'use_test_set' | 'use_behavior' | 'define_custom';
type ScoringTarget = 'fresh' | 'reuse';

interface SelectedMetric {
  id: UUID;
  name: string;
  scope?: string[];
}

interface OriginalMetric {
  id: string;
  name: string;
  scope?: string[];
}

interface RerunConfig {
  testSetId: string;
  testSetName: string;
  testSetType?: string;
  endpointId: string;
  endpointName: string;
  projectId?: string;
  projectName: string;
  /** ID of the current test run being viewed (used as reference for output reuse) */
  testRunId: string;
  /** Original test configuration attributes containing metrics if custom were used */
  originalAttributes?: {
    metrics?: OriginalMetric[];
    parameters_ref?: {
      experiment_id?: string;
      version?: string;
      label?: string;
    };
    [key: string]: unknown;
  };
}

interface RerunTestRunDrawerProps {
  open: boolean;
  onClose: () => void;
  rerunConfig: RerunConfig;
  sessionToken: string;
  onSuccess?: () => void;
}

export default function RerunTestRunDrawer({
  open,
  onClose,
  rerunConfig,
  sessionToken,
  onSuccess,
}: RerunTestRunDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [tags, setTags] = useState<string[]>([]);
  const notifications = useNotifications();

  // Test set metrics state
  const [testSetMetrics, setTestSetMetrics] = useState<TestSetMetric[]>([]);

  // Metrics section state
  const [metricMode, setMetricMode] = useState<MetricMode>('use_behavior');
  const [selectedMetrics, setSelectedMetrics] = useState<SelectedMetric[]>([]);
  const [metricsDialogOpen, setMetricsDialogOpen] = useState(false);

  // Execution mode state
  const [executionMode, setExecutionMode] = useState<string>('Parallel');

  // Scoring target state
  const [scoringTarget, setScoringTarget] = useState<ScoringTarget>('fresh');

  // Model override state
  const [selectedExecutionModelId, setSelectedExecutionModelId] = useState('');
  const [selectedEvaluationModelId, setSelectedEvaluationModelId] =
    useState('');

  // Experiment state — multi-select via the picker. Re-runs pre-fill
  // from the original run's pinned experiment when present.
  const [selectedExperiments, setSelectedExperiments] = useState<
    SelectedExperiment[]
  >([]);
  const [experimentsDialogOpen, setExperimentsDialogOpen] = useState(false);

  // Fetch test set metrics and determine original metric source when drawer opens
  useEffect(() => {
    const fetchTestSetMetricsAndDetermineMode = async () => {
      if (!sessionToken || !open || !rerunConfig.testSetId) return;

      try {
        setLoading(true);
        setError(undefined);

        const clientFactory = new ApiClientFactory(sessionToken);
        const testSetsClient = clientFactory.getTestSetsClient();

        // Get test set metrics
        const metrics = await testSetsClient.getTestSetMetrics(
          rerunConfig.testSetId
        );
        setTestSetMetrics(metrics || []);

        // Determine original metric source from the test configuration
        const originalMetrics = rerunConfig.originalAttributes?.metrics;

        if (originalMetrics && originalMetrics.length > 0) {
          // Original test run used custom metrics
          setMetricMode('define_custom');
          setSelectedMetrics(
            originalMetrics.map(m => ({
              id: m.id as UUID,
              name: m.name,
              scope: m.scope,
            }))
          );
        } else if (metrics && metrics.length > 0) {
          // Original test run used test set metrics (test set has metrics configured)
          setMetricMode('use_test_set');
          setSelectedMetrics([]);
        } else {
          // Original test run used behavior metrics (fallback)
          setMetricMode('use_behavior');
          setSelectedMetrics([]);
        }
      } catch (err) {
        console.warn('Failed to fetch test set metrics:', err);
        setTestSetMetrics([]);
        setMetricMode('use_behavior');
        setSelectedMetrics([]);
      } finally {
        setLoading(false);
      }
    };

    if (open) {
      fetchTestSetMetricsAndDetermineMode();
      setTags([]);
      setExecutionMode('Parallel');
      setScoringTarget('fresh');
      setSelectedExecutionModelId(
        (rerunConfig.originalAttributes?.execution_model_id as string) || ''
      );
      setSelectedEvaluationModelId(
        (rerunConfig.originalAttributes?.evaluation_model_id as string) || ''
      );
    }
  }, [
    sessionToken,
    open,
    rerunConfig.testSetId,
    rerunConfig.originalAttributes,
  ]);

  // Pre-fill the experiment picker with the original run's pinned
  // experiment when re-opening. We hit the API directly (rather than
  // listing the whole project) so the initial chip carries the right
  // name + version without waiting for the modal to open and load.
  useEffect(() => {
    if (!open) return;
    const origRef = rerunConfig.originalAttributes?.parameters_ref;
    const origExpId = origRef?.experiment_id;
    if (!sessionToken || !origExpId) {
      setSelectedExperiments([]);
      return;
    }

    let cancelled = false;
    const loadOriginalExperiment = async () => {
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const parametersClient = clientFactory.getParametersClient();
        const exp = await parametersClient.getExperiment(origExpId);
        if (cancelled) return;
        const version = origRef?.version || exp.latest_version || undefined;
        if (!version) {
          setSelectedExperiments([]);
          return;
        }
        setSelectedExperiments([
          {
            experiment_id: exp.id,
            experiment_name: exp.name,
            version,
          },
        ]);
      } catch {
        if (!cancelled) setSelectedExperiments([]);
      }
    };

    loadOriginalExperiment();
    return () => {
      cancelled = true;
    };
  }, [
    sessionToken,
    open,
    rerunConfig.projectId,
    rerunConfig.originalAttributes,
  ]);

  // Handle adding a metric from the dialog
  const handleAddMetric = async (metricId: UUID) => {
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const metricsClient = clientFactory.getMetricsClient();
      const metric = await metricsClient.getMetric(metricId);
      if (metric) {
        setSelectedMetrics(prev => [
          ...prev,
          {
            id: metric.id as UUID,
            name: metric.name,
            scope: metric.metric_scope,
          },
        ]);
      }
    } catch (err) {
      console.error('Failed to fetch metric details:', err);
    }
  };

  // Handle removing a selected metric
  const handleRemoveMetric = (metricId: UUID) => {
    setSelectedMetrics(prev => prev.filter(m => m.id !== metricId));
  };

  const handleExecute = async () => {
    setExecuting(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = apiFactory.getTestSetsClient();

      const baseAttributes: Record<string, unknown> = {
        execution_mode: executionMode,
      };

      if (metricMode === 'define_custom' && selectedMetrics.length > 0) {
        baseAttributes.metrics = selectedMetrics.map(m => ({
          id: m.id,
          name: m.name,
          scope: m.scope,
        }));
      }

      if (selectedExecutionModelId) {
        baseAttributes.execution_model_id = selectedExecutionModelId;
      }
      if (selectedEvaluationModelId) {
        baseAttributes.evaluation_model_id = selectedEvaluationModelId;
      }

      if (scoringTarget === 'reuse' && rerunConfig.testRunId) {
        baseAttributes.reference_test_run_id = rerunConfig.testRunId;
      }

      const outcome = await executeBatchedTestRuns({
        testSetsClient,
        testSetIds: [rerunConfig.testSetId],
        endpointId: rerunConfig.endpointId,
        selectedExperiments,
        baseAttributes,
      });

      if (tags.length > 0) {
        try {
          const tagsClient = new TagsClient(sessionToken);
          const testRunsClient = apiFactory.getTestRunsClient();
          const endpointsClient = apiFactory.getEndpointsClient();
          const endpoint = await endpointsClient.getEndpoint(
            rerunConfig.endpointId
          );
          const organizationId = endpoint.organization_id as UUID;

          for (const member of outcome.members) {
            const resultAny = member.result as Record<string, unknown>;
            const testConfigurationId =
              (resultAny?.test_configuration_id as string | undefined) ?? null;
            if (!testConfigurationId) continue;

            const testRun = await pollForTestRun(
              testRunsClient,
              testConfigurationId
            );
            if (!testRun) continue;

            for (const tagName of tags) {
              const tagPayload: TagCreate = {
                name: tagName,
                ...(organizationId && { organization_id: organizationId }),
              };
              await tagsClient.assignTagToEntity(
                EntityType.TEST_RUN,
                testRun.id,
                tagPayload
              );
            }
          }
        } catch (tagError) {
          console.error('Failed to assign tags to test run(s):', tagError);
        }
      }

      const runCount = outcome.members.length;
      notifications.show(
        runCount > 1
          ? `Queued ${runCount} test runs (one per experiment)`
          : 'Test run queued successfully',
        { severity: 'success', autoHideDuration: 5000 }
      );

      if (onSuccess) {
        onSuccess();
      }

      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to start test run'));
      throw err;
    } finally {
      setExecuting(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Re-run Test"
      loading={loading || executing}
      error={error}
      onSave={handleExecute}
      saveButtonText="Re-run Test"
    >
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Stack spacing={3}>
          <Typography variant="subtitle2" color="text.secondary">
            Execution Target
          </Typography>

          <TextField
            label="Project"
            value={rerunConfig.projectName}
            disabled
            fullWidth
            InputProps={{
              readOnly: true,
            }}
          />

          <TextField
            label="Endpoint"
            value={rerunConfig.endpointName}
            disabled
            fullWidth
            InputProps={{
              readOnly: true,
            }}
          />

          <TextField
            label="Test Set"
            value={rerunConfig.testSetName}
            disabled
            fullWidth
            InputProps={{
              readOnly: true,
            }}
          />

          {rerunConfig.projectId && (
            <Box>
              <Alert severity="info" sx={{ mb: 2 }}>
                Each selected experiment triggers its own re-run with that
                experiment&apos;s parameters pinned. Leave empty to re-run
                without an experiment.
              </Alert>

              {selectedExperiments.length > 0 && (
                <Stack spacing={1} sx={{ mb: 2 }}>
                  {selectedExperiments.map(exp => (
                    <Box
                      key={exp.experiment_id}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        p: 1,
                        border: 1,
                        borderColor: 'divider',
                        borderRadius: theme => theme.spacing(1),
                      }}
                    >
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          minWidth: 0,
                        }}
                      >
                        <BiotechIcon fontSize="small" color="primary" />
                        <Box sx={{ minWidth: 0 }}>
                          <Typography variant="body2" noWrap>
                            {exp.experiment_name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Version {shortVersion(exp.version)}
                          </Typography>
                        </Box>
                      </Box>
                      <IconButton
                        size="small"
                        onClick={() =>
                          setSelectedExperiments(prev =>
                            prev.filter(
                              row => row.experiment_id !== exp.experiment_id
                            )
                          )
                        }
                      >
                        <CloseIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  ))}
                </Stack>
              )}

              <Button
                variant="outlined"
                size="small"
                startIcon={<AddIcon />}
                onClick={() => setExperimentsDialogOpen(true)}
              >
                Add Experiment
              </Button>
            </Box>
          )}

          <SelectExperimentsDialog
            open={experimentsDialogOpen}
            onClose={() => setExperimentsDialogOpen(false)}
            onConfirm={setSelectedExperiments}
            sessionToken={sessionToken}
            projectId={rerunConfig.projectId ?? null}
            initialSelection={selectedExperiments}
            title="Experiments for this re-run"
            subtitle="Selecting multiple experiments queues one re-run per experiment. Edit values inline to save a new version on the spot."
          />

          <Divider />

          <Typography variant="subtitle2" color="text.secondary">
            Configuration Options
          </Typography>

          <FormControl fullWidth>
            <InputLabel>Execution Mode</InputLabel>
            <Select
              value={executionMode}
              onChange={e => setExecutionMode(e.target.value)}
              label="Execution Mode"
            >
              <MenuItem value="Parallel">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CallSplitIcon fontSize="small" />
                  <Box>
                    <Typography variant="body1">Parallel</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Tests run simultaneously for faster execution (default)
                    </Typography>
                  </Box>
                </Box>
              </MenuItem>
              <MenuItem value="Sequential">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ArrowForwardIcon fontSize="small" />
                  <Box>
                    <Typography variant="body1">Sequential</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Tests run one after another, better for rate-limited
                      endpoints
                    </Typography>
                  </Box>
                </Box>
              </MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth>
            <InputLabel>Scoring Target</InputLabel>
            <Select
              value={scoringTarget}
              onChange={e => setScoringTarget(e.target.value as ScoringTarget)}
              label="Scoring Target"
            >
              <MenuItem value="fresh">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <BoltIcon fontSize="small" />
                  <Box>
                    <Typography variant="body1">Fresh Outputs</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Call the endpoint and score the new responses
                    </Typography>
                  </Box>
                </Box>
              </MenuItem>
              <MenuItem value="reuse">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ReplayIcon fontSize="small" />
                  <Box>
                    <Typography variant="body1">Reuse Outputs</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Re-score outputs from this test run
                    </Typography>
                  </Box>
                </Box>
              </MenuItem>
            </Select>
          </FormControl>

          {scoringTarget === 'reuse' && (
            <Alert severity="info">
              Outputs from this test run will be reused. Only metrics will be
              re-evaluated.
            </Alert>
          )}

          <Divider />

          {/* Model Settings Section */}
          <Typography variant="subtitle2" color="text.secondary">
            Model Settings
          </Typography>

          <ModelSelector
            sessionToken={sessionToken}
            value={selectedEvaluationModelId}
            onChange={setSelectedEvaluationModelId}
            label="Evaluation Model"
            purpose="evaluation"
            helperText="Used for scoring test results"
          />

          {scoringTarget === 'fresh' &&
            rerunConfig.testSetType === 'Multi-Turn' && (
              <ModelSelector
                sessionToken={sessionToken}
                value={selectedExecutionModelId}
                onChange={setSelectedExecutionModelId}
                label="Execution Model"
                purpose="execution"
                helperText="Used for multi-turn test execution with Penelope"
              />
            )}

          <Divider />

          {/* Test Run Metrics Section */}
          <Typography variant="subtitle2" color="text.secondary">
            Test Run Metrics
          </Typography>

          <FormControl fullWidth>
            <InputLabel>Metrics Source</InputLabel>
            <Select
              value={metricMode}
              onChange={e => {
                setMetricMode(e.target.value as MetricMode);
                if (e.target.value !== 'define_custom') {
                  setSelectedMetrics([]);
                }
              }}
              label="Metrics Source"
            >
              {testSetMetrics.length > 0 && (
                <MenuItem value="use_test_set">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <TuneIcon fontSize="small" />
                    <Box>
                      <Typography variant="body1">Test Set Metrics</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Use {testSetMetrics.length} metric
                        {testSetMetrics.length !== 1 ? 's' : ''} configured on
                        this test set
                      </Typography>
                    </Box>
                  </Box>
                </MenuItem>
              )}
              <MenuItem value="use_behavior">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <PsychologyIcon fontSize="small" />
                  <Box>
                    <Typography variant="body1">Behavior Metrics</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Use default metrics defined on each test&apos;s behavior
                    </Typography>
                  </Box>
                </Box>
              </MenuItem>
              <MenuItem value="define_custom">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <EditIcon fontSize="small" />
                  <Box>
                    <Typography variant="body1">Custom Metrics</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Define specific metrics for this execution only
                    </Typography>
                  </Box>
                </Box>
              </MenuItem>
            </Select>
          </FormControl>

          {metricMode === 'define_custom' && (
            <Box>
              <Alert severity="info" sx={{ mb: 2 }}>
                These metrics will only be used for this specific execution.
              </Alert>

              {selectedMetrics.length > 0 && (
                <Stack spacing={1} sx={{ mb: 2 }}>
                  {selectedMetrics.map(metric => (
                    <Box
                      key={metric.id}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        p: 1,
                        border: 1,
                        borderColor: 'divider',
                        borderRadius: theme => theme.spacing(1),
                      }}
                    >
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                      >
                        <AutoGraphIcon fontSize="small" color="primary" />
                        <Typography variant="body2">{metric.name}</Typography>
                      </Box>
                      <IconButton
                        size="small"
                        onClick={() => handleRemoveMetric(metric.id)}
                      >
                        <CloseIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  ))}
                </Stack>
              )}

              <Button
                variant="outlined"
                size="small"
                startIcon={<AddIcon />}
                onClick={() => setMetricsDialogOpen(true)}
              >
                Add Metric
              </Button>

              <SelectMetricsDialog
                open={metricsDialogOpen}
                onClose={() => setMetricsDialogOpen(false)}
                onSelect={handleAddMetric}
                sessionToken={sessionToken}
                excludeMetricIds={selectedMetrics.map(m => m.id)}
                title="Add Metric to Execution"
                subtitle="Select a metric to use for this test run"
                scopeFilter={rerunConfig.testSetType ?? undefined}
              />
            </Box>
          )}

          <Divider />

          {/* Tags Section */}
          <Typography variant="subtitle2" color="text.secondary">
            Test Run Tags
          </Typography>
          <BaseTag
            value={tags}
            onChange={setTags}
            label="Tags"
            placeholder="Add tags (press Enter or comma to add)"
            helperText="These tags help categorize and find this test run"
            chipColor="default"
            addOnBlur
            delimiters={[',', 'Enter']}
            size="small"
            fullWidth
            chipClassName={tagStyles.modalTag}
          />
        </Stack>
      )}
    </BaseDrawer>
  );
}
