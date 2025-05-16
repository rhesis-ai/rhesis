'use client';

import React, { useState, useEffect } from "react";
import { Box, Paper, Typography, Button, Grid, Dialog, DialogTitle, DialogContent, DialogActions, TextField, IconButton, CircularProgress, Alert } from '@mui/material';
import { 
  SiOpenai,
  SiGoogle,
  SiAmazon,
  SiHuggingface
} from "@icons-pack/react-simple-icons";
import AnthropicIcon from '@mui/icons-material/Psychology';
import CohereLogo from '@mui/icons-material/AutoFixHigh';
import MistralIcon from '@mui/icons-material/AcUnit';
import CloudIcon from '@mui/icons-material/Cloud';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Model, ModelCreate } from '@/utils/api-client/interfaces/model';
import { PaginatedResponse } from '@/utils/api-client/interfaces/pagination';

interface LLMProvider {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  isConnected: boolean;
  models: string[];
  endpoint?: string;
  connectionName?: string;
  apiKey?: string;
}

interface ConnectionDialogProps {
  open: boolean;
  provider: LLMProvider | null;
  onClose: () => void;
  onConnect: (providerId: string, modelData: ModelCreate) => Promise<void>;
}

interface DisconnectDialogProps {
  open: boolean;
  provider: LLMProvider | null;
  onClose: () => void;
  onConfirm: () => void;
}

