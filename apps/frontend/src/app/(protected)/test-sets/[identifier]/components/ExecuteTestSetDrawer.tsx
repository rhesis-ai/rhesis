import { useState, useEffect } from 'react';
import {
  Box,
  CircularProgress,
  Chip,
  Stack,
  Autocomplete,
  TextField,
  FormControl,
  FormHelperText,
  Divider,
  Typography,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Button,
  IconButton,
} from '@mui/material';
import {
  ArrowForward as ArrowForwardIcon,
  CallSplit as CallSplitIcon,
  Add as AddIcon,
  Close as CloseIcon,
  AutoGraph as AutoGraphIcon,
  Tune as TuneIcon,
  Psychology as PsychologyIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Project } from '@/utils/api-client/interfaces/project';
import { useNotifications } from '@/components/common/NotificationContext';
import { UUID } from 'crypto';
import BaseTag from '@/components/common/BaseTag';
import { EntityType, TagCreate } from '@/utils/api-client/interfaces/tag';
import { TagsClient } from '@/utils/api-client/tags-client';
import { pollForTestRun } from '@/utils/test-run-utils';
import tagStyles from '@/styles/BaseTag.module.css';
import SelectMetricsDialog from '@/components/common/SelectMetricsDialog';
import type { TestSetMetric } from '@/utils/api-client/interfaces/test-set';

interface ProjectOption {
  id: UUID;
  name: string;
}

interface EndpointOption {
  id: UUID;
  name: string;
  environment?: 'development' | 'staging' | 'production' | 'local';
  project_id?: string;
}

type MetricMode = 'use_test_set' | 'use_behavior' | 'define_custom';

interface SelectedMetric {
  id: UUID;
  name: string;
  scope?: string[];
}

interface ExecuteTestSetDrawerProps {
  open: boolean;
  onClose: () => void;
  testSetId: string;
  sessionToken: string;
}

