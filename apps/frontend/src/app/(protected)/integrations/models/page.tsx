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
import { DeleteIcon, AddIcon, CloudIcon } from '@/components/icons';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Model, ModelCreate } from '@/utils/api-client/interfaces/model';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { DeleteModal } from '@/components/common/DeleteModal';
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
  onClose: () => void;
  onConnect: (providerId: string, modelData: ModelCreate) => Promise<void>;
}

function ConnectionDialog({
  open,
  provider,
  onClose,
  onConnect,
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
  } | null>(null);

  const isCustomProvider = provider?.type_value === 'vllm';
  const requiresEndpoint = provider
    ? PROVIDERS_REQUIRING_ENDPOINT.includes(provider.type_value)
    : false;

  // Reset form when dialog opens with new provider
  useEffect(() => {
    if (provider) {
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
    }
  }, [provider]);

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

  const handleTestConnection = async () => {
    if (!provider || !modelName || !apiKey) {
      setTestResult({
        success: false,
        message: 'Please fill in provider, model name, and API key',
      });
      return;
    }

    setTestingConnection(true);
    setTestResult(null);
    setError(null);

    try {
      const session = useSession();
      if (!session?.data?.session_token) {
        throw new Error('No session token available');
      }

      const apiFactory = new ApiClientFactory(session.data.session_token);
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'}/models/test-connection`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session.data.session_token}`,
          },
          body: JSON.stringify({
            provider: provider.type_value,
            model_name: modelName,
            api_key: apiKey,
            ...(requiresEndpoint && endpoint ? { endpoint } : {}),
          }),
        }
      );

      const result = await response.json();

      setTestResult({
        success: result.success,
        message: result.message,
      });
    } catch (err) {
      setTestResult({
        success: false,
        message:
          err instanceof Error
            ? err.message
            : 'Failed to test connection. Please try again.',
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Validate required fields
    const isValid =
      provider &&
      name &&
      modelName &&
      apiKey &&
      (!requiresEndpoint || endpoint); // Endpoint required for certain providers

    if (isValid) {
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
          description: `${isCustomProvider ? providerName : provider.description} Connection`,
          icon: provider.type_value,
          model_name: modelName,
          key: apiKey,
          tags: [provider.type_value],
          request_headers: requestHeaders,
          ...(requiresEndpoint && endpoint ? { endpoint } : {}), // Include endpoint if required
        };
        await onConnect(provider.type_value, modelData);
        onClose();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to connect to provider'
        );
      } finally {
        setLoading(false);
      }
    }
  };

  const providerIcon = PROVIDER_ICONS[provider?.type_value || ''] || (
    <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.medium }} />
  );
  const displayName = isCustomProvider
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
              Connect to {displayName}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Configure your connection settings below
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

            <TextField
              label="API Key"
              fullWidth
              required
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              helperText={
                isCustomProvider
                  ? 'Authentication key for your deployment (if required)'
                  : "Your API key from the provider's dashboard"
              }
            />

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
              (isCustomProvider && !providerName) ||
              !apiKey ||
              (requiresEndpoint && !endpoint) ||
              loading
            }
            size="large"
            sx={{ minWidth: 120 }}
          >
            {loading ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={16} />
                Connecting...
              </Box>
            ) : (
              'Connect'
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
              md: 'repeat(4, 1fr)', // 4 columns on medium screens
              lg: 'repeat(4, 1fr)', // 4 columns on large screens
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
              <IconButton
                size="small"
                onClick={e => handleDeleteClick(model, e)}
                sx={{
                  position: 'absolute',
                  top: 8,
                  right: 8,
                  color: 'error.main',
                  '&:hover': {
                    backgroundColor: 'error.light',
                    color: 'error.main',
                  },
                }}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>

              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
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
                <Typography variant="body2" color="text.secondary">
                  API Key: •••••{model.key.slice(-4)}
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
              <AddIcon
                sx={{
                  fontSize: theme => theme.iconSizes.large,
                  color: 'grey.500',
                }}
              />
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
        onClose={() => {
          setConnectionDialogOpen(false);
          setSelectedProvider(null);
        }}
        onConnect={handleConnect}
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
