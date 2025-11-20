'use client';

import React, { useState, useEffect } from 'react';
import {
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  Alert,
  IconButton,
  InputAdornment,
} from '@mui/material';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import BaseDrawer from '@/components/common/BaseDrawer';
import {
  Tool,
  ToolCreate,
  ToolUpdate,
} from '@/utils/api-client/interfaces/tool';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { UUID } from 'crypto';

interface ToolConfigurationDrawerProps {
  open: boolean;
  onClose: () => void;
  tool?: Tool | null;
  toolTypes: TypeLookup[];
  providerTypes: TypeLookup[];
  sessionToken: string;
  onSave: (toolData: ToolCreate | ToolUpdate) => Promise<void>;
}

export default function ToolConfigurationDrawer({
  open,
  onClose,
  tool,
  toolTypes,
  providerTypes,
  sessionToken,
  onSave,
}: ToolConfigurationDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAuthToken, setShowAuthToken] = useState(false);

  // Form state
  const [toolTypeId, setToolTypeId] = useState<UUID | ''>('');
  const [providerTypeId, setProviderTypeId] = useState<UUID | ''>('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [authToken, setAuthToken] = useState('');

  // Initialize form with tool data or defaults
  useEffect(() => {
    if (tool) {
      setName(tool.name);
      setDescription(tool.description || '');
      setToolTypeId(tool.tool_type_id);
      setProviderTypeId(tool.tool_provider_type_id);
      // Don't set auth token for existing tools (it's encrypted and not returned)
      setAuthToken('');
    } else {
      // Default to MCP tool type
      const mcpType = toolTypes.find(t => t.type_value === 'mcp');
      if (mcpType) {
        setToolTypeId(mcpType.id);
      }
      setName('');
      setDescription('');
      setProviderTypeId('');
      setAuthToken('');
    }
  }, [tool, toolTypes]);

  const handleSave = async () => {
    setError(null);

    // Validation
    if (!name.trim()) {
      setError('Tool name is required');
      return;
    }
    if (!toolTypeId) {
      setError('Tool type is required');
      return;
    }
    if (!providerTypeId) {
      setError('Provider is required');
      return;
    }
    if (!tool && !authToken.trim()) {
      setError('Auth token is required');
      return;
    }

    try {
      setLoading(true);
      if (tool) {
        // Update existing tool
        const updateData: ToolUpdate = {
          name: name.trim(),
          description: description.trim() || undefined,
          tool_type_id: toolTypeId as UUID,
          tool_provider_type_id: providerTypeId as UUID,
        };
        // Only include auth_token if it was changed
        if (authToken.trim()) {
          updateData.auth_token = authToken.trim();
        }
        await onSave(updateData);
      } else {
        // Create new tool
        const createData: ToolCreate = {
          name: name.trim(),
          description: description.trim() || undefined,
          tool_type_id: toolTypeId as UUID,
          tool_provider_type_id: providerTypeId as UUID,
          auth_token: authToken.trim(),
        };
        await onSave(createData);
      }
      onClose();
      // Reset form
      setName('');
      setDescription('');
      setAuthToken('');
      setProviderTypeId('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save tool');
    } finally {
      setLoading(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={tool ? 'Edit Tool' : 'Add Tool'}
      loading={loading}
      error={error || undefined}
      onSave={handleSave}
      saveButtonText={tool ? 'Update' : 'Create'}
    >
      <Stack spacing={3}>
        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <FormControl fullWidth required>
          <InputLabel>Tool Type</InputLabel>
          <Select
            value={toolTypeId}
            label="Tool Type"
            onChange={e => setToolTypeId(e.target.value as UUID)}
            disabled={loading}
          >
            {toolTypes.map(type => (
              <MenuItem key={type.id} value={type.id}>
                {type.type_value.toUpperCase()}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl fullWidth required>
          <InputLabel>Provider</InputLabel>
          <Select
            value={providerTypeId}
            label="Provider"
            onChange={e => setProviderTypeId(e.target.value as UUID)}
            disabled={loading}
          >
            {providerTypes.map(provider => (
              <MenuItem key={provider.id} value={provider.id}>
                {provider.type_value.charAt(0).toUpperCase() +
                  provider.type_value.slice(1)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <TextField
          label="Tool Name"
          value={name}
          onChange={e => setName(e.target.value)}
          required
          fullWidth
          disabled={loading}
          placeholder="e.g., My Notion Workspace"
        />

        <TextField
          label="Description"
          value={description}
          onChange={e => setDescription(e.target.value)}
          fullWidth
          multiline
          rows={2}
          disabled={loading}
          placeholder="Optional description"
        />

        <TextField
          label="Auth Token"
          type={showAuthToken ? 'text' : 'password'}
          value={authToken}
          onChange={e => setAuthToken(e.target.value)}
          required={!tool}
          fullWidth
          disabled={loading}
          placeholder={
            tool
              ? 'Leave empty to keep current token'
              : 'Enter authentication token'
          }
          helperText={
            tool
              ? 'Leave empty to keep the current token'
              : 'This token will be encrypted and stored securely'
          }
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  onClick={() => setShowAuthToken(!showAuthToken)}
                  edge="end"
                  disabled={loading}
                >
                  {showAuthToken ? <VisibilityOff /> : <Visibility />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
      </Stack>
    </BaseDrawer>
  );
}
