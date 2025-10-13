'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Stack,
  Chip,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import EditIcon from '@mui/icons-material/Edit';
import { DeleteIcon, AddIcon, CloudIcon } from '@/components/icons';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Model, ModelCreate } from '@/utils/api-client/interfaces/model';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { DeleteModal } from '@/components/common/DeleteModal';
import { UUID } from 'crypto';
import {
  SUPPORTED_PROVIDERS,
  PROVIDERS_REQUIRING_ENDPOINT,
  DEFAULT_ENDPOINTS,
  PROVIDER_ICONS,
  type ProviderInfo,
} from '@/config/model-providers';

interface ProviderSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelectProvider: (provider: TypeLookup) => void;
  providers: TypeLookup[];
}

function ProviderSelectionDialog({
  open,
  onClose,
  onSelectProvider,
  providers,
}: ProviderSelectionDialogProps) {
  if (!providers || providers.length === 0) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>Select LLM Provider</DialogTitle>
        <DialogContent>
          <Box sx={{ py: 2, textAlign: 'center' }}>
            <Typography color="text.secondary">
              No providers available. Please try again later.
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  }

  // Sort providers: enabled first (alphabetically), then coming soon (alphabetically)
  const sortedProviders = [...providers].sort((a, b) => {
    const aSupported = SUPPORTED_PROVIDERS.includes(a.type_value);
    const bSupported = SUPPORTED_PROVIDERS.includes(b.type_value);

    // If support status differs, supported comes first
    if (aSupported !== bSupported) {
      return bSupported ? 1 : -1;
    }

    // Within same support status, sort alphabetically
    return a.type_value.localeCompare(b.type_value);
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Select Model Provider</DialogTitle>
      <DialogContent>
        <List>
          {sortedProviders.map(provider => {
            const isSupported = SUPPORTED_PROVIDERS.includes(
              provider.type_value
            );
            const providerInfo: ProviderInfo = {
              id: provider.type_value,
              name: provider.description || provider.type_value,
              description: provider.description || '',
              icon: PROVIDER_ICONS[provider.type_value] || (
                <SmartToyIcon
                  sx={{ fontSize: theme => theme.iconSizes.large }}
                />
              ),
            };

            return (
              <ListItemButton
                key={provider.id}
                onClick={() => isSupported && onSelectProvider(provider)}
                disabled={!isSupported}
                sx={{
                  borderRadius: theme => theme.shape.borderRadius * 0.25,
                  my: 0.5,
                  opacity: isSupported ? 1 : 0.5,
                  cursor: isSupported ? 'pointer' : 'not-allowed',
                  '&:hover': {
                    backgroundColor: isSupported
                      ? 'action.hover'
                      : 'transparent',
                  },
                  '&.Mui-disabled': {
                    opacity: 0.5,
                  },
                }}
              >
                <ListItemIcon sx={{ opacity: isSupported ? 1 : 0.4 }}>
                  {providerInfo.icon}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography>{providerInfo.name}</Typography>
                      {!isSupported && (
                        <Chip
                          label="Coming Soon"
                          size="small"
                          color="default"
                          sx={{
                            height: 20,
                            fontSize: '0.7rem',
                            fontWeight: 500,
                          }}
                        />
                      )}
                    </Box>
                  }
                  secondary={providerInfo.description}
                  secondaryTypographyProps={{
                    sx: { opacity: isSupported ? 1 : 0.6 },
                  }}
                />
              </ListItemButton>
            );
          })}
        </List>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
}

interface ConnectionDialogProps {
  open: boolean;
  provider: TypeLookup | null;
  model?: Model | null; // For edit mode
  mode?: 'create' | 'edit';
  onClose: () => void;
  onConnect?: (providerId: string, modelData: ModelCreate) => Promise<void>;
  onUpdate?: (modelId: UUID, updates: Partial<ModelCreate>) => Promise<void>;
}

