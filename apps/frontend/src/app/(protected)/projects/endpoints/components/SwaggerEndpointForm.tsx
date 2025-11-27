'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  Box,
  Button,
  Card,
  Grid,
  TextField,
  Typography,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  ToggleButton,
  ToggleButtonGroup,
  CircularProgress,
  ListItemIcon,
  ListItemText,
  FormHelperText,
} from '@mui/material';
import { LoadingButton } from '@mui/lab';
import DownloadIcon from '@mui/icons-material/Download';
import { createEndpoint } from '@/actions/endpoints';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useSession } from 'next-auth/react';
import { auth } from '@/auth';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { useNotifications } from '@/components/common/NotificationContext';

// Import icons for project icon rendering
import SmartToyIcon from '@mui/icons-material/SmartToy';
import DevicesIcon from '@mui/icons-material/Devices';
import WebIcon from '@mui/icons-material/Web';
import StorageIcon from '@mui/icons-material/Storage';
import CodeIcon from '@mui/icons-material/Code';
import DataObjectIcon from '@mui/icons-material/DataObject';
import CloudIcon from '@mui/icons-material/Cloud';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart';
import TerminalIcon from '@mui/icons-material/Terminal';
import VideogameAssetIcon from '@mui/icons-material/VideogameAsset';
import ChatIcon from '@mui/icons-material/Chat';
import PsychologyIcon from '@mui/icons-material/Psychology';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SearchIcon from '@mui/icons-material/Search';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import PhoneIphoneIcon from '@mui/icons-material/PhoneIphone';
import SchoolIcon from '@mui/icons-material/School';
import ScienceIcon from '@mui/icons-material/Science';
import AccountTreeIcon from '@mui/icons-material/AccountTree';

// Map of icon names to components for easy lookup
const ICON_MAP: Record<string, React.ComponentType> = {
  SmartToy: SmartToyIcon,
  Devices: DevicesIcon,
  Web: WebIcon,
  Storage: StorageIcon,
  Code: CodeIcon,
  DataObject: DataObjectIcon,
  Cloud: CloudIcon,
  Analytics: AnalyticsIcon,
  ShoppingCart: ShoppingCartIcon,
  Terminal: TerminalIcon,
  VideogameAsset: VideogameAssetIcon,
  Chat: ChatIcon,
  Psychology: PsychologyIcon,
  Dashboard: DashboardIcon,
  Search: SearchIcon,
  AutoFixHigh: AutoFixHighIcon,
  PhoneIphone: PhoneIphoneIcon,
  School: SchoolIcon,
  Science: ScienceIcon,
  AccountTree: AccountTreeIcon,
};

const ENVIRONMENTS = ['production', 'staging', 'development'];

// Get appropriate icon based on project type or use case
const getProjectIcon = (project: Project) => {
  // Check if a specific project icon was selected during creation
  if (project?.icon && ICON_MAP[project.icon]) {
    const IconComponent = ICON_MAP[project.icon];
    return <IconComponent />;
  }

  // Fall back to a default icon
  return <SmartToyIcon />;
};

