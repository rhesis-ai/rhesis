'use client';

import React, { useCallback } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import {
  Autocomplete,
  TextField,
  Box,
  Typography,
  Divider,
  Stack,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { TestConfigurationCreate } from '@/utils/api-client/interfaces/test-configuration';
import { UUID } from 'crypto';
import { useNotifications } from '@/components/common/NotificationContext';
import BaseTag from '@/components/common/BaseTag';
import { EntityType, TagCreate } from '@/utils/api-client/interfaces/tag';
import { TagsClient } from '@/utils/api-client/tags-client';
import { pollForTestRun } from '@/utils/test-run-utils';
import { getApiErrorMessage } from '@/utils/error-utils';

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

  const getCurrentUserId = useCallback(() => {
    try {
      const [, payloadBase64] = sessionToken.split('.');
      const base64 = payloadBase64.replace(/-/g, '+').replace(/_/g, '/');
      const pad = base64.length % 4;
      const paddedBase64 = pad ? base64 + '='.repeat(4 - pad) : base64;

      const payload = JSON.parse(
        Buffer.from(paddedBase64, 'base64').toString('utf-8')
      );
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

  const handleSave = async () => {
    if (!sessionToken || !testSet || !endpoint) {
      setError('Please select a test set and endpoint');
      return;
    }

    try {
      setLoading(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const testConfigurationsClient =
        clientFactory.getTestConfigurationsClient();

      const currentUserId: UUID | undefined = getCurrentUserId();

      // Create test configuration
      const testConfigurationData: TestConfigurationCreate = {
        endpoint_id: endpoint.id as UUID,
        test_set_id: testSet.id as UUID,
        ...(currentUserId && { user_id: currentUserId }),
        organization_id: endpoint.organization_id as UUID,
      };

      // Create the test configuration
      const testConfiguration =
        await testConfigurationsClient.createTestConfiguration(
          testConfigurationData
        );

      // Execute the test configuration (this automatically creates a test run)
      await testConfigurationsClient.executeTestConfiguration(
        testConfiguration.id
      );

      // Get the created test run and assign tags if any
      if (tags.length > 0) {
        try {
          const testRunsClient = clientFactory.getTestRunsClient();
          const testRun = await pollForTestRun(
            testRunsClient,
            testConfiguration.id
          );

          if (testRun) {
            const tagsClient = new TagsClient(sessionToken);
            const organizationId = endpoint.organization_id as UUID;

            // Assign each tag to the test run
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
          } else {
            console.warn(
              'Test run not found after polling, tags will not be assigned'
            );
          }
        } catch (tagError) {
          // Log error but don't fail the whole operation
          console.error('Failed to assign tags to test run:', tagError);
        }
      }

      // Show success notification
      notifications.show('Test execution queued successfully', {
        severity: 'success',
      });

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
          </Stack>
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
