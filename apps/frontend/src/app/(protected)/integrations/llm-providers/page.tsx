'use client';

import React, { useState, useEffect } from "react";
import { Box, Paper, Typography, Button, Grid, Dialog, DialogTitle, DialogContent, DialogActions, TextField, IconButton, CircularProgress, Alert, List, ListItem, ListItemIcon, ListItemText, ListItemButton, Stack } from '@mui/material';
import { 
  SiOpenai,
  SiGoogle,
  SiAmazon,
  SiHuggingface,
  SiOllama,
  SiReplicate,
} from "@icons-pack/react-simple-icons";
import AnthropicIcon from '@mui/icons-material/Psychology';
import CohereLogo from '@mui/icons-material/AutoFixHigh';
import MistralIcon from '@mui/icons-material/AcUnit';
import CloudIcon from '@mui/icons-material/Cloud';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Model, ModelCreate } from '@/utils/api-client/interfaces/model';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';

interface ProviderInfo {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
}

const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  'anthropic': <AnthropicIcon sx={{ fontSize: 32 }} />,
  'cohere': <CohereLogo sx={{ fontSize: 32 }} />,
  'google': <SiGoogle className="h-8 w-8" />,
  'groq': <SmartToyIcon sx={{ fontSize: 32 }} />,
  'huggingface': <SiHuggingface className="h-8 w-8" />,
  'meta': <SmartToyIcon sx={{ fontSize: 32 }} />,
  'mistral': <MistralIcon sx={{ fontSize: 32 }} />,
  'ollama': <SiOllama className="h-8 w-8" />,
  'openai': <SiOpenai className="h-8 w-8" />,
  'perplexity': <SmartToyIcon sx={{ fontSize: 32 }} />,
  'replicate': <SiReplicate className="h-8 w-8" />,
  'together': <SmartToyIcon sx={{ fontSize: 32 }} />,
  'vllm': <SmartToyIcon sx={{ fontSize: 32 }} />
};

interface ProviderSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelectProvider: (provider: TypeLookup) => void;
  providers: TypeLookup[];
}

interface DeleteConfirmationDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  modelName: string;
}

