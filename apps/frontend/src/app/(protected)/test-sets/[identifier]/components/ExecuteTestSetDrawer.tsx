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
  Divider,
  Typography,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  ArrowForward as ArrowForwardIcon,
  CallSplit as CallSplitIcon,
} from '@mui/icons-material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { useNotifications } from '@/components/common/NotificationContext';
import { UUID } from 'crypto';

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
  sessionToken,
}: ExecuteTestSetDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [endpoints, setEndpoints] = useState<EndpointOption[]>([]);
  const [filteredEndpoints, setFilteredEndpoints] = useState<EndpointOption[]>(
    []
  );
  const [selectedProject, setSelectedProject] = useState<UUID | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<UUID | null>(null);
  const [executionMode, setExecutionMode] = useState<string>('Parallel');
  const notifications = useNotifications();

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
            sort_by: 'name',
            sort_order: 'asc',
            limit: 100,
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
          setProjects([]);
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
        } catch (endpointsError) {
          setEndpoints([]);
        }
      } catch (error) {
        setError(
          'Failed to load data. Please check your connection and try again.'
        );
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

  const handleExecute = async () => {
    if (!selectedEndpoint) return;

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = apiFactory.getTestSetsClient();

      // Prepare test configuration attributes
      const testConfigurationAttributes = {
        execution_mode: executionMode,
      };

      // Execute test set against the selected endpoint with test configuration attributes
      await testSetsClient.executeTestSet(
        testSetId,
        selectedEndpoint,
        testConfigurationAttributes
      );

      // Show success notification
      notifications.show('Test set execution started successfully!', {
        severity: 'success',
        autoHideDuration: 5000,
      });

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
        </Stack>
      )}
    </BaseDrawer>
  );
}
