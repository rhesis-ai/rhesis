'use client';

import React, {
  useState,
  useEffect,
  useImperativeHandle,
  forwardRef,
} from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  IconButton,
  CircularProgress,
  Alert,
  Switch,
  Autocomplete,
} from '@mui/material';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import { drawerOutlinedFieldSx } from '@/components/common/drawerFormFieldSx';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import { useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { writeUserSettingsCache } from '@/hooks/useUserSettings';
import {
  Model,
  ModelCreate,
  type TestModelConnectionRequest,
} from '@/utils/api-client/interfaces/model';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import { UUID } from 'crypto';
import {
  PROVIDERS_REQUIRING_ENDPOINT,
  DEFAULT_ENDPOINTS,
  LOCAL_PROVIDERS,
  PROVIDERS_WITH_OPTIONAL_API_KEY,
  providerSupportsModelListing,
} from '@/config/model-providers';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

export interface ConnectionFormHandle {
  submit: () => void;
}

interface ConnectionFormProps {
  open: boolean;
  provider: TypeLookup | null;
  model?: Model | null;
  mode?: 'create' | 'edit';
  modelType?: 'language' | 'embedding';
  userSettings?: UserSettings | null;
  onClose: () => void;
  onConnect?: (providerId: string, modelData: ModelCreate) => Promise<Model>;
  onUpdate?: (modelId: UUID, updates: Partial<ModelCreate>) => Promise<void>;
  onUserSettingsUpdate?: () => Promise<void>;
  onLoadingChange?: (loading: boolean) => void;
  onCanSaveChange?: (canSave: boolean) => void;
}

export const ConnectionForm = forwardRef<
  ConnectionFormHandle,
  ConnectionFormProps
>(function ConnectionForm(
  {
    open,
    provider,
    model,
    mode = 'create',
    modelType: initialModelType = 'language',
    userSettings,
    onClose,
    onConnect,
    onUpdate,
    onUserSettingsUpdate,
    onLoadingChange,
    onCanSaveChange,
  },
  ref
) {
  const [name, setName] = useState('');
  const [providerName, setProviderName] = useState('');
  const [modelName, setModelName] = useState('');
  const [modelType, setModelType] = useState<'language' | 'embedding'>(
    'language'
  );
  const [endpoint, setEndpoint] = useState('');
  const [apiKey, setApiKey] = useState('');
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
  const [defaultForExecution, setDefaultForExecution] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  const isEditMode = mode === 'edit';
  const isCustomProvider = provider?.type_value === 'vllm';

  const requiresEndpoint =
    isEditMode && model?.provider_type
      ? PROVIDERS_REQUIRING_ENDPOINT.includes(model.provider_type.type_value)
      : provider
        ? PROVIDERS_REQUIRING_ENDPOINT.includes(provider.type_value)
        : false;

  const isLocalProvider =
    isEditMode && model?.provider_type
      ? LOCAL_PROVIDERS.includes(model.provider_type.type_value)
      : provider
        ? LOCAL_PROVIDERS.includes(provider.type_value)
        : false;

  const hasOptionalApiKey =
    isEditMode && model?.provider_type
      ? PROVIDERS_WITH_OPTIONAL_API_KEY.includes(model.provider_type.type_value)
      : provider
        ? PROVIDERS_WITH_OPTIONAL_API_KEY.includes(provider.type_value)
        : false;

  // Compute whether Save should be enabled and notify parent
  useEffect(() => {
    const canSave = isEditMode
      ? !!(name || model?.name) &&
        !!(modelName || model?.model_name) &&
        (!isLocalProvider &&
        !hasOptionalApiKey &&
        apiKey !== '************' &&
        apiKey !== ''
          ? connectionTested
          : true)
      : !!(
          name &&
          modelName &&
          (isLocalProvider || hasOptionalApiKey || apiKey) &&
          (!requiresEndpoint || endpoint) &&
          (!isCustomProvider || providerName) &&
          connectionTested
        );
    onCanSaveChange?.(canSave);
  }, [
    isEditMode,
    name,
    modelName,
    apiKey,
    endpoint,
    connectionTested,
    isLocalProvider,
    hasOptionalApiKey,
    isCustomProvider,
    providerName,
    requiresEndpoint,
    model,
    onCanSaveChange,
  ]);

  // Notify parent of loading state
  useEffect(() => {
    onLoadingChange?.(loading);
  }, [loading, onLoadingChange]);

  // Reset form when drawer opens
  useEffect(() => {
    if (open) {
      if (isEditMode && model) {
        setName(model.name || '');
        setModelName(model.model_name || '');
        setModelType(model.model_type || 'language');
        setEndpoint(model.endpoint || '');
        setApiKey('************');
        setProviderName('');
        setError(null);
        setTestResult(null);
        setShowFullError(false);
        setConnectionTested(true);
        setShowApiKey(false);
        setLoading(false);

        const isDefaultGeneration =
          userSettings?.models?.generation?.model_id === model.id;
        const isDefaultEvaluation =
          userSettings?.models?.evaluation?.model_id === model.id;
        const isDefaultExecution =
          userSettings?.models?.execution?.model_id === model.id;
        setDefaultForGeneration(isDefaultGeneration || false);
        setDefaultForEvaluation(isDefaultEvaluation || false);
        setDefaultForExecution(isDefaultExecution || false);
      } else if (provider) {
        setName('');
        setProviderName('');
        setModelName('');
        setModelType(initialModelType);
        setEndpoint(
          PROVIDERS_REQUIRING_ENDPOINT.includes(provider.type_value)
            ? DEFAULT_ENDPOINTS[provider.type_value] || ''
            : ''
        );
        setApiKey('');
        setError(null);
        setTestResult(null);
        setShowFullError(false);
        setConnectionTested(false);
        setShowApiKey(false);
        setDefaultForGeneration(false);
        setDefaultForEvaluation(false);
        setDefaultForExecution(false);
        setLoading(false);
      }
    }
  }, [open, provider, model, isEditMode, userSettings, initialModelType]);

  // Reset connection test when critical fields change
  useEffect(() => {
    if (!isEditMode) {
      setConnectionTested(false);
      setTestResult(null);
    } else if (apiKey && apiKey !== '************') {
      setConnectionTested(false);
      setTestResult(null);
    }
  }, [modelName, apiKey, endpoint, isEditMode]);

  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const userScope = session?.user?.id ?? session?.session_token ?? '';

  // Fetch available models for the provider
  useEffect(() => {
    const fetchModels = async () => {
      const currentProvider =
        isEditMode && model?.provider_type ? model.provider_type : provider;
      if (!currentProvider || !session?.session_token) return;

      if (
        !providerSupportsModelListing(currentProvider.type_value, modelType)
      ) {
        setAvailableModels([]);
        setLoadingModels(false);
        return;
      }

      setLoadingModels(true);
      try {
        const apiFactory = new ApiClientFactory(session.session_token);
        const modelsClient = apiFactory.getModelsClient();

        let models: string[];
        if (modelType === 'embedding') {
          models = await modelsClient.getProviderEmbeddingModels(
            currentProvider.type_value
          );
        } else {
          models = await modelsClient.getProviderModels(
            currentProvider.type_value
          );
        }
        setAvailableModels(models);
      } catch (_err) {
        setAvailableModels([]);
      } finally {
        setLoadingModels(false);
      }
    };

    if (open) {
      fetchModels();
    }
  }, [open, provider, model, isEditMode, session, modelType]);

  const updateUserSettingsDefaults = async (modelId: UUID) => {
    if (!session?.session_token) return;

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const usersClient = apiFactory.getUsersClient();
      const updates: { models: Record<string, { model_id: string | null }> } = {
        models: {},
      };

      if (defaultForGeneration) {
        updates.models.generation = { model_id: modelId };
      } else if (userSettings?.models?.generation?.model_id === modelId) {
        updates.models.generation = { model_id: null };
      }

      if (defaultForEvaluation) {
        updates.models.evaluation = { model_id: modelId };
      } else if (userSettings?.models?.evaluation?.model_id === modelId) {
        updates.models.evaluation = { model_id: null };
      }

      if (defaultForExecution) {
        updates.models.execution = { model_id: modelId };
      } else if (userSettings?.models?.execution?.model_id === modelId) {
        updates.models.execution = { model_id: null };
      }

      if (Object.keys(updates.models).length > 0) {
        const updated = await usersClient.updateUserSettings(updates);
        writeUserSettingsCache(queryClient, userScope, updated);
        if (onUserSettingsUpdate) {
          await onUserSettingsUpdate();
        }
      }
    } catch (_err) {
      // Don't block model creation/update if settings fail
    }
  };

  const handleTestConnection = async () => {
    const currentProvider =
      isEditMode && model?.provider_type ? model.provider_type : provider;

    const currentIsLocalProvider = currentProvider
      ? LOCAL_PROVIDERS.includes(currentProvider.type_value)
      : false;

    const canUseStoredKey =
      isEditMode && model?.id && (!apiKey || apiKey === '************');
    const hasApiKey =
      apiKey && apiKey !== '************' && apiKey.trim().length > 0;

    const currentHasOptionalApiKey = currentProvider
      ? PROVIDERS_WITH_OPTIONAL_API_KEY.includes(currentProvider.type_value)
      : false;

    if (
      !currentProvider ||
      !modelName ||
      (!currentIsLocalProvider &&
        !currentHasOptionalApiKey &&
        !hasApiKey &&
        !canUseStoredKey)
    ) {
      setTestResult({
        success: false,
        message:
          currentIsLocalProvider || currentHasOptionalApiKey
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

      const requestBody: TestModelConnectionRequest = {
        provider: currentProvider.type_value,
        model_name: modelName,
        api_key: apiKey && apiKey !== '************' ? apiKey : '',
        model_type: modelType,
      };

      if (canUseStoredKey && model?.id) {
        requestBody.model_id = model.id;
      }

      if (requiresEndpoint && endpoint && endpoint.trim()) {
        requestBody.endpoint = endpoint.trim();
      }

      const result = await modelsClient.testConnection(requestBody);

      if (result.success) {
        setTestResult({ success: true, message: result.message });
        setConnectionTested(true);
      } else {
        const fullError = result.message;
        let friendlyMessage = 'Connection test failed';

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

        setTestResult({ success: false, message: friendlyMessage, fullError });
      }
    } catch (err) {
      const fullError =
        err instanceof Error ? err.message : 'Unknown error occurred';
      setTestResult({
        success: false,
        message: 'Failed to test connection. Please try again.',
        fullError,
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSubmit = async () => {
    if (isEditMode && model && onUpdate) {
      setLoading(true);
      setError(null);
      try {
        const updates: Partial<ModelCreate> = {};

        if (!model.is_protected) {
          updates.name = name;
          updates.model_name = modelName;

          if (requiresEndpoint && endpoint && endpoint.trim()) {
            updates.endpoint = endpoint.trim();
          }

          if (apiKey && apiKey.trim() && apiKey !== '************') {
            updates.key = apiKey.trim();
          }
        }

        await onUpdate(model.id, updates);
        await updateUserSettingsDefaults(model.id);
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update model');
        setLoading(false);
      }
    } else {
      if (!connectionTested) {
        setError('Please test the connection before saving the model.');
        return;
      }

      const isValid =
        provider &&
        name &&
        modelName &&
        (isLocalProvider || hasOptionalApiKey || apiKey) &&
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
            model_type: modelType,
            key: apiKey || '',
            tags: [provider.type_value],
            provider_type_id: provider.id,
          };

          if (requiresEndpoint && endpoint && endpoint.trim()) {
            modelData.endpoint = endpoint.trim();
          }

          const createdModel = await onConnect(provider.type_value, modelData);
          await updateUserSettingsDefaults(createdModel.id);
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

  useImperativeHandle(ref, () => ({ submit: handleSubmit }));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
      {error && <Alert severity="error">{error}</Alert>}

      {/* Basic Configuration */}
      {!model?.is_protected && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
          <FormSectionDivider headline="Basic Configuration" />

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
            {isCustomProvider && (
              <TextField
                label="Provider Name"
                fullWidth
                required
                value={providerName}
                onChange={e => setProviderName(e.target.value)}
                helperText="A descriptive name for your custom LLM provider or deployment"
                sx={drawerOutlinedFieldSx}
              />
            )}

            <TextField
              label="Connection Name"
              fullWidth
              required
              value={name}
              onChange={e => setName(e.target.value)}
              helperText="A unique name to identify this connection"
              sx={drawerOutlinedFieldSx}
            />

            <Autocomplete
              fullWidth
              freeSolo
              options={availableModels}
              value={modelName}
              onChange={(_event, newValue) => setModelName(newValue || '')}
              onInputChange={(_event, newInputValue) =>
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
                  sx={drawerOutlinedFieldSx}
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {loadingModels ? <CircularProgress size={20} /> : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
            />
          </Box>
        </Box>
      )}

      {/* Connection Details */}
      {!model?.is_protected && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
          <FormSectionDivider headline="Connection Details" />

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
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
                    ? 'When Rhesis runs in Docker, use host.docker.internal instead of localhost to reach Ollama on your machine'
                    : provider?.type_value === 'litellm_proxy'
                      ? 'When Rhesis runs in Docker, use host.docker.internal instead of localhost to reach LiteLLM on your machine'
                      : provider?.type_value === 'azure_ai'
                        ? 'Your Azure AI inference endpoint URL (e.g. https://your-deployment.inference.ai.azure.com/)'
                        : provider?.type_value === 'azure'
                          ? 'Your Azure OpenAI endpoint URL (e.g. https://your-resource.openai.azure.com/)'
                          : 'The base URL for your self-hosted model endpoint'
                }
                sx={drawerOutlinedFieldSx}
              />
            )}

            {!isLocalProvider && (
              <Box
                sx={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}
              >
                <TextField
                  label={hasOptionalApiKey ? 'API Key (optional)' : 'API Key'}
                  fullWidth
                  required={!isEditMode && !hasOptionalApiKey}
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  onFocus={() => {
                    if (isEditMode && apiKey === '************') setApiKey('');
                  }}
                  onBlur={e => {
                    if (isEditMode && !e.target.value)
                      setApiKey('************');
                  }}
                  helperText={
                    isEditMode
                      ? apiKey !== '************' && apiKey !== ''
                        ? 'New API key will replace the current one'
                        : 'Click to update the API key'
                      : hasOptionalApiKey
                        ? 'Optional authentication key for the proxy server'
                        : isCustomProvider
                          ? 'Authentication key for your deployment (if required)'
                          : "Your API key from the model provider's dashboard"
                  }
                  sx={drawerOutlinedFieldSx}
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
                    (!hasOptionalApiKey &&
                      (!apiKey || apiKey === '************') &&
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
                  sx={{ minWidth: 120, height: 56, flexShrink: 0 }}
                >
                  {testingConnection ? 'Testing...' : 'Test'}
                </Button>
              </Box>
            )}

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
                  sx={{ minWidth: 160, height: 56 }}
                >
                  {testingConnection ? 'Testing...' : 'Test Connection'}
                </Button>
              </Box>
            )}

            {/* Test result */}
            {testResult && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '12px',
                  px: '30px',
                  py: '12px',
                  borderRadius: '4px',
                  backgroundColor: testResult.success ? '#d0f5ec' : '#fadbde',
                  color: testResult.success ? '#0080af' : '#de3355',
                }}
              >
                {testResult.success ? (
                  <CheckCircleOutlineIcon
                    sx={{ fontSize: 22, mt: '7px', flexShrink: 0 }}
                  />
                ) : (
                  <ErrorOutlineIcon
                    sx={{ fontSize: 22, mt: '7px', flexShrink: 0 }}
                  />
                )}
                <Box sx={{ flex: 1, py: '8px' }}>
                  <Typography
                    sx={{
                      fontSize: 18,
                      fontWeight: 700,
                      lineHeight: '25px',
                      color: 'inherit',
                    }}
                  >
                    {testResult.success
                      ? 'Connection successful'
                      : 'Connection failed'}
                  </Typography>
                  <Typography
                    sx={{
                      fontSize: 16,
                      lineHeight: '24px',
                      color: 'inherit',
                      whiteSpace: 'pre-line',
                    }}
                  >
                    {testResult.message}
                  </Typography>
                  {!testResult.success &&
                    testResult.fullError &&
                    showFullError && (
                      <Box
                        sx={{
                          mt: 2,
                          pt: 2,
                          borderTop: '1px solid',
                          borderColor: 'currentColor',
                          opacity: 0.6,
                        }}
                      >
                        <Typography
                          sx={{
                            fontSize: 12,
                            fontWeight: 600,
                            lineHeight: '18px',
                            display: 'block',
                            mb: 1,
                            color: 'inherit',
                          }}
                        >
                          Technical Details:
                        </Typography>
                        <Typography
                          component="pre"
                          sx={{
                            fontSize: 12,
                            lineHeight: '18px',
                            color: 'inherit',
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
                {!testResult.success && testResult.fullError && (
                  <IconButton
                    size="small"
                    onClick={() => setShowFullError(!showFullError)}
                    sx={{ color: 'inherit', mt: '4px', flexShrink: 0 }}
                    aria-label="Show technical details"
                  >
                    <InfoOutlinedIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
            )}

            {/* Connection test required notices */}
            {!isEditMode && !connectionTested && !testResult && (
              <Alert severity="info">
                Please test the connection before saving the model
                configuration.
              </Alert>
            )}
            {isEditMode &&
              apiKey !== '************' &&
              !connectionTested &&
              !testResult && (
                <Alert severity="info">
                  Please test the connection with the new API key before
                  updating.
                </Alert>
              )}
          </Box>
        </Box>
      )}

      {/* Default Model Settings */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
        <FormSectionDivider headline="Default Model Settings" />

        <Box sx={{ display: 'flex', flexDirection: 'column' }}>
          {modelType === 'language' && (
            <>
              {[
                {
                  label: 'Default for Test Generation',
                  checked: defaultForGeneration,
                  onChange: setDefaultForGeneration,
                },
                {
                  label: 'Default for Evaluation (LLM as Judge)',
                  checked: defaultForEvaluation,
                  onChange: setDefaultForEvaluation,
                },
                {
                  label: 'Default for Execution (Multi-Turn)',
                  checked: defaultForExecution,
                  onChange: setDefaultForExecution,
                },
              ].map(({ label, checked, onChange }) => (
                <Box
                  key={label}
                  sx={{
                    borderTop: 1,
                    borderColor: theme => theme.palette.greyscale.border,
                    pt: '20px',
                    pb: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <Typography
                    sx={{
                      fontSize: 16,
                      lineHeight: '24px',
                      color: theme => theme.palette.greyscale.title,
                    }}
                  >
                    {label}
                  </Typography>
                  <Switch
                    checked={checked}
                    onChange={e => onChange(e.target.checked)}
                    size="small"
                  />
                </Box>
              ))}
            </>
          )}
          {modelType === 'embedding' && (
            <Box
              sx={{
                borderTop: 1,
                borderColor: theme => theme.palette.greyscale.border,
                pt: '20px',
              }}
            >
              <Typography
                sx={{
                  fontSize: 14,
                  lineHeight: '22px',
                  color: theme => theme.palette.greyscale.subtitle,
                }}
              >
                The default embedding model is managed by the platform and
                cannot be changed here. Connect embedding models so the platform
                can use them where needed.
              </Typography>
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
});