function ConnectionDialog({ open, provider, onClose, onConnect }: ConnectionDialogProps) {
  const [name, setName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (provider && name && apiKey) {
      setLoading(true);
      setError(null);
      try {
        const modelData: ModelCreate = {
          name,
          description: `${provider.name} Connection`,
          icon: provider.id,
          model_name: provider.models[0], // Default to first available model
          endpoint: provider.endpoint || `https://api.${provider.id}.com/v1`,
          key: apiKey,
          tags: [provider.id],
          request_headers: {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
          }
        };
        await onConnect(provider.id, modelData);
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect to provider');
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Connect to {provider?.name}</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            <TextField
              label="Connection Name"
              fullWidth
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Production OpenAI"
            />
            <TextField
              label="API Key"
              fullWidth
              required
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your API key"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={loading}>Cancel</Button>
          <Button 
            type="submit" 
            variant="contained" 
            disabled={!name || !apiKey || loading}
            startIcon={loading ? <CircularProgress size={20} /> : null}
          >
            {loading ? 'Connecting...' : 'Connect'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function DisconnectDialog({ open, provider, onClose, onConfirm }: DisconnectDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Disconnect {provider?.name}</DialogTitle>
      <DialogContent>
        <Typography>
          Are you sure you want to disconnect from {provider?.name}? This will remove the API key and all connection settings.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={onConfirm} color="error" variant="contained">
          Disconnect
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function LLMProvidersPage() {
  const { data: session } = useSession();
  const [providers, setProviders] = useState<LLMProvider[]>([
    {
      id: 'openai',
      name: 'OpenAI',
      description: 'Access GPT-4, GPT-3.5, and other state-of-the-art language models.',
      icon: <SiOpenai className="h-8 w-8" />,
      isConnected: false,
      models: ['GPT-4', 'GPT-3.5-Turbo'],
      endpoint: 'https://api.openai.com/v1/chat/completions'
    },
    {
      id: 'anthropic',
      name: 'Anthropic',
      description: 'Use Claude and other advanced AI models for natural language tasks.',
      icon: <AnthropicIcon sx={{ fontSize: 32 }} />,
      isConnected: false,
      models: ['Claude-3', 'Claude-2.1']
    },
    {
      id: 'google',
      name: 'Google AI',
      description: 'Integrate with Gemini and PaLM models for diverse AI capabilities.',
      icon: <SiGoogle className="h-8 w-8" />,
      isConnected: false,
      models: ['Gemini Pro', 'Gemini Ultra']
    },
    {
      id: 'azure',
      name: 'Azure OpenAI',
      description: 'Enterprise-ready OpenAI models with Azure security and compliance.',
      icon: <CloudIcon sx={{ fontSize: 32 }} />,
      isConnected: false,
      models: ['GPT-4', 'GPT-3.5-Turbo']
    },
    {
      id: 'cohere',
      name: 'Cohere',
      description: 'Specialized models for text generation, classification, and embeddings.',
      icon: <CohereLogo sx={{ fontSize: 32 }} />,
      isConnected: false,
      models: ['Command', 'Embed']
    },
    {
      id: 'mistral',
      name: 'Mistral AI',
      description: 'High-performance open models with enterprise capabilities.',
      icon: <MistralIcon sx={{ fontSize: 32 }} />,
      isConnected: false,
      models: ['Mistral-Large', 'Mistral-Medium']
    },
    {
      id: 'aws',
      name: 'Amazon Bedrock',
      description: 'Access multiple foundation models through AWS infrastructure.',
      icon: <SiAmazon className="h-8 w-8" />,
      isConnected: false,
      models: ['Claude-3', 'Llama-2']
    },
    {
      id: 'huggingface',
      name: 'Hugging Face',
      description: 'Access thousands of open-source models and deploy them at scale.',
      icon: <SiHuggingface className="h-8 w-8" />,
      isConnected: false,
      models: ['Open Models', 'Inference API']
    },
    {
      id: 'custom',
      name: 'Custom LLM',
      description: 'Connect to your own LLM deployment or other AI providers.',
      icon: <AddIcon sx={{ fontSize: 32 }} />,
      isConnected: false,
      models: ['Any custom model']
    }
  ]);

  const [selectedProvider, setSelectedProvider] = useState<LLMProvider | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [disconnectDialogOpen, setDisconnectDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleConnect = (providerId: string) => {
    const provider = providers.find(p => p.id === providerId);
    if (provider) {
      if (provider.isConnected) {
        setSelectedProvider(provider);
        setDisconnectDialogOpen(true);
      } else {
        setSelectedProvider(provider);
        setDialogOpen(true);
      }
    }
  };

  const handleDisconnect = async () => {
    if (!session?.session_token || !selectedProvider) return;

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const modelsClient = apiFactory.getModelsClient();
      
      // Find and delete the model associated with this provider
      const response = await modelsClient.getModels({
        provider_type: selectedProvider.id
      });
      
      if (response.data.length > 0) {
        await modelsClient.deleteModel(response.data[0].id);
      }

      setProviders(prev => prev.map(p => 
        p.id === selectedProvider.id 
          ? { ...p, isConnected: false, connectionName: undefined, apiKey: undefined }
          : p
      ));
      
      setDisconnectDialogOpen(false);
      setSelectedProvider(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect provider');
    }
  };

  const handleProviderConnect = async (providerId: string, modelData: ModelCreate) => {
    if (!session?.session_token) return;

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const modelsClient = apiFactory.getModelsClient();
      
      const model = await modelsClient.createModel(modelData);
      
      setProviders(prev => prev.map(p => 
        p.id === providerId 
          ? { 
              ...p, 
              isConnected: true, 
              connectionName: model.name,
              apiKey: model.key 
            }
          : p
      ));
    } catch (err) {
      throw err;
    }
  };

  // Load existing connections on mount
  useEffect(() => {
    async function loadConnections() {
      if (!session?.session_token) return;

      try {
        setLoading(true);
        const apiFactory = new ApiClientFactory(session.session_token);
        const modelsClient = apiFactory.getModelsClient();
        
        const response = await modelsClient.getModels();
        
        // Update providers with existing connections
        setProviders(prev => prev.map(provider => {
          const existingModel = response.data.find((model: Model) => 
            model.tags.includes(provider.id)
          );
          
          return existingModel 
            ? {
                ...provider,
                isConnected: true,
                connectionName: existingModel.name,
                apiKey: existingModel.key
              }
            : provider;
        }));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load providers');
      } finally {
        setLoading(false);
      }
    }

    loadConnections();
  }, [session]);

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
          {providers.map((provider) => (
            <Grid item xs={12} md={6} lg={4} key={provider.id}>
              <Paper 
                sx={{ 
                  p: 3, 
                  height: '100%', 
                  display: 'flex', 
                  flexDirection: 'column',
                  ...(provider.id === 'custom' && {
                    bgcolor: 'grey.50',
                    borderColor: 'grey.300'
                  })
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                  <Box sx={{ 
                    color: provider.id === 'custom' ? 'grey.500' : 'inherit',
                    display: 'flex',
                    alignItems: 'center'
                  }}>
                    {provider.icon}
                    {provider.isConnected && (
                      <CheckCircleIcon 
                        sx={{ 
                          ml: -1, 
                          mt: -2, 
                          fontSize: 16, 
                          color: 'success.main' 
                        }} 
                      />
                    )}
                  </Box>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="h6" color={provider.id === 'custom' ? 'text.secondary' : 'inherit'}>
                      {provider.name}
                    </Typography>
                    <Typography color="text.secondary" variant="body2">
                      {provider.description}
                    </Typography>
                  </Box>
                </Box>
                
                {provider.isConnected && (
                  <Box sx={{ mt: 1, mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Connected as: {provider.connectionName}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      API Key: •••••{provider.apiKey?.slice(-4)}
                    </Typography>
                  </Box>
                )}

                {!provider.isConnected && (
                  <Box sx={{ mt: 2, mb: 2 }}>
                    <Typography variant="caption" color="text.secondary">
                      Available Models:
                    </Typography>
                    <Typography variant="body2" color={provider.id === 'custom' ? 'text.secondary' : 'inherit'}>
                      {provider.models.join(', ')}
                    </Typography>
                  </Box>
                )}

                <Box sx={{ mt: 'auto' }}>
                  <Button
                    fullWidth
                    variant={provider.isConnected ? "contained" : "outlined"}
                    color={provider.isConnected ? "success" : "primary"}
                    size="small"
                    onClick={() => handleConnect(provider.id)}
                    sx={{ 
                      textTransform: 'none',
                      borderRadius: 1.5
                    }}
                  >
                    {provider.isConnected ? "Connected" : (provider.id === 'custom' ? "Add Custom LLM" : "Connect")}
                  </Button>
                </Box>
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}

      <ConnectionDialog 
        open={dialogOpen}
        provider={selectedProvider}
        onClose={() => {
          setDialogOpen(false);
          setSelectedProvider(null);
        }}
        onConnect={handleProviderConnect}
      />

      <DisconnectDialog
        open={disconnectDialogOpen}
        provider={selectedProvider}
        onClose={() => {
          setDisconnectDialogOpen(false);
          setSelectedProvider(null);
        }}
        onConfirm={handleDisconnect}
      />
    </Box>
  );
} 