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
  Stack,
  Switch,
  FormControlLabel,
  Divider,
  Autocomplete,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import { DeleteIcon, AddIcon } from '@/components/icons';
import { useSession } from 'next-auth/react';
import { Model, ModelCreate } from '@/utils/api-client/interfaces/model';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import { UUID } from 'crypto';
import {
  PROVIDERS_REQUIRING_ENDPOINT,
  DEFAULT_ENDPOINTS,
  PROVIDER_ICONS,
  LOCAL_PROVIDERS,
} from '@/config/model-providers';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface ConnectionDialogProps {
  open: boolean;
  provider: TypeLookup | null;
  model?: Model | null; // For edit mode
  mode?: 'create' | 'edit';
  userSettings?: UserSettings | null; // Current user settings
  onClose: () => void;
  onConnect?: (providerId: string, modelData: ModelCreate) => Promise<Model>;
  onUpdate?: (modelId: UUID, updates: Partial<ModelCreate>) => Promise<void>;
  onUserSettingsUpdate?: () => Promise<void>; // Callback to refresh user settings
}

export function ConnectionDialog({
  open,
  provider,
  model,
  mode = 'create',
  userSettings,
  onClose,
  onConnect,
  onUpdate,
  onUserSettingsUpdate,
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
  const [defaultForGeneration, setDefaultForGeneration] = useState(false);
  const [defaultForEvaluation, setDefaultForEvaluation] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const isEditMode = mode === 'edit';
  const isCustomProvider = provider?.type_value === 'vllm';

  // Determine requiresEndpoint from either provider or model
  const requiresEndpoint =
    isEditMode && model?.provider_type
      ? PROVIDERS_REQUIRING_ENDPOINT.includes(model.provider_type.type_value)
      : provider
        ? PROVIDERS_REQUIRING_ENDPOINT.includes(provider.type_value)
        : false;

  // Determine if this is a local provider (doesn't require API key)
  const isLocalProvider =
    isEditMode && model?.provider_type
      ? LOCAL_PROVIDERS.includes(model.provider_type.type_value)
      : provider
        ? LOCAL_PROVIDERS.includes(provider.type_value)
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
        setCustomHeaders(
          (model.request_headers as Record<string, string>) || {}
        );
        setProviderName('');
        setError(null);
        setTestResult(null);
        setShowFullError(false);
        setConnectionTested(true); // Skip test requirement in edit mode
        setShowApiKey(false);
        setLoading(false); // Reset loading state

        // Check if this model is set as default in user settings
        const isDefaultGeneration =
          userSettings?.models?.generation?.model_id === model.id;
        const isDefaultEvaluation =
          userSettings?.models?.evaluation?.model_id === model.id;
        setDefaultForGeneration(isDefaultGeneration || false);
        setDefaultForEvaluation(isDefaultEvaluation || false);
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
        setDefaultForGeneration(false);
        setDefaultForEvaluation(false);
        setLoading(false); // Reset loading state
      }
    }
  }, [open, provider, model, isEditMode, userSettings]);

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

  // Fetch available models when provider is selected
  useEffect(() => {
    const fetchModels = async () => {
      const currentProvider =
        isEditMode && model?.provider_type ? model.provider_type : provider;
      if (!currentProvider || !session?.session_token) return;

      setLoadingModels(true);
      try {
        const apiFactory = new ApiClientFactory(session.session_token);
        const modelsClient = apiFactory.getModelsClient();
        const models = await modelsClient.getProviderModels(
          currentProvider.type_value
        );
        setAvailableModels(models);
      } catch (_err) {
        // Silently fail - user can still manually enter model name
        setAvailableModels([]);
      } finally {
        setLoadingModels(false);
      }
    };

    if (open) {
      fetchModels();
    }
  }, [open, provider, model, isEditMode, session]);

  // Helper function to update user settings for default models
  const updateUserSettingsDefaults = async (modelId: UUID) => {
    if (!session?.session_token) return;

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const usersClient = apiFactory.getUsersClient();
      const updates: any = {
        models: {},
      };

      // Update generation default if toggle is on
      if (defaultForGeneration) {
        updates.models.generation = { model_id: modelId };
      } else if (userSettings?.models?.generation?.model_id === modelId) {
        // If toggle is off and this model was previously the default, clear it by setting model_id to null
        updates.models.generation = { model_id: null };
      }

      // Update evaluation default if toggle is on
      if (defaultForEvaluation) {
        updates.models.evaluation = { model_id: modelId };
      } else if (userSettings?.models?.evaluation?.model_id === modelId) {
        // If toggle is off and this model was previously the default, clear it by setting model_id to null
        updates.models.evaluation = { model_id: null };
      }

      // Only update if there are changes
      if (Object.keys(updates.models).length > 0) {
        await usersClient.updateUserSettings(updates);
        // Refresh user settings in parent
        if (onUserSettingsUpdate) {
          await onUserSettingsUpdate();
        }
      }
    } catch (_err) {
      // Don't throw - we don't want to block model creation/update if settings fail
    }
  };

  const handleTestConnection = async () => {
    // Get provider from either new connection or existing model
    const currentProvider =
      isEditMode && model?.provider_type ? model.provider_type : provider;

    // For local providers, API key is optional
    const currentIsLocalProvider = currentProvider
      ? LOCAL_PROVIDERS.includes(currentProvider.type_value)
      : false;

    // In edit mode with existing model, we can use stored API key (model_id)
    const canUseStoredKey =
      isEditMode && model?.id && (!apiKey || apiKey === '************');
    const hasApiKey =
      apiKey && apiKey !== '************' && apiKey.trim().length > 0;

    if (
      !currentProvider ||
      !modelName ||
      (!currentIsLocalProvider && !hasApiKey && !canUseStoredKey)
    ) {
      setTestResult({
        success: false,
        message: currentIsLocalProvider
          ? 'Please fill in provider and model name'
          : canUseStoredKey
            ? 'Please fill in provider and model name'
            : 'Please fill in provider, model name, and API key',
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
      const apiFactory = new ApiClientFactory(session.session_token);
      const modelsClient = apiFactory.getModelsClient();

      const requestBody: any = {
        provider: currentProvider.type_value,
        model_name: modelName,
        api_key: hasApiKey ? apiKey : '',
      };

      if (canUseStoredKey && model?.id) {
        requestBody.model_id = model.id;
      }

      // Only include endpoint if it's required and has a value
      if (requiresEndpoint && endpoint && endpoint.trim()) {
        requestBody.endpoint = endpoint.trim();
      }

      const result = await modelsClient.testConnection(requestBody);

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
        if (
          lowerError.includes('api key') ||
          lowerError.includes('unauthorized')
        ) {
          friendlyMessage = 'Invalid API key. Please check your credentials.';
        } else if (
          lowerError.includes('not found') ||
          lowerError.includes('404')
        ) {
          friendlyMessage = `Model '${modelName}' not found for ${currentProvider.type_value}.`;
        } else if (
          lowerError.includes('quota') ||
          lowerError.includes('rate limit')
        ) {
          friendlyMessage = 'API quota exceeded or rate limit reached.';
        } else if (
          lowerError.includes('connection') ||
          lowerError.includes('timeout')
        ) {
          friendlyMessage =
            'Connection failed. Check endpoint URL and network.';
        }

        setTestResult({
          success: false,
          message: friendlyMessage,
          fullError: fullError,
        });
      }
    } catch (err) {
      const fullError =
        err instanceof Error ? err.message : 'Unknown error occurred';
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
        const updates: Partial<ModelCreate> = {};

        // For protected models, only send non-core fields (status, owner, assignee, tags)
        // For regular models, include all editable fields
        if (!model.is_protected) {
          updates.name = name;
          updates.model_name = modelName;

          // Only include endpoint if it's required and has a value
          if (requiresEndpoint && endpoint && endpoint.trim()) {
            updates.endpoint = endpoint.trim();
          }

          // Only include API key if it was changed (not the placeholder)
          if (apiKey && apiKey.trim() && apiKey !== '************') {
            updates.key = apiKey.trim();
          }

          // Always update custom headers to allow removal (Authorization and Content-Type are handled automatically)
          updates.request_headers = customHeaders;
        }

        await onUpdate(model.id, updates);
        // Update user settings for default models
        await updateUserSettingsDefaults(model.id);
        // Don't reset loading state - let dialog close with "Updating..." text
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update model');
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
        (isLocalProvider || apiKey) &&
        (!requiresEndpoint || endpoint);

      if (isValid && onConnect && provider) {
        setLoading(true);
        setError(null);
        try {
          const modelData: ModelCreate = {
            name,
            description: `${isCustomProvider ? providerName : provider.description} Connection`,
            icon: provider.type_value,
            model_name: modelName,
            key: apiKey || '', // Empty string for local providers without API key
            tags: [provider.type_value],
            // Only store custom headers (Authorization and Content-Type are handled automatically by SDK)
            request_headers: customHeaders,
            provider_type_id: provider.id,
          };

          // Only include endpoint if it's required and has a value
          if (requiresEndpoint && endpoint && endpoint.trim()) {
            modelData.endpoint = endpoint.trim();
          }

          const createdModel = await onConnect(provider.type_value, modelData);
          // Update user settings for default models
          await updateUserSettingsDefaults(createdModel.id);
          // Don't reset loading state - let dialog close with "Connecting..." text
          onClose();
        } catch (err) {
          setError(
            err instanceof Error ? err.message : 'Failed to connect to provider'
          );
          setLoading(false);
        }
      }
    }
  };

  // Determine icon and display name based on mode
  const providerIconKey =
    isEditMode && model
      ? model.icon || model.provider_type?.type_value || 'custom'
      : provider?.type_value || 'custom';

  const providerIcon = PROVIDER_ICONS[providerIconKey] || (
    <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.medium }} />
  );

  const displayName =
    isEditMode && model
      ? model.provider_type?.description ||
        model.provider_type?.type_value ||
        'Provider'
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
            {/* Basic Configuration - Hidden for protected models */}
            {!model?.is_protected && (
              <>
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

                  <Autocomplete
                    fullWidth
                    freeSolo
                    options={availableModels}
                    value={modelName}
                    onChange={(event, newValue) => setModelName(newValue || '')}
                    onInputChange={(event, newInputValue) =>
                      setModelName(newInputValue)
                    }
                    loading={loadingModels}
                    filterOptions={(options, { inputValue }) => {
                      if (!inputValue) return options;
                      const input = inputValue.toLowerCase();
                      return options.filter(option =>
                        option.toLowerCase().includes(input)
                      );
                    }}
                    renderInput={params => (
                      <TextField
                        {...params}
                        label="Model Name"
                        required
                        helperText={
                          isCustomProvider
                            ? 'The model identifier for your deployment'
                            : 'The specific model to use from this provider'
                        }
                        InputProps={{
                          ...params.InputProps,
                          endAdornment: (
                            <>
                              {loadingModels ? (
                                <CircularProgress size={20} />
                              ) : null}
                              {params.InputProps.endAdornment}
                            </>
                          ),
                        }}
                      />
                    )}
                  />
                </Stack>
              </>
            )}

            {/* Connection Details - Hidden for protected models */}
            {!model?.is_protected && (
              <>
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
                        ? 'The URL where Ollama is running (default: http://host.docker.internal:11434)'
                        : 'The base URL for your self-hosted model endpoint'
                    }
                  />
                )}

                {/* API Key with Test Connection Button (hidden for local providers) */}
                {!isLocalProvider && (
                  <Box
                    sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}
                  >
                    <TextField
                      label="API Key"
                      fullWidth
                      required={!isEditMode}
                      type={showApiKey ? 'text' : 'password'}
                      value={apiKey}
                      onChange={e => setApiKey(e.target.value)}
                      onFocus={_e => {
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
                            ? 'New API key will replace the current one'
                            : 'Click to update the API key'
                          : isCustomProvider
                            ? 'Authentication key for your deployment (if required)'
                            : "Your API key from the model provider's dashboard"
                      }
                      InputProps={{
                        endAdornment:
                          apiKey && apiKey !== '************' ? (
                            <IconButton
                              size="small"
                              onClick={() => setShowApiKey(!showApiKey)}
                              edge="end"
                              aria-label={
                                showApiKey ? 'Hide API key' : 'Show API key'
                              }
                            >
                              {showApiKey ? (
                                <VisibilityOffIcon fontSize="small" />
                              ) : (
                                <VisibilityIcon fontSize="small" />
                              )}
                            </IconButton>
                          ) : null,
                      }}
                    />
                    <Button
                      onClick={handleTestConnection}
                      variant="outlined"
                      disabled={
                        !modelName ||
                        ((!apiKey || apiKey === '************') &&
                          !(isEditMode && model?.id)) ||
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
                  </Box>
                )}

                {/* Test Connection Button for Local Providers (no API key needed) */}
                {isLocalProvider && (
                  <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <Button
                      onClick={handleTestConnection}
                      variant="outlined"
                      disabled={
                        !modelName ||
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
                      }}
                    >
                      {testingConnection ? 'Testing...' : 'Test Connection'}
                    </Button>
                  </Box>
                )}
              </>
            )}

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
                  {!testResult.success &&
                    testResult.fullError &&
                    showFullError && (
                      <Box
                        sx={{
                          mt: 2,
                          pt: 2,
                          borderTop: '1px solid',
                          borderColor: 'divider',
                        }}
                      >
                        <Typography
                          variant="caption"
                          sx={{ fontWeight: 600, display: 'block', mb: 1 }}
                        >
                          Technical Details:
                        </Typography>
                        <Typography
                          variant="caption"
                          component="pre"
                          sx={{
                            fontSize: theme =>
                              theme.typography.caption.fontSize,
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

            {/* Connection Test Required Message */}
            {!isEditMode && !connectionTested && !testResult && (
              <Alert severity="info" sx={{ mt: 2 }}>
                Please test the connection before saving the model
                configuration.
              </Alert>
            )}
            {isEditMode &&
              apiKey !== '************' &&
              !connectionTested &&
              !testResult && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  Please test the connection with the new API key before
                  updating.
                </Alert>
              )}

            {/* Custom Headers - Hidden for protected models */}
            {!model?.is_protected && (
              <Stack spacing={1}>
                <Typography
                  variant="subtitle1"
                  sx={{ fontWeight: 600, color: 'primary.main', mt: 1 }}
                >
                  Custom Headers (Optional)
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Add any additional HTTP headers required for your API calls.
                  Authorization and Content-Type headers are handled
                  automatically.
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
            )}

            {/* Default Model Settings */}
            <Box sx={{ mt: 3 }}>
              <Divider sx={{ mb: 2 }} />
              <Typography
                variant="subtitle1"
                sx={{ fontWeight: 600, mb: 2, color: 'primary.main' }}
              >
                Default Model Settings
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Set this model as the default for test generation or evaluation
                tasks.
              </Typography>
              <Stack spacing={1}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={defaultForGeneration}
                      onChange={e => setDefaultForGeneration(e.target.checked)}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        Default for Test Generation
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Use this model when generating new test cases
                      </Typography>
                    </Box>
                  }
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={defaultForEvaluation}
                      onChange={e => setDefaultForEvaluation(e.target.checked)}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        Default for Evaluation (LLM as Judge)
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Use this model when running metrics and evaluations
                      </Typography>
                    </Box>
                  }
                />
              </Stack>
            </Box>
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
              (!isEditMode && !isLocalProvider && !apiKey) ||
              (requiresEndpoint && !endpoint) ||
              (!isEditMode && !connectionTested) ||
              (isEditMode &&
                !isLocalProvider &&
                apiKey !== '************' &&
                !connectionTested) || // Require test if key changed in edit mode (but not for local providers)
              loading
            }
            size="large"
            sx={{
              minWidth: 120,
              '&.Mui-disabled': {
                backgroundColor: 'action.disabledBackground',
                color: 'action.disabled',
              },
            }}
          >
            {loading ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={16} />
                {isEditMode ? 'Updating...' : 'Connecting...'}
              </Box>
            ) : isEditMode ? (
              'Update'
            ) : (
              'Connect'
            )}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
