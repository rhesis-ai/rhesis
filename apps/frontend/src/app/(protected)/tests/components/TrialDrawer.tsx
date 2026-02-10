'use client';

import React, { useState, useEffect, useRef } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import ConversationHistory from '@/components/common/ConversationHistory';
import {
  Box,
  Typography,
  FormControl,
  FormHelperText,
  CircularProgress,
  Paper,
  Chip,
  Autocomplete,
  TextField,
  useTheme,
  Button,
  Collapse,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Project } from '@/utils/api-client/interfaces/project';
import { useNotifications } from '@/components/common/NotificationContext';
import { UUID } from 'crypto';
import { isMultiTurnTest } from '@/constants/test-types';
import {
  isMultiTurnConfig,
  MultiTurnTestConfig,
} from '@/utils/api-client/interfaces/multi-turn-test-config';

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

interface TrialDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  testIds: string[];
  onSuccess?: () => void;
}

export default function TrialDrawer({
  open,
  onClose,
  sessionToken,
  testIds,
  onSuccess: _onSuccess,
}: TrialDrawerProps) {
  const [error, setError] = useState<string>();
  const theme = useTheme();
  const [loading, setLoading] = useState(false);
  const [testData, setTestData] = useState<TestDetail | null>(null);
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [endpoints, setEndpoints] = useState<EndpointOption[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<string | null>(null);
  const [filteredEndpoints, setFilteredEndpoints] = useState<EndpointOption[]>(
    []
  );
  const [trialResponse, setTrialResponse] = useState<any>(null);
  const [trialInProgress, setTrialInProgress] = useState(false);
  const [_trialCompleted, setTrialCompleted] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [selectedProjectData, setSelectedProjectData] =
    useState<Project | null>(null);
  const notifications = useNotifications();
  const hasLoadedRef = useRef(false);
  const testIdsRef = useRef<string>('');

  // Fetch projects, endpoints, and test data
  useEffect(() => {
    const fetchData = async () => {
      if (!sessionToken || !open) {
        return;
      }

      // Check if testIds actually changed (not just reference)
      const testIdsKey = JSON.stringify(testIds);
      const isTestIdsChanged = testIdsRef.current !== testIdsKey;
      testIdsRef.current = testIdsKey;

      // Only fetch if it's the first load or testIds actually changed
      if (!isTestIdsChanged && hasLoadedRef.current) {
        return;
      }

      // Only reset state on initial open, not on subsequent re-renders
      const isInitialOpen = !hasLoadedRef.current;

      try {
        setLoading(true);
        if (isInitialOpen) {
          setTrialResponse(null);
          setTrialCompleted(false);
          setError(undefined);
        }
        const clientFactory = new ApiClientFactory(sessionToken);

        // Fetch test data (we only support single test trial for now)
        if (testIds.length > 0) {
          try {
            const testsClient = clientFactory.getTestsClient();
            const testDetail = await testsClient.getTest(testIds[0]);

            // If test has a prompt_id but no prompt data, fetch the prompt
            if (testDetail.prompt_id && !testDetail.prompt) {
              const promptsClient = clientFactory.getPromptsClient();
              const promptData = await promptsClient.getPrompt(
                testDetail.prompt_id
              );
              testDetail.prompt = promptData;
            }

            setTestData(testDetail);
          } catch (_testError) {
            // Continue with projects/endpoints even if test fetch fails
          }
        }

        // Fetch projects with proper response handling
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
            // Direct array response (what we're getting)
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
        } catch (_projectsError) {
          setProjects([]);
          notifications.show(
            'Failed to load projects. Please refresh the page.',
            { severity: 'error' }
          );
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
          notifications.show(
            'Failed to load endpoints. Please refresh the page.',
            { severity: 'error' }
          );
        }
      } catch (error) {
        console.error('[TrialDrawer] Error loading data:', error);
        setError(
          'Failed to load data. Please check your connection and try again.'
        );
      } finally {
        setLoading(false);
        hasLoadedRef.current = true;
      }
    };

    if (open) {
      fetchData();
    } else {
      // Reset the refs when drawer closes so next open will be treated as initial
      hasLoadedRef.current = false;
      testIdsRef.current = '';
    }
    // testIds is intentionally not in deps - we track changes via testIdsRef to avoid re-running on array reference changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionToken, open]);

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

  const handleSave = async () => {
    if (!sessionToken || !selectedEndpoint || !testData) return;

    // Determine test type
    const isMultiTurn = isMultiTurnTest(testData.test_type?.type_value);

    // Validate based on test type
    if (isMultiTurn) {
      // For multi-turn, check test_configuration
      if (
        !testData.test_configuration ||
        !isMultiTurnConfig(testData.test_configuration)
      ) {
        setError('Invalid multi-turn test configuration');
        return;
      }
    } else {
      // For single-turn, check prompt content
      if (!testData.prompt?.content) {
        setError('Test prompt is missing');
        return;
      }
    }

    try {
      // Clear previous results immediately when starting a new execution
      setTrialResponse(null);
      setTrialInProgress(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);

      if (isMultiTurn) {
        // Multi-turn test execution
        const testsClient = clientFactory.getTestsClient();
        const config = testData.test_configuration as MultiTurnTestConfig;

        const executeRequest = {
          endpoint_id:
            selectedEndpoint as `${string}-${string}-${string}-${string}-${string}`,
          test_configuration: {
            goal: config.goal,
            instructions: config.instructions,
            restrictions: config.restrictions,
            scenario: config.scenario,
            max_turns: config.max_turns,
          },
          behavior: testData.behavior?.name || '',
          topic: testData.topic?.name || '',
          category: testData.category?.name || '',
          evaluate_metrics: false,
        };

        const executeResponse = await testsClient.executeTest(executeRequest);

        // Extract conversation from test_output
        let conversation = [];
        if (
          executeResponse.test_output &&
          typeof executeResponse.test_output === 'object'
        ) {
          // Check for conversation_summary
          if (executeResponse.test_output.conversation_summary) {
            conversation = executeResponse.test_output.conversation_summary;
          }
          // Also check if test_output itself is an array (alternative structure)
          else if (Array.isArray(executeResponse.test_output)) {
            conversation = executeResponse.test_output;
          }
        }

        setTrialResponse({
          type: 'multi_turn',
          conversation,
          execution_time: executeResponse.execution_time,
          status: executeResponse.status,
          raw_response: executeResponse, // Keep full response for debugging
        });
      } else {
        // Single-turn test execution
        const endpointsClient = clientFactory.getEndpointsClient();

        const data = await endpointsClient.invokeEndpoint(selectedEndpoint, {
          input: testData.prompt?.content || '',
        });

        setTrialResponse({
          type: 'single_turn',
          output: data?.output || data,
        });
      }

      notifications.show('Test executed successfully', { severity: 'success' });
    } catch (error) {
      setError(
        `Failed to execute test: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
      notifications.show('Failed to execute test', { severity: 'error' });
    } finally {
      setTrialInProgress(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Run Test"
      loading={loading || trialInProgress}
      error={error}
      onSave={trialResponse ? onClose : handleSave}
      saveButtonText={
        trialResponse
          ? 'Close'
          : trialInProgress
            ? 'Running Test...'
            : 'Run Test'
      }
      closeButtonText={trialResponse ? '' : 'Cancel'}
      width={900}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
          height: '100%',
          overflow: 'hidden',
        }}
      >
        <FormControl fullWidth sx={{ mt: 1 }}>
          <Autocomplete
            options={projects}
            value={projects.find(p => p.id === selectedProject) || null}
            onChange={async (_, newValue) => {
              if (!newValue) {
                setSelectedProject(null);
                setSelectedProjectData(null);
                return;
              }
              setSelectedProject(newValue.id);
              setSelectedEndpoint(null);

              // Fetch full project data to get icon
              try {
                const clientFactory = new ApiClientFactory(sessionToken);
                const projectsClient = clientFactory.getProjectsClient();
                const projectData = await projectsClient.getProject(
                  newValue.id
                );
                setSelectedProjectData(projectData);
              } catch (_error) {
                // Fallback to basic data if fetch fails
                setSelectedProjectData({
                  id: newValue.id,
                  name: newValue.name,
                } as Project);
              }
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
                  selectedProject ? 'Select endpoint' : 'Select a project first'
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

        {/* Test Content - Single-Turn */}
        {testData?.prompt?.content && (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Test Prompt
            </Typography>
            <Typography
              variant="body2"
              component="pre"
              sx={{
                whiteSpace: 'pre-wrap',
                fontFamily: 'monospace',
                p: 1,
                bgcolor: 'action.hover',
                borderRadius: theme.shape.sharp,
                minHeight: '100px',
              }}
            >
              {testData.prompt.content}
            </Typography>
          </Paper>
        )}

        {/* Test Content - Multi-Turn */}
        {testData &&
          isMultiTurnTest(testData.test_type?.type_value) &&
          isMultiTurnConfig(testData.test_configuration) && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Test Configuration
              </Typography>

              {/* Goal - Always visible */}
              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}
                >
                  Goal:
                </Typography>
                <Typography
                  variant="body2"
                  component="pre"
                  sx={{
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'monospace',
                    p: 1,
                    bgcolor: 'action.hover',
                    borderRadius: theme.shape.sharp,
                  }}
                >
                  {testData.test_configuration.goal}
                </Typography>
              </Box>

              {/* Collapsible Details */}
              {(testData.test_configuration.instructions ||
                testData.test_configuration.scenario ||
                testData.test_configuration.restrictions) && (
                <>
                  <Button
                    size="small"
                    onClick={() => setShowDetails(!showDetails)}
                    sx={{ mb: 1, textTransform: 'none' }}
                  >
                    {showDetails ? 'Hide Details' : 'Show Details'}
                  </Button>
                  <Collapse in={showDetails}>
                    <Box
                      sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
                    >
                      {testData.test_configuration.instructions && (
                        <Box>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{
                              fontWeight: 'bold',
                              display: 'block',
                              mb: 0.5,
                            }}
                          >
                            Instructions:
                          </Typography>
                          <Typography
                            variant="body2"
                            component="pre"
                            sx={{
                              whiteSpace: 'pre-wrap',
                              fontFamily: 'monospace',
                              p: 1,
                              bgcolor: 'action.hover',
                              borderRadius: theme.shape.sharp,
                            }}
                          >
                            {testData.test_configuration.instructions}
                          </Typography>
                        </Box>
                      )}
                      {testData.test_configuration.scenario && (
                        <Box>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{
                              fontWeight: 'bold',
                              display: 'block',
                              mb: 0.5,
                            }}
                          >
                            Scenario:
                          </Typography>
                          <Typography
                            variant="body2"
                            component="pre"
                            sx={{
                              whiteSpace: 'pre-wrap',
                              fontFamily: 'monospace',
                              p: 1,
                              bgcolor: 'action.hover',
                              borderRadius: theme.shape.sharp,
                            }}
                          >
                            {testData.test_configuration.scenario}
                          </Typography>
                        </Box>
                      )}
                      {testData.test_configuration.restrictions && (
                        <Box>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{
                              fontWeight: 'bold',
                              display: 'block',
                              mb: 0.5,
                            }}
                          >
                            Restrictions:
                          </Typography>
                          <Typography
                            variant="body2"
                            component="pre"
                            sx={{
                              whiteSpace: 'pre-wrap',
                              fontFamily: 'monospace',
                              p: 1,
                              bgcolor: 'action.hover',
                              borderRadius: theme.shape.sharp,
                            }}
                          >
                            {testData.test_configuration.restrictions}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </Collapse>
                </>
              )}
            </Paper>
          )}

        {/* Response Output */}
        <Paper
          variant="outlined"
          sx={{
            p: 2,
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            minHeight: 0,
          }}
        >
          <Typography variant="subtitle2" gutterBottom>
            Response Output
            {trialInProgress && <CircularProgress size={16} sx={{ ml: 1 }} />}
          </Typography>

          <Box
            sx={{
              flex: 1,
              overflow: 'auto',
              minHeight: 0,
            }}
          >
            {!trialResponse ? (
              <Typography
                variant="body2"
                component="pre"
                sx={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  p: 1,
                  bgcolor: 'action.hover',
                  borderRadius: theme.shape.sharp,
                  minHeight: '100px',
                  color: 'text.secondary',
                }}
              >
                Run the test to see the response
              </Typography>
            ) : trialResponse.type === 'multi_turn' ? (
              // Multi-turn response
              <Box>
                {trialResponse.conversation &&
                trialResponse.conversation.length > 0 ? (
                  <Box>
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="caption" color="text.secondary">
                        Test Execution: {trialResponse.conversation.length}{' '}
                        turns completed
                      </Typography>
                    </Box>
                    <ConversationHistory
                      conversationSummary={trialResponse.conversation}
                      project={selectedProjectData || undefined}
                      projectName={selectedProjectData?.name}
                      maxHeight="100%"
                    />
                  </Box>
                ) : (
                  <Box>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ mb: 1 }}
                    >
                      No conversation data available. Raw response:
                    </Typography>
                    <Typography
                      variant="body2"
                      component="pre"
                      sx={{
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'monospace',
                        p: 1,
                        bgcolor: 'action.hover',
                        borderRadius: theme.shape.sharp,
                        minHeight: '100px',
                        ...theme.typography.chartLabel,
                        overflow: 'auto',
                        maxHeight: '400px',
                      }}
                    >
                      {JSON.stringify(trialResponse.raw_response, null, 2)}
                    </Typography>
                  </Box>
                )}
              </Box>
            ) : (
              // Single-turn response
              <Typography
                variant="body2"
                component="pre"
                sx={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  p: 1,
                  bgcolor: 'action.hover',
                  borderRadius: theme.shape.sharp,
                  minHeight: '100px',
                }}
              >
                {(() => {
                  if (!trialResponse.output) {
                    return 'No response received';
                  }

                  // If output is an object, stringify it
                  if (typeof trialResponse.output === 'object') {
                    return JSON.stringify(trialResponse.output, null, 2);
                  }

                  // Otherwise render as-is (string, number, boolean)
                  return String(trialResponse.output);
                })()}
              </Typography>
            )}
          </Box>
        </Paper>
      </Box>
    </BaseDrawer>
  );
}
