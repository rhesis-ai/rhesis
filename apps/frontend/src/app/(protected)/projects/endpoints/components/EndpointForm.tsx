'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  Box,
  Button,
  Card,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Tab,
  Tabs,
  TextField,
  Typography,
  Alert,
  ToggleButton,
  ToggleButtonGroup,
  CircularProgress,
  ListItemIcon,
  ListItemText,
  FormHelperText,
  IconButton,
  InputAdornment,
} from '@mui/material';
import dynamic from 'next/dynamic';
import { useTheme } from '@mui/material/styles';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import { createEndpoint } from '@/actions/endpoints';
import { LoadingButton } from '@mui/lab';
import {
  PlayArrowIcon,
  SmartToyIcon,
  DevicesIcon,
  WebIcon,
  StorageIcon,
  CodeIcon,
  DataObjectIcon,
  CloudIcon,
  AnalyticsIcon,
  ShoppingCartIcon,
  TerminalIcon,
  VideogameAssetIcon,
  ChatIcon,
  PsychologyIcon,
  DashboardIcon,
  SearchIcon,
  AutoFixHighIcon,
  PhoneIphoneIcon,
  SchoolIcon,
  ScienceIcon,
  AccountTreeIcon,
  VisibilityIcon,
  VisibilityOffIcon,
  InfoIcon,
  LockIcon,
} from '@/components/icons';
import { useSession } from 'next-auth/react';
import { useNotifications } from '@/components/common/NotificationContext';
import { useOnboarding } from '@/contexts/OnboardingContext';

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

// Lazy load Monaco Editor
const Editor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => (
    <Box
      sx={{
        height: '200px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: 1,
        borderColor: 'divider',
        borderRadius: theme => theme.shape.borderRadius,
        backgroundColor: 'background.default',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={20} />
        <Typography variant="body2" color="text.secondary">
          Loading editor...
        </Typography>
      </Box>
    </Box>
  ),
});

