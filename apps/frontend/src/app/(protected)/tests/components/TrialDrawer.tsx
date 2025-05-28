'use client';

import React, { useState, useEffect } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { Box, Typography, FormControl, FormHelperText, CircularProgress, Paper, Divider, Chip, Autocomplete, TextField } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Project } from '@/utils/api-client/interfaces/project';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useNotifications } from '@/components/common/NotificationContext';
import { UUID } from 'crypto';

interface ProjectOption {
  id: UUID;
  name: string;
}

interface EndpointOption {
  id: UUID;
  name: string;
  environment?: 'development' | 'staging' | 'production';
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
  onSuccess 
}: TrialDrawerProps) {
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [testData, setTestData] = useState<TestDetail | null>(null);
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [endpoints, setEndpoints] = useState<EndpointOption[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<string | null>(null);
  const [filteredEndpoints, setFilteredEndpoints] = useState<EndpointOption[]>([]);
  const [trialResponse, setTrialResponse] = useState<any>(null);
  const [trialInProgress, setTrialInProgress] = useState(false);
  const [trialCompleted, setTrialCompleted] = useState(false);
  const notifications = useNotifications();

  // Fetch projects, endpoints, and test data
  useEffect(() => {
    const fetchData = async () => {
      if (!sessionToken || !open) return;
      
      try {
        setLoading(true);
        setTrialResponse(null);
        setTrialCompleted(false);
        setError(undefined);
        const clientFactory = new ApiClientFactory(sessionToken);
        
        // Fetch test data (we only support single test trial for now)
        if (testIds.length > 0) {
          try {
            const testsClient = clientFactory.getTestsClient();
            const testDetail = await testsClient.getTest(testIds[0]);
            
            // If test has a prompt_id but no prompt data, fetch the prompt
            if (testDetail.prompt_id && !testDetail.prompt) {
              const promptsClient = clientFactory.getPromptsClient();
              const promptData = await promptsClient.getPrompt(testDetail.prompt_id);
              testDetail.prompt = promptData;
            }
            
            setTestData(testDetail);
          } catch (testError) {
            console.error('Error fetching test data:', testError);
            // Continue with projects/endpoints even if test fetch fails
          }
        }
        
        // Fetch projects with proper response handling
        try {
          const projectsClient = clientFactory.getProjectsClient();
          const projectsData = await projectsClient.getProjects({ 
            sortBy: 'name', 
            sortOrder: 'asc',
            limit: 100
          });
          
          console.log('Projects API response:', projectsData);
          
          // Handle both response formats: direct array or {data: array}
          let projectsArray: Project[] = [];
          if (Array.isArray(projectsData)) {
            // Direct array response (what we're getting)
            projectsArray = projectsData;
            console.log('Using direct array response');
          } else if (projectsData && Array.isArray(projectsData.data)) {
            // Paginated response with data property
            projectsArray = projectsData.data;
            console.log('Using paginated response data');
          } else {
            console.warn('Invalid projects response structure:', projectsData);
          }
          
          const processedProjects = projectsArray
            .filter((p: Project) => p.id && p.name && p.name.trim() !== '')
            .map((p: Project) => ({ id: p.id as UUID, name: p.name }));
          
          console.log('Final processed projects:', processedProjects);
          setProjects(processedProjects);
        } catch (projectsError) {
          console.error('Error fetching projects:', projectsError);
          setProjects([]);
          notifications.show('Failed to load projects. Please refresh the page.', { severity: 'error' });
        }
        
        // Fetch all endpoints
        try {
          const endpointsClient = clientFactory.getEndpointsClient();
          const endpointsResponse = await endpointsClient.getEndpoints({
            sortBy: 'name',
            sortOrder: 'asc',
            limit: 100
          });
          
          console.log('Endpoints API response:', endpointsResponse);
          
          if (endpointsResponse && Array.isArray(endpointsResponse.data)) {
            const processedEndpoints = endpointsResponse.data
              .filter(e => e.id && e.name && e.name.trim() !== '')
              .map(e => ({ 
                id: e.id as UUID, 
                name: e.name,
                environment: e.environment,
                project_id: e.project_id
              }));
            
            console.log('Final processed endpoints:', processedEndpoints);
            setEndpoints(processedEndpoints);
          } else {
            console.warn('Invalid endpoints response structure:', endpointsResponse);
            setEndpoints([]);
          }
        } catch (endpointsError) {
          console.error('Error fetching endpoints:', endpointsError);
          setEndpoints([]);
          notifications.show('Failed to load endpoints. Please refresh the page.', { severity: 'error' });
        }
        
      } catch (error) {
        console.error('General error in fetchData:', error);
        setError('Failed to load data. Please check your connection and try again.');
      } finally {
        setLoading(false);
      }
    };
    
    if (open) {
      fetchData();
    }
  }, [sessionToken, open, testIds, notifications]);

  // Filter endpoints when project changes
  useEffect(() => {
    if (!selectedProject) {
      setFilteredEndpoints([]);
      setSelectedEndpoint(null);
      return;
    }
    
    // Filter endpoints that belong to the selected project
    const filtered = endpoints.filter(endpoint => endpoint.project_id === selectedProject);
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
    if (!sessionToken || !selectedEndpoint || !testData?.prompt?.content) return;
    
    try {
      setTrialInProgress(true);
      
      const clientFactory = new ApiClientFactory(sessionToken);
      const endpointsClient = clientFactory.getEndpointsClient();
      
      const data = await endpointsClient.invokeEndpoint(selectedEndpoint, {
        input: testData.prompt.content
      });
      
      console.log('Response data:', data);
      console.log('Output:', data.output);
      
      setTrialResponse(data);
    } catch (error) {
      console.error(error);
      setError('Failed to execute trial');
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
      onSave={handleSave}
      saveButtonText={trialInProgress ? "Running Trial..." : "Start Trial"}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <FormControl fullWidth>
          <Autocomplete
            options={projects}
            value={projects.find(p => p.id === selectedProject) || null}
            onChange={(_, newValue) => {
              console.log('Project selection changed:', newValue);
              if (!newValue) {
                setSelectedProject(null);
                return;
              }
              setSelectedProject(newValue.id);
              setSelectedEndpoint(null);
            }}
            getOptionLabel={(option) => option.name}
            renderInput={(params) => (
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
            value={filteredEndpoints.find(e => e.id === selectedEndpoint) || null}
            onChange={(_, newValue) => handleEndpointChange(newValue)}
            getOptionLabel={(option) => option.name}
            disabled={!selectedProject}
            renderInput={(params) => (
              <TextField 
                {...params} 
                label="Endpoint" 
                required 
                placeholder={selectedProject ? "Select endpoint" : "Select a project first"}
              />
            )}
            renderOption={(props, option) => {
              const { key, ...otherProps } = props;
              return (
                <Box
                  key={option.id}
                  {...otherProps}
                  component="li"
                  sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <span>{option.name}</span>
                  {option.environment && (
                    <Chip 
                      label={option.environment} 
                      size="small"
                      color={
                        option.environment === 'production' ? 'error' :
                        option.environment === 'staging' ? 'warning' : 
                        'success'
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
            <FormHelperText>No endpoints available for this project</FormHelperText>
          )}
        </FormControl>

        {testData?.prompt?.content && (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Test Executable
            </Typography>
            <Typography 
              variant="body2" 
              component="pre" 
              sx={{ 
                whiteSpace: 'pre-wrap',
                fontFamily: 'monospace',
                p: 1,
                bgcolor: 'action.hover',
                borderRadius: 1,
                minHeight: '100px'
              }}
            >
              {testData.prompt.content}
            </Typography>
          </Paper>
        )}

        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle2" gutterBottom>Response Output</Typography>
          <Typography variant="body2" component="pre" sx={{ 
            whiteSpace: 'pre-wrap',
            fontFamily: 'monospace',
            p: 1,
            bgcolor: 'action.hover',
            borderRadius: 1,
            minHeight: '100px'
          }}>
            {trialResponse?.output || 'Run the trial to see the response'}
          </Typography>
        </Paper>
      </Box>
    </BaseDrawer>
  );
} 