import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  FormControl,
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
import tagStyles from '@/styles/BaseTag.module.css';

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

// Import execution mode icons directly from Material-UI
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CallSplitIcon from '@mui/icons-material/CallSplit';

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
          .map((p: Project) => ({ id: p.id as UUID, name: p.name }));

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
    }
  }, [sessionToken, onError, selectedTestSetIds, open]);

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

      // Prepare test configuration attributes
      const testConfigurationAttributes = {
        execution_mode: executionMode,
      };

      // Execute each test set individually with test configuration attributes
      const results = await Promise.all(
        selectedTestSetIds.map(testSetId =>
          testSetsClient.executeTestSet(
            testSetId,
            selectedEndpoint,
            testConfigurationAttributes
          )
        )
      );

      // Get the test configuration IDs from results and assign tags if any
      if (tags.length > 0) {
        try {
          // Get endpoint to retrieve organization_id
          const endpointsClient = clientFactory.getEndpointsClient();
          const endpoint = await endpointsClient.getEndpoint(selectedEndpoint);

          const organizationId = endpoint.organization_id as UUID;
          const testRunsClient = clientFactory.getTestRunsClient();
          const tagsClient = new TagsClient(sessionToken);

          // Assign tags to each created test run
          for (const result of results) {
            // The result should contain test_configuration_id
            // We need to get the test run from the test configuration
            const resultRecord = result as unknown as Record<string, unknown>;
            if (resultRecord.test_configuration_id) {
              const testConfigurationId = resultRecord.test_configuration_id as string;

              const testRun = await pollForTestRun(
                testRunsClient,
                testConfigurationId
              );

              if (testRun) {
                for (const tagName of tags) {
                  const tagPayload: TagCreate = {
                    name: tagName,
                    ...(organizationId && {
                      organization_id: organizationId,
                    }),
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
          }
        } catch (tagError) {
          // Log error but don't fail the whole operation
          console.error('Failed to assign tags to test runs:', tagError);
        }
      }

      onSuccess?.();
    } catch (_error) {
      onError?.('Failed to execute test sets');
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
              getOptionLabel={option => option.name}
              renderOption={(props, option) => {
                const { key: _key, ...otherProps } = props;
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
