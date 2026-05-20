'use client';

import React, { useCallback } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import ModelSelector from '@/components/common/ModelSelector';
import SelectExperimentsDialog from '@/components/common/SelectExperimentsDialog';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import {
  Alert,
  Autocomplete,
  Button,
  IconButton,
  TextField,
  Box,
  Typography,
  Divider,
  Stack,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { UUID } from 'crypto';
import { useNotifications } from '@/components/common/NotificationContext';
import BaseTag from '@/components/common/BaseTag';
import { EntityType, TagCreate } from '@/utils/api-client/interfaces/tag';
import { TagsClient } from '@/utils/api-client/tags-client';
import { pollForTestRun } from '@/utils/test-run-utils';
import { getApiErrorMessage } from '@/utils/error-utils';
import {
  executeBatchedTestRuns,
  type SelectedExperiment,
} from '@/utils/test-run-batch';
import { BiotechIcon } from '@/components/icons';
import { shortVersion } from '@/utils/api-client/interfaces/parameters';

interface TestRunDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  testRun?: TestRunDetail;
  onSuccess?: () => void;
}

export default function TestRunDrawer({
  open,
  onClose,
  sessionToken,
  testRun,
  onSuccess,
}: TestRunDrawerProps) {
  const notifications = useNotifications();
  const [error, setError] = React.useState<string>();
  const [loading, setLoading] = React.useState(false);
  const [testSet, setTestSet] = React.useState<TestSet | null>(null);
  const [project, setProject] = React.useState<Project | null>(null);
  const [endpoint, setEndpoint] = React.useState<Endpoint | null>(null);

  const [testSets, setTestSets] = React.useState<TestSet[]>([]);
  const [projects, setProjects] = React.useState<Project[]>([]);
  const [endpoints, setEndpoints] = React.useState<Endpoint[]>([]);
  const [filteredEndpoints, setFilteredEndpoints] = React.useState<Endpoint[]>(
    []
  );
  const [tags, setTags] = React.useState<string[]>([]);
  const [selectedExecutionModelId, setSelectedExecutionModelId] =
    React.useState('');
  const [selectedEvaluationModelId, setSelectedEvaluationModelId] =
    React.useState('');

  // Experiment fan-out (optional): when set, each experiment triggers
  // its own run via the shared batch helper.
  const [selectedExperiments, setSelectedExperiments] = React.useState<
    SelectedExperiment[]
  >([]);
  const [experimentsDialogOpen, setExperimentsDialogOpen] =
    React.useState(false);

  const getCurrentUserId = useCallback((): UUID | undefined => {
    try {
      const [, payloadBase64] = sessionToken.split('.');
      const base64 = payloadBase64.replace(/-/g, '+').replace(/_/g, '/');
      const pad = base64.length % 4;
      const paddedBase64 = pad ? base64 + '='.repeat(4 - pad) : base64;

      const payload = JSON.parse(
        Buffer.from(paddedBase64, 'base64').toString('utf-8')
      ) as { user?: { id?: UUID } };
      return payload.user?.id;
    } catch (_err) {
      return undefined;
    }
  }, [sessionToken]);

  // Load initial data
  React.useEffect(() => {
    const loadData = async () => {
      if (!sessionToken || !open) return;

      try {
        setLoading(true);
        setError(undefined);

        const clientFactory = new ApiClientFactory(sessionToken);
        const testSetsClient = clientFactory.getTestSetsClient();
        const projectsClient = clientFactory.getProjectsClient();
        const endpointsClient = clientFactory.getEndpointsClient();

        try {
          const [fetchedTestSets, fetchedProjects, fetchedEndpoints] =
            await Promise.all([
              testSetsClient.getTestSets({ limit: 100 }),
              projectsClient.getProjects(),
              endpointsClient.getEndpoints(),
            ]);

          // Ensure we always set arrays, never undefined
          setTestSets(
            Array.isArray(fetchedTestSets?.data) ? fetchedTestSets.data : []
          );

          // Handle both response formats for projects: direct array or {data: array}
          let projectsArray: Project[] = [];
          if (Array.isArray(fetchedProjects)) {
            // Direct array response (what we're getting)
            projectsArray = fetchedProjects;
          } else if (fetchedProjects && Array.isArray(fetchedProjects.data)) {
            // Paginated response with data property
            projectsArray = fetchedProjects.data;
          } else {
          }

          setProjects(projectsArray);
          setEndpoints(
            Array.isArray(fetchedEndpoints?.data) ? fetchedEndpoints.data : []
          );

          // Set initial values if editing
          if (testRun) {
            // Set tags if available
            if (testRun.tags && testRun.tags.length > 0) {
              setTags(testRun.tags.map(tag => tag.name));
            } else {
              setTags([]);
            }
          } else {
            // Reset tags for new test runs
            setTags([]);
          }
          setSelectedExecutionModelId('');
          setSelectedEvaluationModelId('');
          setSelectedExperiments([]);
        } catch (_fetchError) {
          setError('Failed to load required data');
          // Ensure state remains as empty arrays even on error
          setTestSets([]);
          setProjects([]);
          setEndpoints([]);
          setFilteredEndpoints([]);
        }
      } catch (_err) {
        setError('Failed to load required data');
      } finally {
        setLoading(false);
      }
    };

    if (open) {
      loadData();
    }
  }, [sessionToken, testRun, getCurrentUserId, open]);

  // Filter endpoints when project changes
  React.useEffect(() => {
    if (project && Array.isArray(endpoints)) {
      const filtered = endpoints.filter(
        endpoint => endpoint.project_id === project.id
      );
      setFilteredEndpoints(filtered);
      // Clear endpoint selection if current selection is not in filtered list
      if (endpoint && !filtered.find(e => e.id === endpoint.id)) {
        setEndpoint(null);
      }
    } else {
      setFilteredEndpoints([]);
      setEndpoint(null);
    }
  }, [project, endpoints, endpoint]);

  // Experiments are project-scoped — drop any pinned ones if the user
  // switches project so they can't accidentally submit a cross-project
  // experiment.
  React.useEffect(() => {
    setSelectedExperiments([]);
  }, [project]);

  const handleSave = async () => {
    if (!sessionToken || !testSet || !endpoint) {
      setError('Please select a test set and endpoint');
      return;
    }

    try {
      setLoading(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();
      const currentUserId = getCurrentUserId();

      const baseAttributes: Record<string, unknown> = {
        ...(selectedExecutionModelId && {
          execution_model_id: selectedExecutionModelId,
        }),
        ...(selectedEvaluationModelId && {
          evaluation_model_id: selectedEvaluationModelId,
        }),
      };

      // Routed through the shared batch helper for consistency with the
      // other launch surfaces: experiment fan-out, ``batch_*`` metadata,
      // and the same ``executeTestSet`` request shape land on the same
      // queue path.
      const outcome = await executeBatchedTestRuns({
        testSetsClient,
        testSetIds: [testSet.id as string],
        endpointId: endpoint.id as string,
        selectedExperiments,
        baseAttributes,
      });

      if (tags.length > 0) {
        try {
          const testRunsClient = clientFactory.getTestRunsClient();
          const tagsClient = new TagsClient(sessionToken);
          const organizationId = endpoint.organization_id as UUID;

          for (const member of outcome.members) {
            const resultRecord = member.result as Record<string, unknown>;
            const testConfigurationId =
              (resultRecord?.test_configuration_id as string | undefined) ??
              null;
            if (!testConfigurationId) continue;

            const testRun = await pollForTestRun(
              testRunsClient,
              testConfigurationId
            );
            if (!testRun) {
              console.warn(
                'Test run not found after polling, tags will not be assigned'
              );
              continue;
            }
            for (const tagName of tags) {
              const tagPayload: TagCreate = {
                name: tagName,
                ...(organizationId && { organization_id: organizationId }),
                ...(currentUserId && { user_id: currentUserId }),
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
          : 'Test execution queued successfully',
        { severity: 'success' }
      );

      onSuccess?.();
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to execute test run'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Test Run Configuration"
      loading={loading}
      error={error}
      onSave={handleSave}
      saveButtonText="Execute Now"
    >
      <Stack spacing={3}>
        {/* Test Run Configuration Section */}
        <Stack spacing={2}>
          <Typography variant="subtitle2" color="text.secondary">
            Test Run Configuration
          </Typography>

          <Stack spacing={2}>
            <Autocomplete
              options={Array.isArray(testSets) ? testSets : []}
              value={testSet}
              onChange={(_, newValue) => setTestSet(newValue)}
              getOptionLabel={option => option.name || 'Unnamed Test Set'}
              isOptionEqualToValue={(option, value) => option.id === value.id}
              renderOption={(props, option) => {
                const { key: _key, ...otherProps } = props;
                return (
                  <Box component="li" key={option.id} {...otherProps}>
                    {option.name || 'Unnamed Test Set'}
                  </Box>
                );
              }}
              fullWidth
              renderInput={params => (
                <TextField {...params} label="Test Set" required />
              )}
            />

            <Autocomplete
              options={Array.isArray(projects) ? projects : []}
              value={project}
              onChange={(_, newValue) => setProject(newValue)}
              getOptionLabel={option => option.name}
              isOptionEqualToValue={(option, value) => option.id === value.id}
              renderOption={(props, option) => {
                const { key: _key, ...otherProps } = props;
                return (
                  <Box component="li" key={option.id} {...otherProps}>
                    {option.name}
                  </Box>
                );
              }}
              fullWidth
              renderInput={params => (
                <TextField {...params} label="Project" required />
              )}
            />

            <Autocomplete
              options={
                Array.isArray(filteredEndpoints) ? filteredEndpoints : []
              }
              value={endpoint}
              onChange={(_, newValue) => setEndpoint(newValue)}
              getOptionLabel={option =>
                `${option.name} (${option.environment})`
              }
              disabled={!project}
              fullWidth
              renderInput={params => (
                <TextField
                  {...params}
                  label="Endpoint"
                  required
                  helperText={!project ? 'Select a project first' : undefined}
                />
              )}
            />

            {project && (
              <Box>
                <Alert severity="info" sx={{ mb: 2 }}>
                  Each selected experiment triggers its own test run
                  with that experiment&apos;s parameters pinned. Leave
                  empty to run without an experiment.
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
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              Version {shortVersion(exp.version)}
                            </Typography>
                          </Box>
                        </Box>
                        <IconButton
                          size="small"
                          onClick={() =>
                            setSelectedExperiments(prev =>
                              prev.filter(
                                row =>
                                  row.experiment_id !== exp.experiment_id
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
              projectId={(project?.id as string) ?? null}
              initialSelection={selectedExperiments}
              title="Experiments for this run"
              subtitle="Selecting multiple experiments queues one run per experiment."
            />
          </Stack>
        </Stack>

        <Divider />

        {/* Model Settings Section */}
        <Stack spacing={2}>
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

          {testSet?.test_set_type?.type_value === 'Multi-Turn' && (
            <ModelSelector
              sessionToken={sessionToken}
              value={selectedExecutionModelId}
              onChange={setSelectedExecutionModelId}
              label="Execution Model"
              purpose="execution"
              helperText="Used for multi-turn test execution with Penelope"
            />
          )}
        </Stack>

        <Divider />

        {/* Tags Section */}
        <Stack spacing={2}>
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
            size="medium"
            fullWidth
            sx={{
              '& .MuiInputBase-root': {
                minHeight: '56px',
                alignItems: 'flex-start',
                paddingTop: 1,
                paddingBottom: 1,
              },
            }}
          />
        </Stack>
      </Stack>
    </BaseDrawer>
  );
}
