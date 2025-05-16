'use client';

import React, { useRef, useCallback } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TestRunDetail, TestRunCreate } from '@/utils/api-client/interfaces/test-run';
import { Autocomplete, TextField, Box, Avatar, Typography, Divider } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { TestConfigurationCreate } from '@/utils/api-client/interfaces/test-configuration';
import PersonIcon from '@mui/icons-material/Person';
import { UUID } from 'crypto';

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
  onSuccess 
}: TestRunDrawerProps) {
  const [error, setError] = React.useState<string>();
  const [loading, setLoading] = React.useState(false);
  const [assignee, setAssignee] = React.useState<User | null>(null);
  const [owner, setOwner] = React.useState<User | null>(null);
  const [testSet, setTestSet] = React.useState<TestSet | null>(null);
  const [project, setProject] = React.useState<Project | null>(null);
  const [endpoint, setEndpoint] = React.useState<Endpoint | null>(null);
  
  const [users, setUsers] = React.useState<User[]>([]);
  const [testSets, setTestSets] = React.useState<TestSet[]>([]);
  const [projects, setProjects] = React.useState<Project[]>([]);
  const [endpoints, setEndpoints] = React.useState<Endpoint[]>([]);
  const [filteredEndpoints, setFilteredEndpoints] = React.useState<Endpoint[]>([]);

  const getCurrentUserId = useCallback(() => {
    try {
      const [, payloadBase64] = sessionToken.split('.');
      const base64 = payloadBase64.replace(/-/g, '+').replace(/_/g, '/');
      const pad = base64.length % 4;
      const paddedBase64 = pad ? base64 + '='.repeat(4 - pad) : base64;
      
      const payload = JSON.parse(Buffer.from(paddedBase64, 'base64').toString('utf-8'));
      return payload.user?.id;
    } catch (err) {
      console.error('Error decoding JWT token:', err);
      return undefined;
    }
  }, [sessionToken]);

  // Load initial data
  React.useEffect(() => {
    const loadData = async () => {
      if (!sessionToken) return;

      const clientFactory = new ApiClientFactory(sessionToken);
      const usersClient = clientFactory.getUsersClient();
      const testSetsClient = clientFactory.getTestSetsClient();
      const projectsClient = clientFactory.getProjectsClient();
      const endpointsClient = clientFactory.getEndpointsClient();

      try {
        const currentUserId = getCurrentUserId();
        const [fetchedUsers, fetchedTestSets, fetchedProjects, fetchedEndpoints] = await Promise.all([
          usersClient.getUsers(),
          testSetsClient.getTestSets({ limit: 100 }),
          projectsClient.getProjects(),
          endpointsClient.getEndpoints()
        ]);

        setUsers(fetchedUsers);
        setTestSets(fetchedTestSets.data);
        setProjects(fetchedProjects.data);
        setEndpoints(fetchedEndpoints.data);

        // Set initial values if editing
        if (testRun) {
          if (testRun.assignee_id) {
            const currentAssignee = fetchedUsers.find(u => u.id === testRun.assignee_id);
            setAssignee(currentAssignee || null);
          }
          if (testRun.owner_id) {
            const currentOwner = fetchedUsers.find(u => u.id === testRun.owner_id);
            setOwner(currentOwner || null);
          }
          // Add test set, project and endpoint initialization if available in testRun
        } else {
          // Set default owner as current user for new test runs
          if (currentUserId) {
            const currentUser = fetchedUsers.find(u => u.id === currentUserId);
            setOwner(currentUser || null);
          }
        }
      } catch (err) {
        console.error('Error loading data:', err);
        setError('Failed to load required data');
      }
    };

    loadData();
  }, [sessionToken, testRun, getCurrentUserId]);

  // Filter endpoints when project changes
  React.useEffect(() => {
    if (project) {
      const filtered = endpoints.filter(endpoint => endpoint.project_id === project.id);
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
      const testConfigurationsClient = clientFactory.getTestConfigurationsClient();
      const testRunsClient = clientFactory.getTestRunsClient();

      // Create test configuration
      const testConfigurationData: TestConfigurationCreate = {
        endpoint_id: endpoint.id as UUID,
        test_set_id: testSet.id as UUID,
        user_id: owner?.id as UUID,
        organization_id: endpoint.organization_id as UUID
      };

      // Create the test configuration
      const testConfiguration = await testConfigurationsClient.createTestConfiguration(testConfigurationData);

      // Execute the test configuration
      await testConfigurationsClient.executeTestConfiguration(testConfiguration.id);

      // Create test run
      const testRunData: TestRunCreate = {
        name: `Test Run for ${testSet.name}`,
        test_configuration_id: testConfiguration.id as UUID,
        owner_id: owner?.id,
        assignee_id: assignee?.id,
        organization_id: endpoint.organization_id as UUID
      };

      // Create the test run
      await testRunsClient.createTestRun(testRunData);

      onSuccess?.();
      onClose();
    } catch (err) {
      console.error('Error executing test run:', err);
      setError('Failed to execute test run');
    } finally {
      setLoading(false);
    }
  };

  const getUserDisplayName = (user: User) => {
    return user.name || 
      `${user.given_name || ''} ${user.family_name || ''}`.trim() || 
      user.email;
  };

  const renderUserOption = (props: React.HTMLAttributes<HTMLLIElement> & { key?: string }, option: User) => {
    const { key, ...otherProps } = props;
    return (
      <Box component="li" key={key} {...otherProps}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Avatar
            src={option.picture}
            sx={{ width: 24, height: 24 }}
          >
            <PersonIcon />
          </Avatar>
          {getUserDisplayName(option)}
        </Box>
      </Box>
    );
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
      <>
        <Typography variant="subtitle2" color="text.secondary">
          Workflow
        </Typography>

        <Autocomplete
          options={users}
          value={assignee}
          onChange={(_, newValue) => setAssignee(newValue)}
          getOptionLabel={getUserDisplayName}
          renderOption={renderUserOption}
          renderInput={(params) => (
            <TextField 
              {...params} 
              label="Assignee"
              InputProps={{
                ...params.InputProps,
                startAdornment: assignee && (
                  <Avatar
                    src={assignee.picture}
                    sx={{ width: 24, height: 24, mr: 1 }}
                  >
                    <PersonIcon />
                  </Avatar>
                )
              }}
            />
          )}
        />

        <Autocomplete
          options={users}
          value={owner}
          onChange={(_, newValue) => setOwner(newValue)}
          getOptionLabel={getUserDisplayName}
          renderOption={renderUserOption}
          renderInput={(params) => (
            <TextField 
              {...params} 
              label="Owner" 
              required
              InputProps={{
                ...params.InputProps,
                startAdornment: owner && (
                  <Avatar
                    src={owner.picture}
                    sx={{ width: 24, height: 24, mr: 1 }}
                  >
                    <PersonIcon />
                  </Avatar>
                )
              }}
            />
          )}
        />

        <Divider sx={{ my: 1 }} />

        <Typography variant="subtitle2" color="text.secondary">
          Test Run Configuration
        </Typography>

        <Autocomplete
          options={testSets}
          value={testSet}
          onChange={(_, newValue) => setTestSet(newValue)}
          getOptionLabel={(option) => option.name || 'Unnamed Test Set'}
          renderInput={(params) => (
            <TextField {...params} label="Test Set" required />
          )}
        />

        <Autocomplete
          options={projects}
          value={project}
          onChange={(_, newValue) => setProject(newValue)}
          getOptionLabel={(option) => option.name}
          renderInput={(params) => (
            <TextField {...params} label="Application" required />
          )}
        />

        <Autocomplete
          options={filteredEndpoints}
          value={endpoint}
          onChange={(_, newValue) => setEndpoint(newValue)}
          getOptionLabel={(option) => `${option.name} (${option.environment})`}
          disabled={!project}
          renderInput={(params) => (
            <TextField 
              {...params} 
              label="Endpoint" 
              required
              helperText={!project ? "Select an application first" : undefined}
            />
          )}
        />
      </>
    </BaseDrawer>
  );
} 