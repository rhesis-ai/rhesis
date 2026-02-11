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
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
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
  const [name, setName] = useState<string>('');

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
        } catch (endpointsError) {
          setEndpoints([]);
        }
      } catch (error) {
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
      setName('');
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
      const testConfigurationsClient =
        clientFactory.getTestConfigurationsClient();
      const tagsClient = new TagsClient(sessionToken);

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

      // Get the test configuration IDs from results and assign name/tags if any
      const trimmedName = name.trim();
      if (trimmedName || tags.length > 0) {
        try {
          // Get endpoint to retrieve organization_id
          const endpointsClient = clientFactory.getEndpointsClient();
          const endpoint = await endpointsClient.getEndpoint(selectedEndpoint);

          const organizationId = endpoint.organization_id as UUID;
          const testRunsClient = clientFactory.getTestRunsClient();
          const tagsClient = new TagsClient(sessionToken);

          // Update name and assign tags to each created test run
          for (const result of results) {
            if ((result as any).test_configuration_id) {
              const testConfigurationId =
                (result as any).test_configuration_id;

              const testRun = await pollForTestRun(
                testRunsClient,
                testConfigurationId
              );

              if (testRun) {
                // Update the test run name if provided
                if (trimmedName) {
                  await testRunsClient.updateTestRun(testRun.id, {
                    name: trimmedName,
                  });
                }

                // Assign each tag to the test run
                if (tags.length > 0) {
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
                }
              } else {
                console.warn(
                  `Test run not found for configuration ` +
                    `${testConfigurationId}, ` +
                    `name and tags will not be assigned`
                );
              }
            }
          }
        } catch (postCreateError) {
          // Log error but don't fail the whole operation
          console.error(
            'Failed to update test run name/tags:',
            postCreateError
          );
        }
      }

      onSuccess?.();
    } catch (error) {
      onError?.('Failed to execute test sets');
    } finally {
      setLoading(false);
    }
  };

  // Attach submit handler to ref
  if (submitRef) {
    submitRef.current = handleSubmit;
  }

  const isFormValid = selectedProject && selectedEndpoint;

  return (
    <>
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Stack spacing={3}>
          <TextField
            label="Name"
            value={name}
            onChange={e => setName(e.target.value)}
            fullWidth
            placeholder="Leave blank for auto-generated name"
            helperText="Optional custom name. Leave blank for auto-generated name"
          />

          <Divider />

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
