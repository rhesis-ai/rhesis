import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Typography,
  FormControl,
  IconButton,
  InputLabel,
  Select,
  MenuItem,
  Divider,
  Chip,
  Stack,
  Autocomplete,
  TextField,
  FormHelperText,
  CircularProgress,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Project } from '@/utils/api-client/interfaces/project';
import { EntityType, TagCreate } from '@/utils/api-client/interfaces/tag';
import { UUID } from 'crypto';
import BaseTag from '@/components/common/BaseTag';
import { TagsClient } from '@/utils/api-client/tags-client';
import { pollForTestRun } from '@/utils/test-run-utils';
import { getApiErrorMessage } from '@/utils/error-utils';
import tagStyles from '@/styles/BaseTag.module.css';
import ModelSelector from '@/components/common/ModelSelector';
import SelectExperimentsDialog from '@/components/common/SelectExperimentsDialog';
import {
  executeBatchedTestRuns,
  type SelectedExperiment,
} from '@/utils/test-run-batch';
import { BiotechIcon } from '@/components/icons';
import { shortVersion } from '@/utils/api-client/interfaces/parameters';

interface ProjectOption {
  id: UUID;
  name: string;
  nano_id?: string;
  created_at?: string;
}

interface EndpointOption {
  id: UUID;
  name: string;
  environment?: 'development' | 'staging' | 'production' | 'local';
  project_id?: string;
}

// Import execution mode icons directly from Material-UI
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CallSplitIcon from '@mui/icons-material/CallSplit';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';

interface CreateTestRunProps {
  open: boolean;
  sessionToken: string;
  selectedTestSetIds: string[];
  onSuccess?: () => void;
  onError?: (error: string) => void;
  submitRef?: React.MutableRefObject<(() => Promise<void>) | undefined>;
}

