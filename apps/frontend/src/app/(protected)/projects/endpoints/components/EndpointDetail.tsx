'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  Grid,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  ListItemIcon,
  ListItemText,
  Chip,
  Alert,
  Snackbar,
  IconButton,
  InputAdornment,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import dynamic from 'next/dynamic';
import {
  Endpoint,
  EndpointEditData,
} from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import {
  EditIcon,
  SaveIcon,
  CancelIcon,
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
  LockIcon,
} from '@/components/icons';
import { LoadingButton } from '@mui/lab';
import { updateEndpoint, invokeEndpoint } from '@/actions/endpoints';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useSession } from 'next-auth/react';
import { useNotifications } from '@/components/common/NotificationContext';

// Constants for select fields
const CONNECTION_TYPES = ['REST', 'WEBSOCKET', 'GRPC', 'SDK'];
const ENVIRONMENTS = ['production', 'staging', 'development'];
const METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];

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

// Environment chips should use neutral colors for better UX
const getEnvironmentColor = ():
  | 'default'
  | 'primary'
  | 'secondary'
  | 'error'
  | 'info'
  | 'success'
  | 'warning' => {
  // Use 'default' for all environments to get neutral grey styling
  return 'default';
};

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

interface EndpointDetailProps {
  endpoint: Endpoint;
}

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