export default function SwaggerEndpointForm() {
  const router = useRouter();
  const params = useParams<{ identifier?: string }>();
  const projectIdFromUrl = params?.identifier || '';
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [swaggerUrl, setSwaggerUrl] = useState('');
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState<boolean>(true);
  const { data: session } = useSession();
  const { markStepComplete } = useOnboarding();
  const notifications = useNotifications();

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    environment: 'development',
    openapi_spec_url: '',
    config_source: 'openapi',
    project_id: '',
  });

  // Set project_id from URL parameter if provided
  useEffect(() => {
    if (projectIdFromUrl) {
      setFormData(prev => ({
        ...prev,
        project_id: projectIdFromUrl,
      }));
    }
  }, [projectIdFromUrl]);

  // Fetch projects when component mounts
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoadingProjects(true);
        let sessionToken = session?.session_token;

        // Fallback to server-side auth if client-side session is not available
        if (!sessionToken) {
          try {
            const serverSession = await auth();
            sessionToken = serverSession?.session_token;
          } catch {
            // Failed to get session from server-side auth
          }
        }

        if (sessionToken) {
          const client = new ApiClientFactory(sessionToken).getProjectsClient();
          const data = await client.getProjects();
          setProjects(data.data);
        } else {
          setError('Authentication required. Please log in again.');
        }
      } catch {
        setError('Failed to load projects. Please try again later.');
      } finally {
        setLoadingProjects(false);
      }
    };

    fetchProjects();
  }, [session]);

  const handleChange = (field: string, value: unknown) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleImportSpecification = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // TODO: Implement the actual swagger import logic
      await new Promise(resolve => setTimeout(resolve, 1000)); // Simulated delay

      // Update the form data with the Swagger URL
      setFormData(prev => ({
        ...prev,
        openapi_spec_url: swaggerUrl,
      }));
    } catch (error) {
      setError(
        `Failed to import Swagger specification: ${(error as Error).message}`
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.project_id) {
      setError('Please select a project');
      return;
    }

    setIsSubmitting(true);
    try {
      await createEndpoint(formData as unknown as Omit<Endpoint, 'id'>);

      // Mark onboarding step as complete
      markStepComplete('endpointSetup');

      // Show success notification
      notifications.show('Endpoint created successfully!', {
        severity: 'success',
      });

      router.push('/projects/endpoints');
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <Card>
        {/* Action buttons row */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            p: 2,
          }}
        >
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              onClick={() => router.push('/projects/endpoints')}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <LoadingButton
              type="submit"
              variant="contained"
              color="primary"
              loading={isSubmitting}
              disabled={projects.length === 0 && !loadingProjects}
            >
              Create Endpoint
            </LoadingButton>
          </Box>
        </Box>

        <Box sx={{ p: 3 }}>
          <Grid container spacing={3}>
            {/* General Information */}
            <Grid size={12}>
              <Typography variant="subtitle1" sx={{ mb: 2 }}>
                General Information
              </Typography>
              <Grid container spacing={2}>
                <Grid
                  size={{
                    xs: 12,
                    md: 6,
                  }}
                >
                  <TextField
                    fullWidth
                    label="Name"
                    value={formData.name}
                    onChange={e => handleChange('name', e.target.value)}
                    required
                  />
                </Grid>
                <Grid
                  size={{
                    xs: 12,
                    md: 6,
                  }}
                >
                  <TextField
                    fullWidth
                    label="Description"
                    value={formData.description}
                    onChange={e => handleChange('description', e.target.value)}
                    multiline
                    rows={1}
                  />
                </Grid>
              </Grid>
            </Grid>

            {/* Swagger URL */}
            <Grid size={12}>
              <Typography variant="subtitle1" sx={{ mb: 2 }}>
                Swagger Configuration
              </Typography>
              <Grid container spacing={2}>
                <Grid size={12}>
                  <Box sx={{ display: 'flex', gap: 2 }}>
                    <TextField
                      fullWidth
                      label="Swagger Documentation URL"
                      value={swaggerUrl}
                      onChange={e => setSwaggerUrl(e.target.value)}
                      placeholder="https://api.example.com/swagger.json"
                    />
                    <LoadingButton
                      variant="outlined"
                      onClick={handleImportSpecification}
                      loading={isLoading}
                      loadingPosition="start"
                      startIcon={<DownloadIcon />}
                      sx={{ minWidth: '200px' }}
                    >
                      Import
                    </LoadingButton>
                  </Box>
                </Grid>
              </Grid>
            </Grid>

            {/* Project Selection */}
            <Grid size={12}>
              <Typography variant="subtitle1" sx={{ mb: 2 }}>
                Project
              </Typography>
              <Grid container spacing={2}>
                <Grid size={12}>
                  {projects.length === 0 && !loadingProjects ? (
                    <Alert
                      severity="warning"
                      action={
                        <Button
                          color="inherit"
                          size="small"
                          component="a"
                          href="/projects/create-new"
                        >
                          Create Project
                        </Button>
                      }
                    >
                      No projects available. Please create a project first.
                    </Alert>
                  ) : (
                    <FormControl
                      fullWidth
                      required
                      error={Boolean(error && !formData.project_id)}
                    >
                      <InputLabel id="project-select-label">
                        Select Project
                      </InputLabel>
                      <Select
                        labelId="project-select-label"
                        id="project-select"
                        value={formData.project_id}
                        onChange={e =>
                          handleChange('project_id', e.target.value)
                        }
                        label="Select Project"
                        disabled={loadingProjects}
                        required
                        renderValue={selected => {
                          const selectedProject = projects.find(
                            p => p.id === selected
                          );
                          return (
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              {selectedProject && (
                                <Box
                                  sx={{
                                    mr: 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                  }}
                                >
                                  {getProjectIcon(selectedProject)}
                                </Box>
                              )}
                              {selectedProject?.name || 'No project selected'}
                            </Box>
                          );
                        }}
                      >
                        {loadingProjects ? (
                          <MenuItem disabled>
                            <CircularProgress size={20} sx={{ mr: 1 }} />
                            Loading projects...
                          </MenuItem>
                        ) : (
                          projects.map(project => (
                            <MenuItem key={project.id} value={project.id}>
                              <ListItemIcon>
                                {getProjectIcon(project)}
                              </ListItemIcon>
                              <ListItemText
                                primary={project.name}
                                secondary={project.description}
                              />
                            </MenuItem>
                          ))
                        )}
                      </Select>
                      {error && !formData.project_id && (
                        <FormHelperText error>
                          A project is required
                        </FormHelperText>
                      )}
                    </FormControl>
                  )}
                </Grid>
              </Grid>
            </Grid>

            {/* Environment */}
            <Grid size={12}>
              <Typography variant="subtitle1" sx={{ mb: 2 }}>
                Environment
              </Typography>
              <Grid container spacing={2}>
                <Grid size={12}>
                  <ToggleButtonGroup
                    value={formData.environment}
                    exclusive
                    onChange={(e, newValue) => {
                      if (newValue !== null) {
                        setFormData(prev => ({
                          ...prev,
                          environment: newValue,
                        }));
                      }
                    }}
                    aria-label="environment selection"
                    sx={{
                      '& .MuiToggleButton-root.Mui-selected': {
                        backgroundColor: 'primary.main',
                        color: 'common.white',
                        '&:hover': {
                          backgroundColor: 'primary.dark',
                        },
                      },
                    }}
                  >
                    {ENVIRONMENTS.map(env => (
                      <ToggleButton
                        key={env}
                        value={env}
                        sx={{
                          textTransform: 'capitalize',
                          '&.Mui-selected': {
                            borderColor: 'primary.main',
                          },
                          '&:hover': {
                            backgroundColor: 'action.hover',
                          },
                        }}
                      >
                        {env}
                      </ToggleButton>
                    ))}
                  </ToggleButtonGroup>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </Box>
      </Card>
      {error && (
        <Box sx={{ mt: 2 }}>
          <Alert severity="error">{error}</Alert>
        </Box>
      )}
    </form>
  );
}