export default function ExecuteTestSetDrawer({
  open,
  onClose,
  testSetId,
  sessionToken,
}: ExecuteTestSetDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [endpoints, setEndpoints] = useState<EndpointOption[]>([]);
  const [filteredEndpoints, setFilteredEndpoints] = useState<EndpointOption[]>(
    []
  );
  const [selectedProject, setSelectedProject] = useState<UUID | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<UUID | null>(null);
  const [executionMode, setExecutionMode] = useState<string>('Parallel');
  const [tags, setTags] = useState<string[]>([]);
  const notifications = useNotifications();

  // Test set info state
  const [testSetType, setTestSetType] = useState<string | null>(null);
  const [testSetMetrics, setTestSetMetrics] = useState<TestSetMetric[]>([]);

  // Metrics section state
  const [metricMode, setMetricMode] = useState<MetricMode>('use_behavior');
  const [selectedMetrics, setSelectedMetrics] = useState<SelectedMetric[]>([]);
  const [metricsDialogOpen, setMetricsDialogOpen] = useState(false);

  // Fetch projects, endpoints, and test set info when drawer opens
  useEffect(() => {
    const fetchData = async () => {
      if (!sessionToken || !open) return;

      try {
        setLoading(true);
        setError(undefined);

        const clientFactory = new ApiClientFactory(sessionToken);

        // Fetch test set info (type and metrics)
        try {
          const testSetsClient = clientFactory.getTestSetsClient();
          const testSet = await testSetsClient.getTestSet(testSetId);
          if (testSet) {
            // Get test set type
            const typeValue = testSet.test_set_type?.type_value || null;
            setTestSetType(typeValue);

            // Get test set metrics
            const metrics = await testSetsClient.getTestSetMetrics(testSetId);
            setTestSetMetrics(metrics || []);

            // Set default metric mode based on whether test set has metrics
            if (metrics && metrics.length > 0) {
              setMetricMode('use_test_set');
            } else {
              setMetricMode('use_behavior');
            }
          }
        } catch (testSetError) {
          console.warn('Failed to fetch test set info:', testSetError);
          setTestSetType(null);
          setTestSetMetrics([]);
          setMetricMode('use_behavior');
        }

        // Fetch projects
        try {
          const projectsClient = clientFactory.getProjectsClient();
          const projectsData = await projectsClient.getProjects({
            sort_by: 'name',
            sort_order: 'asc',
            limit: 100,
          });

          // Handle both response formats: direct array or {data: array}
          let projectsArray: Project[] = [];
          if (Array.isArray(projectsData)) {
            projectsArray = projectsData;
          } else if (projectsData && Array.isArray(projectsData.data)) {
            projectsArray = projectsData.data;
          }

          const processedProjects = projectsArray
            .filter((p: Project) => p.id && p.name && p.name.trim() !== '')
            .map((p: Project) => ({ id: p.id as UUID, name: p.name }));

          setProjects(processedProjects);
        } catch (_projectsError) {
          setProjects([]);
        }

        // Fetch all endpoints
        try {
          const endpointsClient = clientFactory.getEndpointsClient();
          const endpointsResponse = await endpointsClient.getEndpoints({
            sort_by: 'name',
            sort_order: 'asc',
            limit: 100,
          });

          if (endpointsResponse && Array.isArray(endpointsResponse.data)) {
            const processedEndpoints = endpointsResponse.data
              .filter(e => e.id && e.name && e.name.trim() !== '')
              .map(e => ({
                id: e.id as UUID,
                name: e.name,
                environment: e.environment,
                project_id: e.project_id,
              }));

            setEndpoints(processedEndpoints);
          } else {
            setEndpoints([]);
          }
        } catch (_endpointsError) {
          setEndpoints([]);
        }
      } catch (_error) {
        setError(
          'Failed to load data. Please check your connection and try again.'
        );
      } finally {
        setLoading(false);
      }
    };

    if (open) {
      fetchData();
      // Reset selections when drawer opens
      setSelectedProject(null);
      setSelectedEndpoint(null);
      setTags([]);
      setSelectedMetrics([]);
    }
  }, [sessionToken, open, testSetId]);

  // Filter endpoints when project changes
  useEffect(() => {
    if (!selectedProject) {
      setFilteredEndpoints([]);
      setSelectedEndpoint(null);
      return;
    }

    // Filter endpoints that belong to the selected project
    const filtered = endpoints.filter(
      endpoint => endpoint.project_id === selectedProject
    );
    setFilteredEndpoints(filtered);

    // Reset selected endpoint when project changes
    setSelectedEndpoint(null);
  }, [selectedProject, endpoints]);

  const handleEndpointChange = (value: EndpointOption | null) => {
    if (!value) {
      setSelectedEndpoint(null);
      return;
    }

    setSelectedEndpoint(value.id);
  };

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
    if (!selectedEndpoint) return;

    setExecuting(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = apiFactory.getTestSetsClient();
      const tagsClient = new TagsClient(sessionToken);

      // Prepare test configuration attributes
      const testConfigurationAttributes: Record<string, any> = {
        execution_mode: executionMode,
      };

      // Add execution-time metrics if custom metrics are defined
      if (metricMode === 'define_custom' && selectedMetrics.length > 0) {
        testConfigurationAttributes.metrics = selectedMetrics.map(m => ({
          id: m.id,
          name: m.name,
          scope: m.scope,
        }));
      }

      // Execute test set against the selected endpoint with test configuration attributes
      const result = await testSetsClient.executeTestSet(
        testSetId,
        selectedEndpoint,
        testConfigurationAttributes
      );

      // Assign tags if any
      if (tags.length > 0) {
        try {
          // Get endpoint to retrieve organization_id
          const endpointsClient = apiFactory.getEndpointsClient();
          const endpoint = await endpointsClient.getEndpoint(selectedEndpoint);

          const organizationId = endpoint.organization_id as UUID;

          // Get the test configuration ID from result and get the test run
          if ((result as any).test_configuration_id) {
            const testConfigurationId = (result as any).test_configuration_id;
            const testRunsClient = apiFactory.getTestRunsClient();
            const tagsClient = new TagsClient(sessionToken);

            const testRun = await pollForTestRun(
              testRunsClient,
              testConfigurationId
            );

            if (testRun) {
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
            } else {
              console.warn(
                `Test run not found for configuration ${testConfigurationId}, tags will not be assigned`
              );
            }
          }
        } catch (tagError) {
          // Log error but don't fail the whole operation
          console.error('Failed to assign tags to test run:', tagError);
        }
      }

      // Show success notification
      notifications.show('Test set execution started successfully!', {
        severity: 'success',
        autoHideDuration: 5000,
      });

      // Close drawer on success
      onClose();
    } catch (err) {
      setError('Failed to execute test set');
      throw err; // Re-throw so BaseDrawer can handle the error state
    } finally {
      setExecuting(false);
    }
  };

  const isFormValid = selectedProject && selectedEndpoint;

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Execute Test Set"
      loading={loading || executing}
      error={error}
      onSave={handleExecute}
      saveDisabled={!isFormValid}
      saveButtonText="Execute Test Set"
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

          <FormControl fullWidth>
            <Autocomplete
              options={projects}
              value={projects.find(p => p.id === selectedProject) || null}
              onChange={(_, newValue) => {
                if (!newValue) {
                  setSelectedProject(null);
                  return;
                }
                setSelectedProject(newValue.id);
                setSelectedEndpoint(null);
              }}
              getOptionLabel={option => option.name}
              renderOption={(props, option) => {
                const { key, ...otherProps } = props;
                return (
                  <Box component="li" key={option.id} {...otherProps}>
                    {option.name}
                  </Box>
                );
              }}
              renderInput={params => (
                <TextField
                  {...params}
                  label="Project"
                  required
                  placeholder="Select a project"
                />
              )}
              isOptionEqualToValue={(option, value) => option.id === value.id}
            />
            {projects.length === 0 && !loading && (
              <FormHelperText>No projects available</FormHelperText>
            )}
          </FormControl>

          <FormControl fullWidth>
            <Autocomplete
              options={filteredEndpoints}
              value={
                filteredEndpoints.find(e => e.id === selectedEndpoint) || null
              }
              onChange={(_, newValue) => handleEndpointChange(newValue)}
              getOptionLabel={option => option.name}
              disabled={!selectedProject}
              renderInput={params => (
                <TextField
                  {...params}
                  label="Endpoint"
                  required
                  placeholder={
                    selectedProject
                      ? 'Select endpoint'
                      : 'Select a project first'
                  }
                />
              )}
              renderOption={(props, option) => {
                const { key, ...otherProps } = props;
                return (
                  <Box
                    key={option.id}
                    {...otherProps}
                    component="li"
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span>{option.name}</span>
                    {option.environment && (
                      <Chip
                        label={option.environment}
                        size="small"
                        color={
                          option.environment === 'production'
                            ? 'error'
                            : option.environment === 'staging'
                              ? 'warning'
                              : 'success'
                        }
                        sx={{ ml: 1 }}
                      />
                    )}
                  </Box>
                );
              }}
              isOptionEqualToValue={(option, value) => option.id === value.id}
            />
            {filteredEndpoints.length === 0 && selectedProject && !loading && (
              <FormHelperText>
                No endpoints available for this project
              </FormHelperText>
            )}
          </FormControl>

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
                These metrics will only be used for this specific execution and
                will not be saved to the test set.
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
                scopeFilter={
                  testSetType === 'Single-Turn' || testSetType === 'Multi-Turn'
                    ? (testSetType as 'Single-Turn' | 'Multi-Turn')
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