function DeleteConfirmationDialog({ open, onClose, onConfirm, modelName }: DeleteConfirmationDialogProps) {
  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Delete Model Connection</DialogTitle>
      <DialogContent>
        <Typography>
          Are you sure you want to delete the connection to {modelName}? This action cannot be undone.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={onConfirm} color="error">
          Delete
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function ProviderSelectionDialog({ open, onClose, onSelectProvider, providers }: ProviderSelectionDialogProps) {
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

  // Sort providers alphabetically by type_value
  const sortedProviders = [...providers].sort((a, b) => 
    a.type_value.localeCompare(b.type_value)
  );

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Select LLM Provider</DialogTitle>
      <DialogContent>
        <List>
          {sortedProviders.map((provider) => {
            const providerInfo: ProviderInfo = {
              id: provider.type_value,
              name: provider.description || provider.type_value,
              description: provider.description || '',
              icon: PROVIDER_ICONS[provider.type_value] || <SmartToyIcon sx={{ fontSize: 32 }} />
            };
            
            return (
              <ListItemButton 
                key={provider.id}
                onClick={() => onSelectProvider(provider)}
                sx={{ 
                  borderRadius: 1,
                  my: 0.5,
                  '&:hover': {
                    backgroundColor: 'action.hover'
                  }
                }}
              >
                <ListItemIcon>
                  {providerInfo.icon}
                </ListItemIcon>
                <ListItemText 
                  primary={providerInfo.name}
                  secondary={providerInfo.description}
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

function ConnectionDialog({ open, provider, onClose, onConnect }: ConnectionDialogProps) {
  const [name, setName] = useState('');
  const [providerName, setProviderName] = useState('');
  const [modelName, setModelName] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [customHeaders, setCustomHeaders] = useState<Record<string, string>>({});
  const [newHeaderKey, setNewHeaderKey] = useState('');
  const [newHeaderValue, setNewHeaderValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isCustomProvider = provider?.type_value === 'vllm';

  // Reset form when dialog opens with new provider
  useEffect(() => {
    if (provider) {
      setName('');
      setProviderName('');
      setModelName('');
      setEndpoint('');
      setApiKey('');
      setCustomHeaders({});
      setNewHeaderKey('');
      setNewHeaderValue('');
      setError(null);
    }
  }, [provider]);

  const handleAddHeader = () => {
    if (newHeaderKey.trim() && newHeaderValue.trim()) {
      setCustomHeaders(prev => ({
        ...prev,
        [newHeaderKey.trim()]: newHeaderValue.trim()
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (provider && name && modelName && endpoint && apiKey) {
      setLoading(true);
      setError(null);
      try {
        const requestHeaders: Record<string, any> = {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
          ...customHeaders
        };

        const modelData: ModelCreate = {
          name,
          description: `${isCustomProvider ? providerName : provider.description} Connection`,
          icon: provider.type_value,
          model_name: modelName,
          endpoint,
          key: apiKey,
          tags: [provider.type_value],
          request_headers: requestHeaders
        };
        await onConnect(provider.type_value, modelData);
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect to provider');
      } finally {
        setLoading(false);
      }
    }
  };

  const providerIcon = PROVIDER_ICONS[provider?.type_value || ''] || <SmartToyIcon sx={{ fontSize: 24 }} />;
  const displayName = isCustomProvider ? 'Custom Provider' : (provider?.description || provider?.type_value || 'Provider');

  return (
    <Dialog 
      open={open} 
      onClose={onClose} 
      maxWidth="md" 
      fullWidth
      PaperProps={{
        sx: { borderRadius: 2 }
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

          <Grid container spacing={3}>
            {/* Basic Configuration */}
            <Grid item xs={12}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'primary.main' }}>
                Basic Configuration
              </Typography>
            </Grid>

            {isCustomProvider && (
              <Grid item xs={12}>
                <TextField
                  label="Provider Name"
                  fullWidth
                  required
                  value={providerName}
                  onChange={(e) => setProviderName(e.target.value)}
                  helperText="A descriptive name for your custom LLM provider or deployment"
                />
              </Grid>
            )}

            <Grid item xs={12} sm={6}>
              <TextField
                label="Connection Name"
                fullWidth
                variant="outlined"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                helperText="A unique name to identify this connection"
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                label="Model Name"
                fullWidth
                required
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                helperText={
                  isCustomProvider 
                    ? "The model identifier for your deployment"
                    : "The specific model to use from this provider"
                }
              />
            </Grid>

            {/* Connection Details */}
            <Grid item xs={12}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'primary.main', mt: 2 }}>
                Connection Details
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <TextField
                label="API Endpoint"
                fullWidth
                required
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                helperText={
                  isCustomProvider
                    ? "The full URL of your model's API endpoint"
                    : "The API endpoint URL provided by your LLM provider"
                }
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                label="API Key"
                fullWidth
                required
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                helperText={
                  isCustomProvider
                    ? "Authentication key for your deployment (if required)"
                    : "Your API key from the provider's dashboard"
                }
              />
            </Grid>

            {/* Custom Headers */}
            <Grid item xs={12}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'primary.main', mt: 2 }}>
                Custom Headers (Optional)
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Add any additional HTTP headers required for your API calls. Authorization header is automatically included.
              </Typography>

              {/* Existing Headers */}
              {Object.entries(customHeaders).length > 0 && (
                <Box sx={{ mb: 2 }}>
                  {Object.entries(customHeaders).map(([key, value]) => (
                    <Paper 
                      key={key} 
                      variant="outlined" 
                      sx={{ 
                        p: 2, 
                        mb: 1, 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'space-between',
                        bgcolor: 'grey.50'
                      }}
                    >
                      <Box sx={{ display: 'flex', gap: 2, flex: 1 }}>
                        <Typography variant="body2" sx={{ fontWeight: 500, minWidth: 120 }}>
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
                </Box>
              )}

              {/* Add New Header */}
              <Paper variant="outlined" sx={{ p: 2 }}>
                <Grid container spacing={2} alignItems="flex-end">
                  <Grid item xs={12} sm={5}>
                    <TextField
                      label="Header Name"
                      fullWidth
                      value={newHeaderKey}
                      onChange={(e) => setNewHeaderKey(e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={5}>
                    <TextField
                      label="Header Value"
                      fullWidth
                      value={newHeaderValue}
                      onChange={(e) => setNewHeaderValue(e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={2}>
                    <Button
                      variant="outlined"
                      onClick={handleAddHeader}
                      disabled={!newHeaderKey.trim() || !newHeaderValue.trim()}
                      fullWidth
                      startIcon={<AddIcon />}
                    >
                      Add
                    </Button>
                  </Grid>
                </Grid>
              </Paper>
            </Grid>
          </Grid>
        </DialogContent>

        <DialogActions sx={{ px: 3, py: 2, borderTop: '1px solid', borderColor: 'divider' }}>
          <Button 
            onClick={onClose} 
            disabled={loading}
            size="large"
          >
            Cancel
          </Button>
          <Button 
            type="submit" 
            variant="contained" 
            disabled={!name || (!isCustomProvider && !modelName) || (isCustomProvider && !providerName) || !endpoint || !apiKey || loading}
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
  const [selectedProvider, setSelectedProvider] = useState<TypeLookup | null>(null);
  const [providerSelectionOpen, setProviderSelectionOpen] = useState(false);
  const [connectionDialogOpen, setConnectionDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [modelToDelete, setModelToDelete] = useState<Model | null>(null);

  useEffect(() => {
    async function loadData() {
      if (!session?.session_token) return;

      try {
        setLoading(true);
        const apiFactory = new ApiClientFactory(session.session_token);
        const modelsClient = apiFactory.getModelsClient();
        const typeLookupClient = apiFactory.getTypeLookupClient();
        
        // Load provider types first
        const types = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'ProviderType'"
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
        setError(err instanceof Error ? err.message : 'Failed to load providers');
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
      setConnectedModels(prev => prev.filter(model => model.id !== modelToDelete.id));
      setDeleteDialogOpen(false);
      setModelToDelete(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete model');
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ mb: 1 }}>LLM Providers</Typography>
        <Typography color="text.secondary">
          Connect to leading AI providers to power your evaluation and testing workflows.
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
        <Grid container spacing={3}>
          {connectedModels.map((model) => (
            <Grid item xs={12} md={6} lg={2.4} key={model.id}>
              <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
                <IconButton 
                  size="small" 
                  onClick={(e) => handleDeleteClick(model, e)}
                  sx={{ 
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    color: 'error.main',
                    '&:hover': {
                      backgroundColor: 'error.light',
                      color: 'error.main',
                    }
                  }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
                
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {PROVIDER_ICONS[model.icon || 'custom'] || <SmartToyIcon sx={{ fontSize: 32 }} />}
                    <CheckCircleIcon 
                      sx={{ 
                        ml: -1, 
                        mt: -2, 
                        fontSize: 16, 
                        color: 'success.main' 
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
                      borderRadius: 1.5,
                      pointerEvents: 'none',
                      cursor: 'default'
                    }}
                  >
                    Connected
                  </Button>
                </Box>
              </Paper>
            </Grid>
          ))}

          {/* Add LLM Card */}
          <Grid item xs={12} md={6} lg={2.4}>
            <Paper 
              sx={{ 
                p: 3, 
                height: '100%', 
                display: 'flex', 
                flexDirection: 'column',
                bgcolor: 'grey.50',
                cursor: 'pointer',
                transition: 'all 0.2s',
                '&:hover': {
                  bgcolor: 'grey.100',
                  transform: 'translateY(-2px)'
                }
              }}
              onClick={handleAddLLM}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <AddIcon sx={{ fontSize: 32, color: 'grey.500' }} />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="h6" color="text.secondary">Add LLM</Typography>
                  <Typography color="text.secondary" variant="body2">
                    Connect to a new LLM provider
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
                    borderRadius: 1.5
                  }}
                >
                  Add Provider
                </Button>
              </Box>
            </Paper>
          </Grid>
        </Grid>
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

      <DeleteConfirmationDialog
        open={deleteDialogOpen}
        onClose={() => {
          setDeleteDialogOpen(false);
          setModelToDelete(null);
        }}
        onConfirm={handleDeleteConfirm}
        modelName={modelToDelete?.name || ''}
      />
    </Box>
  );
} 