function ConnectionDialog({
  open,
  provider,
  model,
  mode = 'create',
  onClose,
  onConnect,
  onUpdate,
}: ConnectionDialogProps) {
  const [name, setName] = useState('');
  const [providerName, setProviderName] = useState('');
  const [modelName, setModelName] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [customHeaders, setCustomHeaders] = useState<Record<string, string>>(
    {}
  );
  const [newHeaderKey, setNewHeaderKey] = useState('');
  const [newHeaderValue, setNewHeaderValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    fullError?: string;
  } | null>(null);
  const [showFullError, setShowFullError] = useState(false);
  const [connectionTested, setConnectionTested] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  const isEditMode = mode === 'edit';
  const isCustomProvider = provider?.type_value === 'vllm';
  
  // Determine requiresEndpoint from either provider or model
  const requiresEndpoint = isEditMode && model?.provider_type
    ? PROVIDERS_REQUIRING_ENDPOINT.includes(model.provider_type.type_value)
    : provider
    ? PROVIDERS_REQUIRING_ENDPOINT.includes(provider.type_value)
    : false;

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      if (isEditMode && model) {
        // Edit mode: populate with existing model data
        setName(model.name || '');
        setModelName(model.model_name || '');
        setEndpoint(model.endpoint || '');
        setApiKey('************'); // Show placeholder for existing key
        setCustomHeaders(model.request_headers || {});
        setProviderName('');
        setError(null);
        setTestResult(null);
        setShowFullError(false);
        setConnectionTested(true); // Skip test requirement in edit mode
        setShowApiKey(false);
      } else if (provider) {
        // Create mode: reset to defaults
        setName('');
        setProviderName('');
        setModelName('');
        // Set default endpoint if provider requires it
        setEndpoint(
          PROVIDERS_REQUIRING_ENDPOINT.includes(provider.type_value)
            ? DEFAULT_ENDPOINTS[provider.type_value] || ''
            : ''
        );
        setApiKey('');
        setCustomHeaders({});
        setNewHeaderKey('');
        setNewHeaderValue('');
        setError(null);
        setTestResult(null);
        setShowFullError(false);
        setConnectionTested(false);
        setShowApiKey(false);
      }
    }
  }, [open, provider, model, isEditMode]);

  // Reset connection test status when critical fields change
  useEffect(() => {
    if (!isEditMode) {
      // In create mode, always reset when fields change
      setConnectionTested(false);
      setTestResult(null);
    } else if (apiKey && apiKey !== '************') {
      // In edit mode, reset only if API key was actually changed
      setConnectionTested(false);
      setTestResult(null);
    }
  }, [modelName, apiKey, endpoint, isEditMode]);

  const handleAddHeader = () => {
    if (newHeaderKey.trim() && newHeaderValue.trim()) {
      setCustomHeaders(prev => ({
        ...prev,
        [newHeaderKey.trim()]: newHeaderValue.trim(),
      }));
      setNewHeaderKey('');
      setNewHeaderValue('');
    }
  };

  const handleRemoveHeader = (key: string) => {
    setCustomHeaders(prev => {
      const newHeaders = { ...prev };
      delete newHeaders[key];
      return newHeaders;
    });
  };

  const { data: session } = useSession();

  const handleTestConnection = async () => {
    // Get provider from either new connection or existing model
    const currentProvider = isEditMode && model?.provider_type 
      ? model.provider_type 
      : provider;

    if (!currentProvider || !modelName || !apiKey || apiKey === '************') {
      setTestResult({
        success: false,
        message: 'Please fill in provider, model name, and API key',
      });
      return;
    }

    if (!session?.session_token) {
      setTestResult({
        success: false,
        message: 'No session token available',
      });
      return;
    }

    setTestingConnection(true);
    setTestResult(null);
    setError(null);
    setShowFullError(false);

    try {
      const requestBody: any = {
        provider: currentProvider.type_value,
        model_name: modelName,
        api_key: apiKey,
      };

      // Only include endpoint if it's required and has a value
      if (requiresEndpoint && endpoint && endpoint.trim()) {
        requestBody.endpoint = endpoint.trim();
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'}/models/test-connection`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session.session_token}`,
          },
          body: JSON.stringify(requestBody),
        }
      );

      const result = await response.json();

      if (result.success) {
        setTestResult({
          success: true,
          message: result.message,
        });
        setConnectionTested(true);
      } else {
        // Extract a friendly error message
        const fullError = result.message;
        let friendlyMessage = 'Connection test failed';

        // Try to extract the most user-friendly part of the error
        const lowerError = fullError.toLowerCase();
        if (lowerError.includes('api key') || lowerError.includes('unauthorized')) {
          friendlyMessage = 'Invalid API key. Please check your credentials.';
        } else if (lowerError.includes('not found') || lowerError.includes('404')) {
          friendlyMessage = `Model '${modelName}' not found for ${currentProvider.type_value}.`;
        } else if (lowerError.includes('quota') || lowerError.includes('rate limit')) {
          friendlyMessage = 'API quota exceeded or rate limit reached.';
        } else if (lowerError.includes('connection') || lowerError.includes('timeout')) {
          friendlyMessage = 'Connection failed. Check endpoint URL and network.';
        }

        setTestResult({
          success: false,
          message: friendlyMessage,
          fullError: fullError,
        });
      }
    } catch (err) {
      const fullError = err instanceof Error ? err.message : 'Unknown error occurred';
      setTestResult({
        success: false,
        message: 'Failed to test connection. Please try again.',
        fullError: fullError,
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (isEditMode && model && onUpdate) {
      // Edit mode: update existing model
      setLoading(true);
      setError(null);
      try {
        const updates: Partial<ModelCreate> = {
          name,
          model_name: modelName,
        };

        // Only include endpoint if it's required and has a value
        if (requiresEndpoint && endpoint && endpoint.trim()) {
          updates.endpoint = endpoint.trim();
        }

        // Only include API key if it was changed (not the placeholder)
        if (apiKey && apiKey.trim() && apiKey !== '************') {
          updates.key = apiKey.trim();
          // Update request headers with new API key
          updates.request_headers = {
            ...customHeaders,
            Authorization: `Bearer ${apiKey.trim()}`,
            'Content-Type': 'application/json',
          };
        } else if (Object.keys(customHeaders).length > 0) {
          // Update custom headers without changing API key
          updates.request_headers = {
            ...model.request_headers,
            ...customHeaders,
          };
        }

        await onUpdate(model.id, updates);
        onClose();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to update model'
        );
      } finally {
        setLoading(false);
      }
    } else {
      // Create mode: require connection test
      if (!connectionTested) {
        setError('Please test the connection before saving the model.');
        return;
      }

      // Validate required fields for create mode
      const isValid =
        provider &&
        name &&
        modelName &&
        apiKey &&
        (!requiresEndpoint || endpoint);

      if (isValid && onConnect) {
        setLoading(true);
        setError(null);
        try {
          const requestHeaders: Record<string, any> = {
            Authorization: `Bearer ${apiKey}`,
            'Content-Type': 'application/json',
            ...customHeaders,
          };

          const modelData: ModelCreate = {
            name,
            description: `${isCustomProvider ? providerName : provider!.description} Connection`,
            icon: provider!.type_value,
            model_name: modelName,
            key: apiKey,
            tags: [provider!.type_value],
            request_headers: requestHeaders,
            provider_type_id: provider!.id,
          };

          // Only include endpoint if it's required and has a value
          if (requiresEndpoint && endpoint && endpoint.trim()) {
            modelData.endpoint = endpoint.trim();
          }

          await onConnect(provider!.type_value, modelData);
          onClose();
        } catch (err) {
          setError(
            err instanceof Error ? err.message : 'Failed to connect to provider'
          );
        } finally {
          setLoading(false);
        }
      }
    }
  };

  // Determine icon and display name based on mode
  const providerIconKey = isEditMode && model
    ? model.icon || model.provider_type?.type_value || 'custom'
    : provider?.type_value || 'custom';
  
  const providerIcon = PROVIDER_ICONS[providerIconKey] || (
    <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.medium }} />
  );
  
  const displayName = isEditMode && model
    ? model.provider_type?.description || model.provider_type?.type_value || 'Provider'
    : isCustomProvider
    ? 'Custom Provider'
    : provider?.description || provider?.type_value || 'Provider';

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { borderRadius: theme => theme.shape.borderRadius * 0.5 },
      }}
    >
      <DialogTitle sx={{ pb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {providerIcon}
          <Box>
            <Typography variant="h6" component="div">
              {isEditMode ? `Edit ${displayName}` : `Connect to ${displayName}`}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {isEditMode 
                ? 'Update your connection settings'
                : 'Configure your connection settings below'}
            </Typography>
          </Box>
        </Box>
      </DialogTitle>

      <form onSubmit={handleSubmit}>
        <DialogContent sx={{ px: 3, py: 2 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          <Stack spacing={2}>
            {/* Basic Configuration */}
            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 600, mb: 1, color: 'primary.main' }}
            >
              Basic Configuration
            </Typography>

            {isCustomProvider && (
              <TextField
                label="Provider Name"
                fullWidth
                required
                value={providerName}
                onChange={e => setProviderName(e.target.value)}
                helperText="A descriptive name for your custom LLM provider or deployment"
              />
            )}

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="Connection Name"
                fullWidth
                variant="outlined"
                required
                value={name}
                onChange={e => setName(e.target.value)}
                helperText="A unique name to identify this connection"
              />

              <TextField
                label="Model Name"
                fullWidth
                required
                value={modelName}
                onChange={e => setModelName(e.target.value)}
                helperText={
                  isCustomProvider
                    ? 'The model identifier for your deployment'
                    : 'The specific model to use from this provider'
                }
              />
            </Stack>

            {/* Connection Details */}
            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 600, mb: 1, color: 'primary.main', mt: 1 }}
            >
              Connection Details
            </Typography>

            {/* Endpoint URL (for self-hosted/local providers) */}
            {requiresEndpoint && (
              <TextField
                label="API Endpoint"
                fullWidth
                required
                value={endpoint}
                onChange={e => setEndpoint(e.target.value)}
                placeholder={DEFAULT_ENDPOINTS[provider?.type_value || '']}
                helperText={
                  provider?.type_value === 'ollama'
                    ? 'The URL where Ollama is running (default: http://localhost:11434)'
                    : 'The base URL for your self-hosted model endpoint'
                }
              />
            )}

            {/* API Key with Test Connection Button */}
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
              <TextField
                label="API Key"
                fullWidth
                required={!isEditMode}
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                onFocus={e => {
                  // Clear placeholder when user clicks on field in edit mode
                  if (isEditMode && apiKey === '************') {
                    setApiKey('');
                  }
                }}
                onBlur={e => {
                  // Restore placeholder if field is empty in edit mode
                  if (isEditMode && !e.target.value) {
                    setApiKey('************');
                  }
                }}
                helperText={
                  isEditMode
                    ? apiKey !== '************' && apiKey !== ''
                      ? "New API key will replace the current one"
                      : 'Click to update the API key'
                    : isCustomProvider
                    ? 'Authentication key for your deployment (if required)'
                    : "Your API key from the provider's dashboard"
                }
                InputProps={{
                  endAdornment: isEditMode && apiKey && apiKey !== '************' ? (
                    <IconButton
                      size="small"
                      onClick={() => setShowApiKey(!showApiKey)}
                      edge="end"
                    >
                      <InfoOutlinedIcon fontSize="small" />
                    </IconButton>
                  ) : null,
                }}
              />
              {(!isEditMode || (isEditMode && apiKey !== '************')) && (
                <Button
                  onClick={handleTestConnection}
                  variant="outlined"
                  disabled={
                    !modelName ||
                    !apiKey ||
                    apiKey === '************' ||
                    (requiresEndpoint && !endpoint) ||
                    testingConnection ||
                    loading
                  }
                  startIcon={
                    testingConnection ? (
                      <CircularProgress size={16} />
                    ) : (
                      <CheckCircleIcon />
                    )
                  }
                  sx={{ 
                    minWidth: '120px',
                    height: '56px',
                    mt: 0,
                  }}
                >
                  {testingConnection ? 'Testing...' : 'Test'}
                </Button>
              )}
            </Box>

            {/* Test Connection Result */}
            {testResult && (
              <Alert
                severity={testResult.success ? 'success' : 'error'}
                sx={{ whiteSpace: 'pre-line' }}
                action={
                  !testResult.success && testResult.fullError ? (
                    <IconButton
                      size="small"
                      onClick={() => setShowFullError(!showFullError)}
                      sx={{ alignSelf: 'flex-start' }}
                    >
                      <InfoOutlinedIcon fontSize="small" />
                    </IconButton>
                  ) : null
                }
              >
                <Box>
                  {testResult.message}
                  {!testResult.success && testResult.fullError && showFullError && (
                    <Box
                      sx={{
                        mt: 2,
                        pt: 2,
                        borderTop: '1px solid',
                        borderColor: 'divider',
                      }}
                    >
                      <Typography variant="caption" sx={{ fontWeight: 600, display: 'block', mb: 1 }}>
                        Technical Details:
                      </Typography>
                      <Typography
                        variant="caption"
                        component="pre"
                        sx={{
                          fontSize: '0.7rem',
                          overflowX: 'auto',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {testResult.fullError}
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Alert>
            )}

            {/* Custom Headers */}
            <Stack spacing={1}>
              <Typography
                variant="subtitle1"
                sx={{ fontWeight: 600, color: 'primary.main', mt: 1 }}
              >
                Custom Headers (Optional)
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Add any additional HTTP headers required for your API calls.
                Authorization header is automatically included.
              </Typography>

              {/* Existing Headers */}
              {Object.entries(customHeaders).length > 0 && (
                <Stack spacing={1}>
                  {Object.entries(customHeaders).map(([key, value]) => (
                    <Paper
                      key={key}
                      variant="outlined"
                      sx={{
                        p: 2,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        bgcolor: 'grey.50',
                      }}
                    >
                      <Box sx={{ display: 'flex', gap: 2, flex: 1 }}>
                        <Typography
                          variant="body2"
                          sx={{ fontWeight: 500, minWidth: 120 }}
                        >
                          {key}:
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {value}
                        </Typography>
                      </Box>
                      <IconButton
                        size="small"
                        onClick={() => handleRemoveHeader(key)}
                        color="error"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Paper>
                  ))}
                </Stack>
              )}

              {/* Add New Header */}
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Stack
                  direction={{ xs: 'column', sm: 'row' }}
                  spacing={2}
                  alignItems="flex-end"
                >
                  <TextField
                    label="Header Name"
                    fullWidth
                    value={newHeaderKey}
                    onChange={e => setNewHeaderKey(e.target.value)}
                  />
                  <TextField
                    label="Header Value"
                    fullWidth
                    value={newHeaderValue}
                    onChange={e => setNewHeaderValue(e.target.value)}
                  />
                  <Button
                    variant="outlined"
                    onClick={handleAddHeader}
                    disabled={!newHeaderKey.trim() || !newHeaderValue.trim()}
                    sx={{ minWidth: { xs: '100%', sm: 'auto' } }}
                    startIcon={<AddIcon />}
                  >
                    Add
                  </Button>
                </Stack>
              </Paper>
            </Stack>
          </Stack>
        </DialogContent>

        <DialogActions
          sx={{ px: 3, py: 2, borderTop: '1px solid', borderColor: 'divider' }}
        >
          <Button onClick={onClose} disabled={loading} size="large">
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={
              !name ||
              !modelName ||
              (!isEditMode && isCustomProvider && !providerName) ||
              (!isEditMode && !apiKey) ||
              (requiresEndpoint && !endpoint) ||
              (!isEditMode && !connectionTested) ||
              (isEditMode && apiKey !== '************' && !connectionTested) || // Require test if key changed in edit mode
              loading
            }
            size="large"
            sx={{ minWidth: 120 }}
          >
            {loading ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={16} />
                {isEditMode ? 'Updating...' : 'Connecting...'}
              </Box>
            ) : (
              isEditMode ? 'Update' : 'Connect'
            )}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

export default function LLMProvidersPage() {
  const { data: session } = useSession();
  const [connectedModels, setConnectedModels] = useState<Model[]>([]);
  const [providerTypes, setProviderTypes] = useState<TypeLookup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<TypeLookup | null>(
    null
  );
  const [providerSelectionOpen, setProviderSelectionOpen] = useState(false);
  const [connectionDialogOpen, setConnectionDialogOpen] = useState(false);
  const [modelToEdit, setModelToEdit] = useState<Model | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [modelToDelete, setModelToDelete] = useState<Model | null>(null);

  useEffect(() => {
    async function loadData() {
      if (!session?.session_token) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const apiFactory = new ApiClientFactory(session.session_token);
        const modelsClient = apiFactory.getModelsClient();
        const typeLookupClient = apiFactory.getTypeLookupClient();

        // Load provider types first
        const types = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'ProviderType'",
          limit: 100, // Fetch all providers (default is 10)
        });
        console.log('Provider types loaded:', types);
        setProviderTypes(types);

        // Then load connected models
        try {
          const modelsResponse = await modelsClient.getModels();
          setConnectedModels(modelsResponse.data);
        } catch (err) {
          console.error('Failed to load models:', err);
        }
      } catch (err) {
        console.error('Failed to load providers:', err);
        setError(
          err instanceof Error ? err.message : 'Failed to load providers'
        );
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [session]);

  const handleAddLLM = () => {
    console.log('Opening provider selection with types:', providerTypes);
    setProviderSelectionOpen(true);
  };

  const handleProviderSelect = (provider: TypeLookup) => {
    setSelectedProvider(provider);
    setProviderSelectionOpen(false);
    setConnectionDialogOpen(true);
  };

  const handleConnect = async (providerId: string, modelData: ModelCreate) => {
    if (!session?.session_token) return;

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const modelsClient = apiFactory.getModelsClient();

      const model = await modelsClient.createModel(modelData);
      setConnectedModels(prev => [...prev, model]);
    } catch (err) {
      throw err;
    }
  };

  const handleEditClick = (model: Model, event: React.MouseEvent) => {
    event.stopPropagation();
    setModelToEdit(model);
    setSelectedProvider(model.provider_type || null);
    setConnectionDialogOpen(true);
  };

  const handleUpdate = async (modelId: UUID, updates: Partial<ModelCreate>) => {
    if (!session?.session_token) return;

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const modelsClient = apiFactory.getModelsClient();

      const updatedModel = await modelsClient.updateModel(modelId, updates);
      setConnectedModels(prev =>
        prev.map(model => (model.id === modelId ? updatedModel : model))
      );
    } catch (err) {
      throw err;
    }
  };

  const handleDeleteClick = (model: Model, event: React.MouseEvent) => {
    event.stopPropagation();
    setModelToDelete(model);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!session?.session_token || !modelToDelete) return;

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const modelsClient = apiFactory.getModelsClient();

      await modelsClient.deleteModel(modelToDelete.id);
      setConnectedModels(prev =>
        prev.filter(model => model.id !== modelToDelete.id)
      );
      setDeleteDialogOpen(false);
      setModelToDelete(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete model');
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ mb: 1 }}>
          Models
        </Typography>
        <Typography color="text.secondary">
          Connect to leading AI model providers to power your evaluation and
          testing workflows.
        </Typography>
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr', // 1 column on mobile
              sm: 'repeat(2, 1fr)', // 2 columns on small screens
              md: 'repeat(3, 1fr)', // 3 columns on medium screens
              lg: 'repeat(5, 1fr)', // 5 columns on large screens
              xl: 'repeat(6, 1fr)', // 6 columns on extra large screens
            },
            gap: 3,
            '& > *': {
              minHeight: '200px',
              display: 'flex',
            },
          }}
        >
          {connectedModels.map(model => (
            <Paper
              key={model.id}
              sx={{
                p: 3,
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
                minHeight: 'inherit', // Inherit the minimum height from parent
              }}
            >
              <Box
                sx={{
                  position: 'absolute',
                  top: theme => theme.spacing(1),
                  right: theme => theme.spacing(1),
                  display: 'flex',
                  gap: theme => theme.spacing(0.5),
                  zIndex: 1,
                }}
              >
                <IconButton
                  size="small"
                  onClick={e => handleEditClick(model, e)}
                  sx={{
                    padding: '2px',
                    '& .MuiSvgIcon-root': {
                      fontSize: theme => theme?.typography?.helperText?.fontSize || '0.75rem',
                      color: 'currentColor',
                    },
                  }}
                >
                  <EditIcon fontSize="inherit" />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={e => handleDeleteClick(model, e)}
                  sx={{
                    padding: '2px',
                    '& .MuiSvgIcon-root': {
                      fontSize: theme => theme?.typography?.helperText?.fontSize || '0.75rem',
                      color: 'currentColor',
                    },
                  }}
                >
                  <DeleteIcon fontSize="inherit" />
                </IconButton>
              </Box>

              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    color: 'text.secondary', // Subdued gray color like metrics
                  }}
                >
                  {PROVIDER_ICONS[model.icon || 'custom'] || (
                    <SmartToyIcon
                      sx={{ fontSize: theme => theme.iconSizes.large }}
                    />
                  )}
                  <CheckCircleIcon
                    sx={{
                      ml: -1,
                      mt: -2,
                      fontSize: 16,
                      color: 'success.main',
                    }}
                  />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="h6">{model.name}</Typography>
                  <Typography color="text.secondary" variant="body2">
                    {model.description}
                  </Typography>
                </Box>
              </Box>

              <Box sx={{ mt: 1, mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Model: {model.model_name}
                </Typography>
              </Box>

              <Box sx={{ mt: 'auto' }}>
                <Button
                  fullWidth
                  variant="contained"
                  color="success"
                  size="small"
                  disableElevation
                  disableRipple
                  sx={{
                    textTransform: 'none',
                    borderRadius: theme => theme.shape.borderRadius * 0.375,
                    pointerEvents: 'none',
                    cursor: 'default',
                  }}
                >
                  Connected
                </Button>
              </Box>
            </Paper>
          ))}

          {/* Add LLM Card */}
          <Paper
            sx={{
              p: 3,
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              bgcolor: 'action.hover',
              cursor: 'pointer',
              transition: 'all 0.2s',
              minHeight: 'inherit', // Inherit the minimum height from parent
              '&:hover': {
                bgcolor: 'action.selected',
                transform: 'translateY(-2px)',
              },
            }}
            onClick={handleAddLLM}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  color: 'text.secondary',
                }}
              >
                <AddIcon
                  sx={{
                    fontSize: theme => theme.iconSizes.large,
                  }}
                />
              </Box>
              <Box sx={{ flex: 1 }}>
                <Typography variant="h6" color="text.secondary">
                  Add Model
                </Typography>
                <Typography color="text.secondary" variant="body2">
                  Connect a new model
                </Typography>
              </Box>
            </Box>

            <Box sx={{ mt: 'auto' }}>
              <Button
                fullWidth
                variant="outlined"
                size="small"
                sx={{
                  textTransform: 'none',
                  borderRadius: theme => theme.shape.borderRadius * 0.375,
                }}
              >
                Add Model
              </Button>
            </Box>
          </Paper>
        </Box>
      )}

      <ProviderSelectionDialog
        open={providerSelectionOpen}
        onClose={() => setProviderSelectionOpen(false)}
        onSelectProvider={handleProviderSelect}
        providers={providerTypes}
      />

      <ConnectionDialog
        open={connectionDialogOpen}
        provider={selectedProvider}
        model={modelToEdit}
        mode={modelToEdit ? 'edit' : 'create'}
        onClose={() => {
          setConnectionDialogOpen(false);
          setSelectedProvider(null);
          setModelToEdit(null);
        }}
        onConnect={handleConnect}
        onUpdate={handleUpdate}
      />

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => {
          setDeleteDialogOpen(false);
          setModelToDelete(null);
        }}
        onConfirm={handleDeleteConfirm}
        itemType="model connection"
        itemName={modelToDelete?.name}
        title="Delete Model Connection"
      />
    </Box>
  );
}
