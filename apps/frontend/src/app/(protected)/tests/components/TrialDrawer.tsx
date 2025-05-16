'use client';

import React, { useState, useEffect } from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { Box, Typography, FormControl, FormHelperText, CircularProgress, Paper, Divider, Chip, Autocomplete, TextField } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Project } from '@/utils/api-client/interfaces/project';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import BaseFreesoloAutocomplete, { AutocompleteOption } from '@/components/common/BaseFreesoloAutocomplete';
import { useNotifications } from '@/components/common/NotificationContext';
import { UUID } from 'crypto';

// Sample response for demonstration
const SAMPLE_RESPONSE = {
  output: "I'm sorry, I'm an insurance expert and can only answer questions about insurance.\n",
  session_id: "024de0f6-3cf7-463f-a9a9-129c965e3927",
  context: [
    "Please provide a valid insurance-related question so I can generate relevant context fragments.",
    "I need a clear question about insurance to provide helpful information.",
    "Without a proper question, I am unable to provide context fragments."
  ]
};

interface AutocompleteEndpointOption extends AutocompleteOption {
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
  const [projects, setProjects] = useState<AutocompleteOption[]>([]);
  const [endpoints, setEndpoints] = useState<AutocompleteEndpointOption[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<string | null>(null);
  const [filteredEndpoints, setFilteredEndpoints] = useState<AutocompleteEndpointOption[]>([]);
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
        const clientFactory = new ApiClientFactory(sessionToken);
        
        // Fetch test data (we only support single test trial for now)
        if (testIds.length > 0) {
          const testsClient = clientFactory.getTestsClient();
          const testDetail = await testsClient.getTest(testIds[0]);
          
          // If test has a prompt_id but no prompt data, fetch the prompt
          if (testDetail.prompt_id && !testDetail.prompt) {
            const promptsClient = clientFactory.getPromptsClient();
            const promptData = await promptsClient.getPrompt(testDetail.prompt_id);
            testDetail.prompt = promptData;
          }
          
          setTestData(testDetail);
        }
        
        // Fetch projects
        const projectsClient = clientFactory.getProjectsClient();
        const projectsData = await projectsClient.getProjects({ 
          sortBy: 'name', 
          sortOrder: 'asc'
        });
        
        setProjects(
          projectsData.data
            .filter((p: Project) => p.id && p.name && p.name.trim() !== '')
            .map((p: Project) => ({ id: p.id as UUID, name: p.name }))
        );
        
        // Fetch all endpoints
        const endpointsClient = clientFactory.getEndpointsClient();
        const endpointsResponse = await endpointsClient.getEndpoints({
          sortBy: 'name',
          sortOrder: 'asc'
        });
        
        setEndpoints(
          endpointsResponse.data
            .filter(e => e.id && e.name && e.name.trim() !== '')
            .map(e => ({ 
              id: e.id as UUID, 
              name: e.name,
              environment: e.environment,
              project_id: e.project_id
            }))
        );
        
        setError(undefined);
      } catch (error) {
        console.error('Error fetching data:', error);
        setError('Failed to load projects and endpoints');
      } finally {
        setLoading(false);
      }
    };
    
    if (open) {
      fetchData();
    }
  }, [sessionToken, open, testIds]);

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

  const handleProjectChange = (value: AutocompleteOption | string | null) => {
    if (!value) {
      setSelectedProject(null);
      return;
    }
    
    const projectId = typeof value === 'string' ? value : value.id;
    setSelectedProject(projectId);
    
    // Reset endpoint if project changes
    setSelectedEndpoint(null);
  };

  const handleEndpointChange = (value: AutocompleteEndpointOption | string | null) => {
    if (!value) {
      setSelectedEndpoint(null);
      return;
    }
    
    const endpointId = typeof value === 'string' ? value : value.id;
    setSelectedEndpoint(endpointId);
  };

  const handleSave = async () => {
    if (!sessionToken || !selectedEndpoint || !testData?.prompt?.content) return;
    
    try {
      setTrialInProgress(true);
      
      const response = await fetch(`https://api.rhesis.ai/endpoints/${selectedEndpoint}/invoke`, {
        method: 'POST',
        headers: {
          'accept': 'application/json',
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionToken}`
        },
        body: JSON.stringify({
          input: testData.prompt.content
        })
      });
      
      const data = await response.json();
      console.log('Response data:', data);
      console.log('Output:', data.output);
      
      setTrialResponse(data);
      // Don't set trialCompleted, so the button stays in "Start Trial" state
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
      title="Trial Test Execution"
      loading={loading || trialInProgress}
      error={error}
      onSave={handleSave}
      saveButtonText={trialInProgress ? "Running Trial..." : "Start Trial"}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <FormControl fullWidth>
          <BaseFreesoloAutocomplete
            options={projects}
            value={selectedProject}
            onChange={handleProjectChange}
            label="Project"
            required
          />
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
          />
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