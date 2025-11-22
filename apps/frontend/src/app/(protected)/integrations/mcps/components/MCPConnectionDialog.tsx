import React, { useState, useEffect } from 'react';
import {
  Box,
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
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import {
  Tool,
  ToolCreate,
  ToolUpdate,
} from '@/utils/api-client/interfaces/tool';
import { UUID } from 'crypto';
import { MCP_PROVIDER_ICONS } from '@/config/mcp-providers';

interface MCPConnectionDialogProps {
  open: boolean;
  provider: TypeLookup | null;
  mcpToolType: TypeLookup | null; // MCP tool type (always 'mcp')
  tool?: Tool | null; // For edit mode
  mode?: 'create' | 'edit';
  onClose: () => void;
  onConnect?: (providerId: string, toolData: ToolCreate) => Promise<Tool>;
  onUpdate?: (toolId: UUID, updates: Partial<ToolUpdate>) => Promise<void>;
}

export function MCPConnectionDialog({
  open,
  provider,
  mcpToolType,
  tool,
  mode = 'create',
  onClose,
  onConnect,
  onUpdate,
}: MCPConnectionDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [authToken, setAuthToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAuthToken, setShowAuthToken] = useState(false);

  const isEditMode = mode === 'edit';

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      if (isEditMode && tool) {
        // Edit mode: populate with existing tool data
        setName(tool.name || '');
        setDescription(tool.description || '');
        setAuthToken('************'); // Show placeholder for existing token
        setError(null);
        setShowAuthToken(false);
        setLoading(false);
      } else if (provider) {
        // Create mode: reset to defaults
        setName('');
        setDescription('');
        setAuthToken('');
        setError(null);
        setShowAuthToken(false);
        setLoading(false);
      }
    }
  }, [open, provider, tool, isEditMode]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (isEditMode && tool && onUpdate) {
      // Edit mode: update existing tool
      setLoading(true);
      setError(null);
      try {
        const updates: Partial<ToolUpdate> = {
          name,
          description: description || undefined,
        };

        // Only include auth token if it was changed (not the placeholder)
        if (authToken && authToken.trim() && authToken !== '************') {
          updates.auth_token = authToken.trim();
        }

        await onUpdate(tool.id, updates);
        // Don't reset loading state - let dialog close with "Updating..." text
        onClose();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to update MCP connection'
        );
        setLoading(false);
      }
    } else {
      // Create mode: validate required fields
      if (!provider || !name || !authToken) {
        setError('Please fill in all required fields.');
        return;
      }

      if (onConnect) {
        setLoading(true);
        setError(null);
        try {
          if (!mcpToolType || !provider) {
            setError('MCP tool type or provider not found. Please try again.');
            setLoading(false);
            return;
          }

          const toolData: ToolCreate = {
            name,
            description: description || undefined,
            tool_type_id: mcpToolType.id, // MCP tool type ID
            tool_provider_type_id: provider.id, // Provider type ID
            auth_token: authToken.trim(),
          };

          await onConnect(provider.type_value, toolData);
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

  // Determine icon and display name
  const providerIconKey = provider?.type_value || 'custom';
  const providerIcon = MCP_PROVIDER_ICONS[providerIconKey] || (
    <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.medium }} />
  );

  const displayName =
    provider?.description || provider?.type_value || 'MCP Provider';

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
                ? 'Update your MCP connection settings'
                : 'Configure your MCP connection settings below'}
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
            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 600, mb: 1, color: 'primary.main' }}
            >
              Basic Configuration
            </Typography>

            <TextField
              label="Connection Name"
              fullWidth
              variant="outlined"
              required
              value={name}
              onChange={e => setName(e.target.value)}
              helperText="A unique name to identify this MCP connection"
            />

            <TextField
              label="Description"
              fullWidth
              multiline
              rows={2}
              value={description}
              onChange={e => setDescription(e.target.value)}
              helperText="Optional description for this MCP connection"
            />

            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 600, mb: 1, color: 'primary.main', mt: 1 }}
            >
              Authentication
            </Typography>

            <TextField
              label="Auth Token"
              fullWidth
              required={!isEditMode}
              type={showAuthToken ? 'text' : 'password'}
              value={authToken}
              onChange={e => setAuthToken(e.target.value)}
              onFocus={e => {
                // Clear placeholder when user clicks on field in edit mode
                if (isEditMode && authToken === '************') {
                  setAuthToken('');
                }
              }}
              onBlur={e => {
                // Restore placeholder if field is empty in edit mode
                if (isEditMode && !e.target.value) {
                  setAuthToken('************');
                }
              }}
              helperText={
                isEditMode
                  ? authToken !== '************' && authToken !== ''
                    ? 'New auth token will replace the current one'
                    : 'Click to update the auth token'
                  : 'Your authentication token for this MCP provider'
              }
              InputProps={{
                endAdornment:
                  authToken && authToken !== '************' ? (
                    <IconButton
                      size="small"
                      onClick={() => setShowAuthToken(!showAuthToken)}
                      edge="end"
                      aria-label={
                        showAuthToken ? 'Hide auth token' : 'Show auth token'
                      }
                    >
                      {showAuthToken ? (
                        <VisibilityOffIcon fontSize="small" />
                      ) : (
                        <VisibilityIcon fontSize="small" />
                      )}
                    </IconButton>
                  ) : null,
              }}
            />
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
              (!isEditMode && !authToken) ||
              (isEditMode && authToken === '************' && !description) ||
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
