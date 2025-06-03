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
} from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
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
  sessionToken 
}: ExecuteTestSetDrawerProps) {
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [endpoints, setEndpoints] = useState<EndpointOption[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<string | null>(null);
  const [filteredEndpoints, setFilteredEndpoints] = useState<EndpointOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  // Fetch projects and endpoints when drawer opens
  useEffect(() => {
    const fetchData = async () => {
      if (!sessionToken || !open) return;
      
      try {
        setLoading(true);
        setError(undefined);
        
        const clientFactory = new ApiClientFactory(sessionToken);
        
        // Fetch projects
        try {
          const projectsClient = clientFactory.getProjectsClient();
          const projectsData = await projectsClient.getProjects({ 
            sortBy: 'name', 
            sortOrder: 'asc',
            limit: 100
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
        } catch (projectsError) {
          console.error('Error fetching projects:', projectsError);
          setProjects([]);
        }
        
        // Fetch all endpoints
        try {
          const endpointsClient = clientFactory.getEndpointsClient();
          const endpointsResponse = await endpointsClient.getEndpoints({
            sortBy: 'name',
            sortOrder: 'asc',
            limit: 100
          });
          
          if (endpointsResponse && Array.isArray(endpointsResponse.data)) {
            const processedEndpoints = endpointsResponse.data
              .filter(e => e.id && e.name && e.name.trim() !== '')
              .map(e => ({ 
                id: e.id as UUID, 
                name: e.name,
                environment: e.environment,
                project_id: e.project_id
              }));
            
            setEndpoints(processedEndpoints);
          } else {
            setEndpoints([]);
          }
        } catch (endpointsError) {
          console.error('Error fetching endpoints:', endpointsError);
          setEndpoints([]);
        }
        
      } catch (error) {
        console.error('Error fetching data:', error);
        setError('Failed to load data. Please check your connection and try again.');
      } finally {
        setLoading(false);
      }
    };
    
    if (open) {
      fetchData();
      // Reset selections when drawer opens
      setSelectedProject(null);
      setSelectedEndpoint(null);
    }
  }, [sessionToken, open]);

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

  const handleExecute = async () => {
    if (!selectedEndpoint) return;

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = apiFactory.getTestSetsClient();
      
      // Execute test set against the selected endpoint
      await testSetsClient.executeTestSet(testSetId, selectedEndpoint);
      
      // Close drawer on success
      onClose();
    } catch (err) {
      setError('Failed to execute test set');
      throw err; // Re-throw so BaseDrawer can handle the error state
    }
  };

  const isFormValid = selectedProject && selectedEndpoint;

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Execute Test Set"
      loading={loading}
      error={error}
      onSave={isFormValid ? handleExecute : undefined}
      saveButtonText="Execute Test Set"
    >
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Stack spacing={3}>
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
        </Stack>
      )}
    </BaseDrawer>
  );
} 