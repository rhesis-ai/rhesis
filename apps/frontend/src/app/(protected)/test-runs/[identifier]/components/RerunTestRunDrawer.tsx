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
import {
  Add as AddIcon,
  Close as CloseIcon,
  AutoGraph as AutoGraphIcon,
  Tune as TuneIcon,
  Psychology as PsychologyIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { UUID } from 'crypto';
import BaseTag from '@/components/common/BaseTag';
import { EntityType, TagCreate } from '@/utils/api-client/interfaces/tag';
import { TagsClient } from '@/utils/api-client/tags-client';
import { pollForTestRun } from '@/utils/test-run-utils';
import tagStyles from '@/styles/BaseTag.module.css';
import SelectMetricsDialog from '@/components/common/SelectMetricsDialog';
import type { TestSetMetric } from '@/utils/api-client/interfaces/test-set';

type MetricMode = 'use_test_set' | 'use_behavior' | 'define_custom';

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
  projectName: string;
  /** Original test configuration attributes containing metrics if custom were used */
  originalAttributes?: {
    metrics?: OriginalMetric[];
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
      // Reset tags when drawer opens
      setTags([]);
    }
  }, [
    sessionToken,
    open,
    rerunConfig.testSetId,
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

      // Prepare test configuration attributes
      const testConfigurationAttributes: Record<string, unknown> = {
        execution_mode: 'Parallel',
      };

      // Add execution-time metrics if custom metrics are defined
      if (metricMode === 'define_custom' && selectedMetrics.length > 0) {
        testConfigurationAttributes.metrics = selectedMetrics.map(m => ({
          id: m.id,
          name: m.name,
          scope: m.scope,
        }));
      }

      // Execute test set against the endpoint (creates a new test configuration)
      const result = await testSetsClient.executeTestSet(
        rerunConfig.testSetId,
        rerunConfig.endpointId,
        testConfigurationAttributes
      );

      // Assign tags if any
      if (tags.length > 0) {
        try {
          const tagsClient = new TagsClient(sessionToken);

          // Get the test configuration ID from result and get the test run
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const resultAny = result as any;
          if (resultAny.test_configuration_id) {
            const testConfigurationId =
              resultAny.test_configuration_id as string;
            const testRunsClient = apiFactory.getTestRunsClient();

            const testRun = await pollForTestRun(
              testRunsClient,
              testConfigurationId
            );

            if (testRun) {
              // Get endpoint to retrieve organization_id
              const endpointsClient = apiFactory.getEndpointsClient();
              const endpoint = await endpointsClient.getEndpoint(
                rerunConfig.endpointId
              );
              const organizationId = endpoint.organization_id as UUID;

              // Assign each tag to the test run
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
          }
        } catch (tagError) {
          // Log error but don't fail the whole operation
          console.error('Failed to assign tags to test run:', tagError);
        }
      }

      // Show success notification
      notifications.show('Test run started successfully!', {
        severity: 'success',
        autoHideDuration: 5000,
      });

      // Call onSuccess callback if provided
      if (onSuccess) {
        onSuccess();
      }

      // Close drawer on success
      onClose();
    } catch (err) {
      setError('Failed to start test run');
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
                        borderRadius: 1,
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
                scopeFilter={
                  rerunConfig.testSetType === 'Single-Turn' ||
                  rerunConfig.testSetType === 'Multi-Turn'
                    ? (rerunConfig.testSetType as 'Single-Turn' | 'Multi-Turn')
                    : undefined
                }
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