export default function CreateTestRun({
  open,
  sessionToken,
  selectedTestSetIds,
  onSuccess,
  onError,
  submitRef,
}: CreateTestRunProps) {
  const [loading, setLoading] = useState(false);
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [endpoints, setEndpoints] = useState<EndpointOption[]>([]);
  const [filteredEndpoints, setFilteredEndpoints] = useState<EndpointOption[]>(
    []
  );
  const [selectedProject, setSelectedProject] = useState<UUID | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<UUID | null>(null);
  const [executionMode, setExecutionMode] = useState<string>('Parallel');
  const [tags, setTags] = useState<string[]>([]);
  const [selectedExecutionModelId, setSelectedExecutionModelId] = useState('');
  const [selectedEvaluationModelId, setSelectedEvaluationModelId] =
    useState('');

  // Experiment fan-out: bulk-running selectedTestSets.length test sets
  // against selectedExperiments.length experiments produces
  // ``testSets × experiments`` runs, all sharing one ``batch_id``.
  const [selectedExperiments, setSelectedExperiments] = useState<
    SelectedExperiment[]
  >([]);
  const [experimentsDialogOpen, setExperimentsDialogOpen] = useState(false);

  // Fetch projects and endpoints when drawer opens
  useEffect(() => {
    if (!sessionToken || !open) {
      return;
    }

    const fetchInitialData = async () => {
      try {
        const clientFactory = new ApiClientFactory(sessionToken);

        // Fetch projects with proper response handling
        const projectsClient = clientFactory.getProjectsClient();

        const projectsData = await projectsClient.getProjects({
          sort_by: 'name',
          sort_order: 'asc',
          limit: 100,
        });

        // Handle both response formats: direct array or {data: array}
        let projectsArray: Project[] = [];
        if (Array.isArray(projectsData)) {
          // Direct array response
          projectsArray = projectsData;
        } else if (projectsData && Array.isArray(projectsData.data)) {
          // Paginated response with data property
          projectsArray = projectsData.data;
        } else {
        }

        const processedProjects = projectsArray
          .filter((p: Project) => p.id && p.name && p.name.trim() !== '')
          .map((p: Project) => ({
            id: p.id as UUID,
            name: p.name,
            nano_id: (p as Project & { nano_id?: string }).nano_id,
            created_at: p.created_at,
          }));

        setProjects(processedProjects);

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
        setProjects([]); // Ensure projects remains an empty array on error
        setEndpoints([]);
        onError?.('Failed to load initial data');
      }
    };

    if (open) {
      fetchInitialData();
      // Reset selections when drawer opens
      setSelectedProject(null);
      setSelectedEndpoint(null);
      setTags([]);
      setSelectedExecutionModelId('');
      setSelectedEvaluationModelId('');
      setSelectedExperiments([]);
    }
  }, [sessionToken, onError, selectedTestSetIds, open]);

  // Experiments are project-scoped; switching project invalidates any
  // previously selected ones.
  useEffect(() => {
    setSelectedExperiments([]);
  }, [selectedProject]);

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

  const handleSubmit = async () => {
    if (!selectedEndpoint || selectedTestSetIds.length === 0) {
      onError?.('Please select an endpoint');
      return;
    }

    setLoading(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();

      const baseAttributes: Record<string, unknown> = {
        execution_mode: executionMode,
      };
      if (selectedExecutionModelId) {
        baseAttributes.execution_model_id = selectedExecutionModelId;
      }
      if (selectedEvaluationModelId) {
        baseAttributes.evaluation_model_id = selectedEvaluationModelId;
      }

      const outcome = await executeBatchedTestRuns({
        testSetsClient,
        testSetIds: selectedTestSetIds,
        endpointId: selectedEndpoint,
        selectedExperiments,
        baseAttributes,
      });

      if (tags.length > 0) {
        try {
          const endpointsClient = clientFactory.getEndpointsClient();
          const endpoint = await endpointsClient.getEndpoint(selectedEndpoint);
          const organizationId = endpoint.organization_id as UUID;
          const testRunsClient = clientFactory.getTestRunsClient();
          const tagsClient = new TagsClient(sessionToken);

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
                `Test run not found for configuration ${testConfigurationId}, tags will not be assigned`
              );
              continue;
            }
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
          console.error('Failed to assign tags to test runs:', tagError);
        }
      }

      onSuccess?.();
    } catch (error) {
      onError?.(getApiErrorMessage(error, 'Failed to execute test sets'));
    } finally {
      setLoading(false);
    }
  };

  // Attach submit handler to ref
  if (submitRef) {
    submitRef.current = handleSubmit;
  }

  const _isFormValid = selectedProject && selectedEndpoint;

  return (
    <>
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
              getOptionLabel={option => {
                const hasDuplicate =
                  projects.filter(p => p.name === option.name).length > 1;
                if (!hasDuplicate) return option.name;
                const suffix = option.nano_id
                  ? option.nano_id.slice(0, 6)
                  : option.id.slice(0, 6);
                return `${option.name} (${suffix})`;
              }}
              renderOption={(props, option) => {
                const { key: _key, ...otherProps } = props;
                const hasDuplicate =
                  projects.filter(p => p.name === option.name).length > 1;
                return (
                  <Box component="li" key={option.id} {...otherProps}>
                    <Box>
                      <Typography variant="body2">{option.name}</Typography>
                      {hasDuplicate && (
                        <Typography variant="caption" color="text.secondary">
                          {option.created_at
                            ? `Created ${new Date(option.created_at).toLocaleDateString()}`
                            : `ID: ${option.nano_id ?? option.id.slice(0, 8)}`}
                        </Typography>
                      )}
                    </Box>
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
                const { key: _key, ...otherProps } = props;
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

          {selectedProject && (
            <Box>
              <Alert severity="info" sx={{ mb: 2 }}>
                Each selected experiment runs against every selected
                test set, producing one run per combination. Leave empty
                to run each test set once with no pinned parameters.
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
            projectId={selectedProject}
            initialSelection={selectedExperiments}
            title="Experiments for this bulk run"
            subtitle="Each selected experiment runs against every selected test set, producing one run per combination."
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
          />

          <ModelSelector
            sessionToken={sessionToken}
            value={selectedExecutionModelId}
            onChange={setSelectedExecutionModelId}
            label="Execution Model"
            purpose="execution"
            helperText="Only applies to multi-turn test sets"
          />

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
    </>
  );
}