export default function EndpointDetail({
  endpoint: initialEndpoint,
}: EndpointDetailProps) {
  const theme = useTheme();
  const [endpoint, setEndpoint] = useState<Endpoint>(initialEndpoint);
  const [currentTab, setCurrentTab] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const [editedValues, setEditedValues] = useState<EndpointEditData>({});
  const [isSaving, setIsSaving] = useState(false);
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [tokenFieldFocused, setTokenFieldFocused] = useState(false);

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

  // Auto-enable edit mode when user starts typing
  const autoEnableEditMode = () => {
    if (!isEditing) {
      setIsEditing(true);
    }
  };

  // Check if endpoint has an existing token (we assume it does if this is an existing endpoint)
  const hasExistingToken = !!endpoint.id;
  const [notification, setNotification] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });
  const [testResponse, setTestResponse] = useState<string>('');
  const [isTestingEndpoint, setIsTestingEndpoint] = useState(false);
  const [testInput, setTestInput] = useState<string>(`{
  "input": "[place your input here]"
}`);

  // Add projects state and loading state
  const [projects, setProjects] = useState<Record<string, Project>>({});
  const [loadingProjects, setLoadingProjects] = useState<boolean>(true);
  const { data: session } = useSession();
  const notifications = useNotifications();

  // Fetch projects when component mounts
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoadingProjects(true);
        const sessionToken = session?.session_token || '';

        if (sessionToken) {
          const client = new ApiClientFactory(sessionToken).getProjectsClient();
          const response = await client.getProjects();

          // Create a map for faster lookups
          const projectMap: Record<string, Project> = {};
          const projectsArray = Array.isArray(response)
            ? response
            : response?.data;

          if (Array.isArray(projectsArray)) {
            projectsArray.forEach((project: Project) => {
              if (project && project.id) {
                projectMap[project.id] = project;
              }
            });
          }

          setProjects(projectMap);
        }
      } catch {
        // Error handled silently
      } finally {
        setLoadingProjects(false);
      }
    };

    if (session) {
      fetchProjects();
    }
  }, [session]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  const handleEdit = () => {
    setIsEditing(true);
    setEditedValues(endpoint);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditedValues({});
    setTokenFieldFocused(false); // Reset token field state
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);

      // Clean up the payload: remove auth_token if it's empty (to keep existing token)
      const payload = { ...editedValues };
      if (payload.auth_token === '') {
        delete payload.auth_token;
      }

      const result = await updateEndpoint(endpoint.id, payload);

      if (result.success) {
        setEndpoint({ ...endpoint, ...editedValues });
        setIsEditing(false);
        setEditedValues({});
        setTokenFieldFocused(false); // Reset token field state
        notifications.show('Endpoint updated successfully', {
          severity: 'success',
        });
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      notifications.show(
        `Failed to update endpoint: ${(error as Error).message}`,
        { severity: 'error' }
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleChange = (field: keyof EndpointEditData, value: any) => {
    autoEnableEditMode();
    setEditedValues(prev => ({ ...prev, [field]: value }));
  };

  const handleJsonChange = (field: keyof EndpointEditData, value: string) => {
    autoEnableEditMode();
    try {
      const parsedValue = JSON.parse(value);
      setEditedValues(prev => ({ ...prev, [field]: parsedValue }));
    } catch {
      // Handle JSON parse error if needed
      setEditedValues(prev => ({ ...prev, [field]: value }));
    }
  };

  return (
    <>
      <Paper elevation={2} sx={{ mb: 4 }}>
        <Box
          sx={{
            borderBottom: 1,
            borderColor: 'divider',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            pr: 2,
          }}
        >
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
          {isEditing ? (
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                startIcon={<SaveIcon />}
                variant="contained"
                onClick={handleSave}
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : 'Save'}
              </Button>
              <Button
                startIcon={<CancelIcon />}
                variant="outlined"
                onClick={handleCancel}
                disabled={isSaving}
              >
                Cancel
              </Button>
            </Box>
          ) : (
            <Button
              startIcon={<EditIcon />}
              variant="outlined"
              onClick={handleEdit}
            >
              Edit
            </Button>
          )}
        </Box>

        <TabPanel value={currentTab} index={0}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="subtitle1" sx={{ mb: 2 }}>
                Basic Details
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  {isEditing ? (
                    <TextField
                      fullWidth
                      label="Name"
                      value={editedValues.name || ''}
                      onChange={e => handleChange('name', e.target.value)}
                    />
                  ) : (
                    <>
                      <Typography variant="subtitle2" color="text.secondary">
                        Name
                      </Typography>
                      <Typography variant="body1">{endpoint.name}</Typography>
                    </>
                  )}
                </Grid>
                <Grid item xs={12} md={6}>
                  {isEditing ? (
                    <TextField
                      fullWidth
                      label="Description"
                      value={editedValues.description || ''}
                      onChange={e =>
                        handleChange('description', e.target.value)
                      }
                      multiline
                      rows={1}
                    />
                  ) : (
                    <>
                      <Typography variant="subtitle2" color="text.secondary">
                        Description
                      </Typography>
                      <Typography variant="body1">
                        {endpoint.description || 'No description provided'}
                      </Typography>
                    </>
                  )}
                </Grid>
              </Grid>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle1" sx={{ mb: 2 }}>
                Request Configuration
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  {isEditing ? (
                    <TextField
                      fullWidth
                      label="URL"
                      value={editedValues.url || ''}
                      onChange={e => handleChange('url', e.target.value)}
                    />
                  ) : (
                    <>
                      <Typography variant="subtitle2" color="text.secondary">
                        URL
                      </Typography>
                      <Typography variant="body1">{endpoint.url}</Typography>
                    </>
                  )}
                </Grid>
                <Grid item xs={12} md={3}>
                  {isEditing ? (
                    <FormControl fullWidth>
                      <InputLabel>Connection Type</InputLabel>
                      <Select
                        value={editedValues.connection_type || ''}
                        label="Connection Type"
                        onChange={e => handleChange('connection_type', e.target.value)}
                      >
                        {CONNECTION_TYPES.map(connectionType => (
                          <MenuItem key={connectionType} value={connectionType}>
                            {connectionType}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  ) : (
                    <>
                      <Typography variant="subtitle2" color="text.secondary">
                        Connection Type
                      </Typography>
                      <Typography variant="body1">
                        {endpoint.connection_type}
                      </Typography>
                    </>
                  )}
                </Grid>
                <Grid item xs={12} md={3}>
                  {isEditing ? (
                    <FormControl fullWidth>
                      <InputLabel>Method</InputLabel>
                      <Select
                        value={editedValues.method || ''}
                        label="Method"
                        onChange={e => handleChange('method', e.target.value)}
                      >
                        {METHODS.map(method => (
                          <MenuItem key={method} value={method}>
                            {method}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  ) : (
                    <>
                      <Typography variant="subtitle2" color="text.secondary">
                        Method
                      </Typography>
                      <Typography variant="body1">{endpoint.method}</Typography>
                    </>
                  )}
                </Grid>
              </Grid>
            </Grid>

            {/* Project Selection */}
            <Grid item xs={12}>
              <Typography variant="subtitle1" sx={{ mb: 2 }}>
                Project
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  {isEditing ? (
                    <FormControl fullWidth>
                      <InputLabel>Project</InputLabel>
                      <Select
                        value={editedValues.project_id || ''}
                        label="Project"
                        onChange={e =>
                          handleChange('project_id', e.target.value)
                        }
                      >
                        <MenuItem value="">
                          <em>None</em>
                        </MenuItem>
                        {loadingProjects ? (
                          <MenuItem disabled>
                            <CircularProgress size={20} />
                            <Box component="span" sx={{ ml: 1 }}>
                              Loading projects...
                            </Box>
                          </MenuItem>
                        ) : (
                          Object.values(projects).map(project => (
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
                    </FormControl>
                  ) : (
                    <>
                      {endpoint.project_id ? (
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          {projects[endpoint.project_id] && (
                            <Box
                              sx={{
                                mr: 1,
                                display: 'flex',
                                alignItems: 'center',
                              }}
                            >
                              {getProjectIcon(projects[endpoint.project_id])}
                            </Box>
                          )}
                          <Typography variant="body1">
                            {projects[endpoint.project_id]?.name ||
                              'Loading project...'}
                          </Typography>
                        </Box>
                      ) : (
                        <Typography variant="body1">
                          No project assigned
                        </Typography>
                      )}
                    </>
                  )}
                </Grid>
              </Grid>
            </Grid>

            <Grid item xs={12}>
              {isEditing ? (
                <FormControl fullWidth>
                  <InputLabel>Environment</InputLabel>
                  <Select
                    value={editedValues.environment || ''}
                    label="Environment"
                    onChange={e => handleChange('environment', e.target.value)}
                  >
                    {ENVIRONMENTS.map(env => (
                      <MenuItem key={env} value={env}>
                        {env}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ) : (
                <>
                  <Typography variant="subtitle1" sx={{ mb: 2 }}>
                    Environment
                  </Typography>
                  <Chip
                    label={endpoint.environment}
                    color={getEnvironmentColor()}
                    variant="outlined"
                    sx={{ textTransform: 'capitalize' }}
                  />
                </>
              )}
            </Grid>
          </Grid>
        </TabPanel>

        <TabPanel value={currentTab} index={1}>
          <Grid container spacing={2}>
            {/* Authorization Section */}
            <Grid item xs={12}>
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
                value={
                  editedValues.auth_token !== undefined
                    ? editedValues.auth_token
                    : hasExistingToken && !tokenFieldFocused
                      ? '••••••••••••••••••••••••'
                      : ''
                }
                onChange={e => {
                  autoEnableEditMode();
                  setEditedValues({
                    ...editedValues,
                    auth_token: e.target.value,
                  });
                }}
                onFocus={() => {
                  setTokenFieldFocused(true);
                  if (editedValues.auth_token === undefined) {
                    setEditedValues({ ...editedValues, auth_token: '' });
                  }
                }}
                onBlur={() => {
                  // If user didn't enter anything, revert to showing existing token indicator
                  if (editedValues.auth_token === '') {
                    setTokenFieldFocused(false);
                    const newEditedValues = { ...editedValues };
                    delete newEditedValues.auth_token;
                    setEditedValues(newEditedValues);
                  }
                }}
                placeholder={
                  hasExistingToken
                    ? 'Enter new token or leave empty to keep existing'
                    : 'sk-...'
                }
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
                helperText={
                  hasExistingToken
                    ? 'Token is encrypted and stored securely. Enter a new token to update, or leave empty to keep existing.'
                    : 'Token will be encrypted and stored securely.'
                }
              />
            </Grid>

            <Grid item xs={12}>
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
                  value={JSON.stringify(
                    isEditing
                      ? editedValues.request_headers
                      : endpoint.request_headers || {},
                    null,
                    2
                  )}
                  onChange={value =>
                    handleJsonChange('request_headers', value || '')
                  }
                  options={{
                    readOnly: !isEditing,
                    minimap: { enabled: false },
                    lineNumbers: 'on',
                    scrollBeyondLastLine: false,
                  }}
                />
              </Box>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Request Body Template
              </Typography>
              <Box sx={editorWrapperStyle}>
                <Editor
                  key={`request-body-${editorTheme}`}
                  height="300px"
                  defaultLanguage="json"
                  theme={editorTheme}
                  value={JSON.stringify(
                    isEditing
                      ? editedValues.request_mapping
                      : endpoint.request_mapping || {},
                    null,
                    2
                  )}
                  onChange={value =>
                    handleJsonChange('request_mapping', value || '')
                  }
                  options={{
                    readOnly: !isEditing,
                    minimap: { enabled: false },
                    lineNumbers: 'on',
                    scrollBeyondLastLine: false,
                  }}
                />
              </Box>
            </Grid>
          </Grid>
        </TabPanel>

        <TabPanel value={currentTab} index={2}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Response Mappings
              </Typography>
              <Box sx={editorWrapperStyle}>
                <Editor
                  key={`response-mappings-${editorTheme}`}
                  height="200px"
                  defaultLanguage="json"
                  theme={editorTheme}
                  value={JSON.stringify(
                    isEditing
                      ? editedValues.response_mapping
                      : endpoint.response_mapping || {},
                    null,
                    2
                  )}
                  onChange={value =>
                    handleJsonChange('response_mapping', value || '')
                  }
                  options={{
                    readOnly: !isEditing,
                    minimap: { enabled: false },
                    lineNumbers: 'on',
                    scrollBeyondLastLine: false,
                  }}
                />
              </Box>
            </Grid>
          </Grid>
        </TabPanel>

        <TabPanel value={currentTab} index={3}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
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
                  value={testInput}
                  onChange={value => setTestInput(value || '')}
                  options={{
                    minimap: { enabled: false },
                    lineNumbers: 'on',
                    folding: true,
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                  }}
                />
              </Box>
            </Grid>

            <Grid item xs={12} sx={{ mt: 2 }}>
              <LoadingButton
                variant="contained"
                color="primary"
                onClick={async () => {
                  setIsTestingEndpoint(true);
                  try {
                    let inputData;
                    try {
                      inputData = JSON.parse(testInput);
                    } catch (error) {
                      throw new Error('Invalid JSON input data');
                    }

                    const result = await invokeEndpoint(endpoint.id, inputData);
                    if (result.success) {
                      setTestResponse(JSON.stringify(result.data, null, 2));
                    } else {
                      throw new Error(result.error);
                    }
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
              <Grid item xs={12}>
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
                      readOnly: true,
                      minimap: { enabled: false },
                      lineNumbers: 'on',
                      folding: true,
                      scrollBeyondLastLine: false,
                    }}
                  />
                </Box>
              </Grid>
            )}
          </Grid>
        </TabPanel>
      </Paper>
    </>
  );
}