// Enums based on your backend models
const CONNECTION_TYPES = ['REST', 'WEBSOCKET', 'GRPC', 'SDK'];
const ENVIRONMENTS = ['production', 'staging', 'development'];
const METHODS = ['POST'];

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`endpoint-tabpanel-${index}`}
      aria-labelledby={`endpoint-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

interface FormData
  extends Omit<
    Endpoint,
    'id' | 'request_headers' | 'request_mapping' | 'response_mapping'
  > {
  request_headers?: string;
  request_mapping?: string;
  response_mapping?: string;
  auth_token?: string; // Write-only field for create/update
}

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

export default function EndpointForm() {
  const router = useRouter();
  const params = useParams<{ identifier?: string }>();
  const theme = useTheme();
  const projectIdFromUrl = params?.identifier || '';
  const [error, setError] = useState<string | null>(null);
  const [currentTab, setCurrentTab] = useState(0);
  const [urlError] = useState<string | null>(null);
  const [testResponse, setTestResponse] = useState<string>('');
  const [isTestingEndpoint, setIsTestingEndpoint] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState<boolean>(true);
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { data: session } = useSession();
  const notifications = useNotifications();
  const { markStepComplete } = useOnboarding();

  // Determine editor theme based on MUI theme
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';

  // Theme-aware editor wrapper style
  const editorWrapperStyle = {
    border: 1,
    borderColor: 'divider',
    borderRadius: theme.shape.borderRadius,
    '&:hover': {
      borderColor: 'text.primary',
    },
    '&:focus-within': {
      borderWidth: 2,
      borderColor: 'primary.main',
      margin: '-1px',
    },
  };

  const [formData, setFormData] = useState<FormData>({
    name: '',
    description: '',
    connection_type: 'REST',
    url: '',
    environment: 'development',
    config_source: 'manual',
    response_format: 'json',
    method: 'POST',
    endpoint_path: '',
    project_id: '',
    organization_id: '',
    auth_token: '',
    request_headers: '{}',
    request_mapping: '{}',
    response_mapping: '{}',
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
      if (!session?.session_token) {
        setLoadingProjects(false);
        return;
      }

      try {
        setLoadingProjects(true);
        const client = new ApiClientFactory(
          session.session_token
        ).getProjectsClient();
        const data = await client.getProjects();
        setProjects(Array.isArray(data) ? data : data?.data || []);
      } catch {
        setError('Failed to load projects. Please try again later.');
        setProjects([]);
      } finally {
        setLoadingProjects(false);
      }
    };

    fetchProjects();
  }, [session]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  const validateUrl = (url: string): boolean => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  const handleChange = (field: keyof FormData, value: unknown) => {
    setFormData((prev: FormData) => ({ ...prev, [field]: value }));
  };

  const handleJsonChange = (field: string, value: string) => {
    try {
      // Validate JSON if not empty
      if (value.trim()) {
        JSON.parse(value);
      }
      setFormData(prev => ({
        ...prev,
        [field]: value,
      }));
      setError(null);
    } catch (err) {
      setError(`Invalid JSON in ${field}`);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.url || !validateUrl(formData.url)) {
      setError('Please enter a valid URL');
      return;
    }

    if (!formData.project_id) {
      setError('Please select a project');
      return;
    }

    setIsSubmitting(true);
    try {
      const transformedData = { ...formData } as Partial<typeof formData>;

      // Handle JSON string fields
      const jsonStringFields = [
        'request_headers',
        'request_mapping',
        'response_mapping',
      ] as const;
      for (const field of jsonStringFields) {
        const value = transformedData[field] as string;
        if (value && typeof value === 'string' && value.trim()) {
          try {
            (transformedData as Record<string, unknown>)[field] =
              JSON.parse(value);
          } catch {
            delete (transformedData as Record<string, unknown>)[field];
          }
        } else {
          delete (transformedData as Record<string, unknown>)[field];
        }
      }

      // Remove organization_id as it should not be part of the request
      delete (transformedData as Record<string, unknown>).organization_id;

      // Remove empty project_id
      if (!transformedData.project_id || transformedData.project_id === '') {
        delete (transformedData as Record<string, unknown>).project_id;
      }

      // Handle auth_token: only include if it has a value
      if (!transformedData.auth_token || transformedData.auth_token === '') {
        delete (transformedData as any).auth_token;
      }

      // Ensure we're sending a single object, not an array
      const endpointData = transformedData as unknown as Omit<Endpoint, 'id'>;
      await createEndpoint(endpointData);

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
              disabled={(projects?.length || 0) === 0 && !loadingProjects}
            >
              Create Endpoint
            </LoadingButton>
          </Box>
        </Box>

        {/* Tabs row */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs
            value={currentTab}
            onChange={handleTabChange}
            aria-label="endpoint configuration tabs"
          >
            <Tab label="Basic Information" />
            <Tab label="Request Settings" />
            <Tab label="Response Settings" />
            <Tab label="Test Connection" />
          </Tabs>
        </Box>

        {/* Basic Information Tab */}
        <TabPanel value={currentTab} index={0}>
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
                    required
                    label="Name"
                    name="name"
                    value={formData.name}
                    onChange={e => handleChange('name', e.target.value)}
                    helperText="A unique name to identify this endpoint"
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
                    name="description"
                    value={formData.description}
                    onChange={e => handleChange('description', e.target.value)}
                    multiline
                    rows={1}
                  />
                </Grid>
              </Grid>
            </Grid>
            {/* Request Configuration */}
            <Grid size={12}>
              <Typography variant="subtitle1" sx={{ mb: 2 }}>
                Request Configuration
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
                    label="URL"
                    name="url"
                    value={formData.url}
                    onChange={e => handleChange('url', e.target.value)}
                    required
                    error={Boolean(urlError)}
                    helperText={urlError}
                    placeholder="https://api.example.com"
                  />
                </Grid>
                <Grid
                  size={{
                    xs: 12,
                    md: 3,
                  }}
                >
                  <FormControl fullWidth>
                    <InputLabel>Connection Type</InputLabel>
                    <Select
                      name="connectionType"
                      value={formData.connection_type}
                      onChange={e =>
                        handleChange('connection_type', e.target.value)
                      }
                      label="Connection Type"
                      required
                    >
                      {CONNECTION_TYPES.map(connectionType => (
                        <MenuItem key={connectionType} value={connectionType}>
                          {connectionType}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid
                  size={{
                    xs: 12,
                    md: 3,
                  }}
                >
                  <FormControl fullWidth>
                    <InputLabel>Method</InputLabel>
                    <Select
                      name="method"
                      value={formData.method}
                      onChange={e => handleChange('method', e.target.value)}
                      label="Method"
                    >
                      {METHODS.map(method => (
                        <MenuItem key={method} value={method}>
                          {method}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
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
                  {(projects?.length || 0) === 0 && !loadingProjects ? (
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
                        name="project_id"
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

            {/* Environment & Configuration */}
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
                        handleChange('environment', newValue);
                      }
                    }}
                    aria-label="environment selection"
                    sx={{
                      '& .MuiToggleButton-root.Mui-selected': {
                        backgroundColor: 'primary.main',
                        color: 'primary.contrastText',
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
        </TabPanel>

        {/* Request Settings Tab */}
        <TabPanel value={currentTab} index={1}>
          <Grid container spacing={2}>
            {/* Authentication Token Section */}
            <Grid size={12}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Authorization (Optional)
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Token will be encrypted and automatically included as{' '}
                <code>Authorization: Bearer {'<token>'}</code>. Use{' '}
                <code>{'{{ auth_token }}'}</code> placeholder in custom headers.
              </Typography>

              <TextField
                fullWidth
                label="API Token"
                type={showAuthToken ? 'text' : 'password'}
                value={formData.auth_token}
                onChange={e => handleChange('auth_token', e.target.value)}
                placeholder="sk-..."
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <LockIcon color="action" />
                    </InputAdornment>
                  ),
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        aria-label="toggle token visibility"
                        onClick={() => setShowAuthToken(!showAuthToken)}
                        edge="end"
                      >
                        {showAuthToken ? (
                          <VisibilityOffIcon />
                        ) : (
                          <VisibilityIcon />
                        )}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
                helperText="Token will be encrypted and stored securely"
              />
            </Grid>

            <Grid size={12}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Request Headers (Optional)
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Custom headers for your endpoint. Authorization and Content-Type
                are automatically provided. Example:{' '}
                <code>{`{
  "x-api-key": "{{ auth_token }}",
  "x-custom-header": "value"
}`}</code>
              </Typography>
              <Box sx={editorWrapperStyle}>
                <Editor
                  key={`request-headers-${editorTheme}`}
                  height="200px"
                  defaultLanguage="json"
                  theme={editorTheme}
                  value={formData.request_headers}
                  onChange={value =>
                    handleJsonChange('request_headers', value || '')
                  }
                  options={{
                    minimap: { enabled: false },
                    lineNumbers: 'on',
                    folding: true,
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    formatOnPaste: true,
                    formatOnType: true,
                    padding: { top: 8, bottom: 8 },
                    scrollbar: {
                      vertical: 'visible',
                      horizontal: 'visible',
                    },
                    fontSize: 14,
                  }}
                />
              </Box>
            </Grid>
            <Grid size={12}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Request Body Template defines the structure of your request with
                placeholders for dynamic values.
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Example:{' '}
                <code>{`{
  "model": "gpt-3.5-turbo",
  "messages": [
    {
      "role": "user",
      "content": "{user_input}"
    }
  ],
  "temperature": 0.7
}`}</code>
              </Typography>
              <Box sx={editorWrapperStyle}>
                <Editor
                  key={`request-body-${editorTheme}`}
                  height="300px"
                  defaultLanguage="json"
                  theme={editorTheme}
                  value={formData.request_mapping}
                  onChange={value =>
                    handleJsonChange('request_mapping', value || '')
                  }
                  options={{
                    minimap: { enabled: false },
                    lineNumbers: 'on',
                    folding: true,
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    formatOnPaste: true,
                    formatOnType: true,
                    padding: { top: 8, bottom: 8 },
                    scrollbar: {
                      vertical: 'visible',
                      horizontal: 'visible',
                    },
                    fontSize: 14,
                  }}
                />
              </Box>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Response Settings Tab */}
        <TabPanel value={currentTab} index={2}>
          <Grid container spacing={2}>
            <Grid size={12}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Response Mappings define how to extract values from the API
                response using JSONPath syntax.
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Example:{' '}
                <code>{'{ "output": "$.choices[0].message.content" }'}</code>
              </Typography>
              <Box sx={editorWrapperStyle}>
                <Editor
                  key={`response-mappings-${editorTheme}`}
                  height="200px"
                  defaultLanguage="json"
                  theme={editorTheme}
                  value={formData.response_mapping}
                  onChange={value =>
                    handleJsonChange('response_mapping', value || '')
                  }
                  options={{
                    minimap: { enabled: false },
                    lineNumbers: 'on',
                    folding: true,
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    formatOnPaste: true,
                    formatOnType: true,
                    padding: { top: 8, bottom: 8 },
                    scrollbar: {
                      vertical: 'visible',
                      horizontal: 'visible',
                    },
                    fontSize: 14,
                  }}
                />
              </Box>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Test Connection Tab */}
        <TabPanel value={currentTab} index={3}>
          <Grid container spacing={2}>
            <Grid size={12}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Test your endpoint configuration with sample data
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Enter sample JSON data. It will be matched to your request
                template and parsed using your response mappings.
              </Typography>
              <Box sx={editorWrapperStyle}>
                <Editor
                  key={`test-input-${editorTheme}`}
                  height="200px"
                  defaultLanguage="json"
                  theme={editorTheme}
                  defaultValue={`{
  "input": "[place your input here]"
}`}
                  options={{
                    minimap: { enabled: false },
                    lineNumbers: 'on',
                    folding: true,
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    formatOnPaste: true,
                    formatOnType: true,
                    padding: { top: 8, bottom: 8 },
                    scrollbar: {
                      vertical: 'visible',
                      horizontal: 'visible',
                    },
                    fontSize: 14,
                  }}
                />
              </Box>
            </Grid>

            <Grid sx={{ mt: 2 }} size={12}>
              <LoadingButton
                variant="contained"
                color="primary"
                onClick={async () => {
                  setIsTestingEndpoint(true);
                  try {
                    // TODO: Implement actual test logic here
                    await new Promise(resolve => setTimeout(resolve, 1000)); // Simulated delay
                    setTestResponse(
                      JSON.stringify(
                        {
                          success: true,
                          message: 'Response from endpoint',
                          data: {
                            output: 'Sample response data',
                          },
                        },
                        null,
                        2
                      )
                    );
                  } catch (error) {
                    setTestResponse(
                      JSON.stringify(
                        {
                          success: false,
                          error: (error as Error).message,
                        },
                        null,
                        2
                      )
                    );
                  } finally {
                    setIsTestingEndpoint(false);
                  }
                }}
                loading={isTestingEndpoint}
                loadingPosition="start"
                startIcon={<PlayArrowIcon />}
              >
                Test Endpoint
              </LoadingButton>
            </Grid>

            {testResponse && (
              <Grid size={12}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Response
                </Typography>
                <Box sx={editorWrapperStyle}>
                  <Editor
                    key={`test-response-${editorTheme}`}
                    height="200px"
                    defaultLanguage="json"
                    theme={editorTheme}
                    value={testResponse}
                    options={{
                      minimap: { enabled: false },
                      lineNumbers: 'on',
                      folding: true,
                      scrollBeyondLastLine: false,
                      automaticLayout: true,
                      readOnly: true,
                      padding: { top: 8, bottom: 8 },
                      scrollbar: {
                        vertical: 'visible',
                        horizontal: 'visible',
                      },
                      fontSize: 14,
                    }}
                  />
                </Box>
              </Grid>
            )}
          </Grid>
        </TabPanel>
      </Card>
      {error && (
        <Box sx={{ mt: 2 }}>
          <Alert severity="error">{error}</Alert>
        </Box>
      )}
    </form>
  );
}
