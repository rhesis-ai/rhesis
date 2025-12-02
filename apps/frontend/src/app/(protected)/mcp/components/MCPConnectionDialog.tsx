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
  Collapse,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import dynamic from 'next/dynamic';
import { useTheme } from '@mui/material/styles';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import {
  Tool,
  ToolCreate,
  ToolUpdate,
} from '@/utils/api-client/interfaces/tool';
import { UUID } from 'crypto';
import { MCP_PROVIDER_ICONS } from '@/config/mcp-providers';

// Lazy load Monaco Editor
const Editor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => (
    <Box
      sx={{
        height: '300px',
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

/**
 * Get the credential key name for a given provider
 */
function getCredentialKey(providerType: string | undefined): string {
  switch (providerType) {
    case 'notion':
      return 'NOTION_TOKEN';
    case 'github':
      return 'GITHUB_PERSONAL_ACCESS_TOKEN';
    case 'atlassian':
      // Atlassian doesn't require credentials in the template, but we'll use a generic key
      return 'ATLASSIAN_TOKEN';
    case 'custom':
      return 'TOKEN';
    default:
      return 'TOKEN';
  }
}

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
  const theme = useTheme();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [authToken, setAuthToken] = useState('');
  const [toolMetadata, setToolMetadata] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [showAdvancedConfig, setShowAdvancedConfig] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);

  const isEditMode = mode === 'edit';

  // Check if provider requires authentication token
  const providerType =
    provider?.type_value || tool?.tool_provider_type?.type_value;
  const requiresToken = providerType !== 'atlassian';
  const isCustomProvider = providerType === 'custom';

  // Determine editor theme based on MUI theme
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';

  // Theme-aware editor wrapper style (function to be reactive to jsonError)
  const getEditorWrapperStyle = () => ({
    border: 1,
    borderColor: jsonError ? 'error.main' : 'divider',
    borderRadius: theme.shape.borderRadius,
    '&:hover': {
      borderColor: jsonError ? 'error.main' : 'text.primary',
    },
    '&:focus-within': {
      borderWidth: 2,
      borderColor: jsonError ? 'error.main' : 'primary.main',
      margin: '-1px',
    },
  });

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      const currentProviderType =
        provider?.type_value || tool?.tool_provider_type?.type_value;
      const currentRequiresToken = currentProviderType !== 'atlassian';

      if (isEditMode && tool) {
        // Edit mode: populate with existing tool data
        setName(tool.name || '');
        setDescription(tool.description || '');
        // Only show placeholder if provider requires token
        setAuthToken(currentRequiresToken ? '************' : '');
        setToolMetadata(
          tool.tool_metadata ? JSON.stringify(tool.tool_metadata, null, 2) : ''
        );
        setError(null);
        setJsonError(null);
        setShowAuthToken(false);
        setLoading(false);
        setShowAdvancedConfig(!!tool.tool_metadata);
      } else if (provider) {
        // Create mode: reset to defaults
        setName('');
        setDescription('');
        setAuthToken('');
        setToolMetadata('');
        setError(null);
        setJsonError(null);
        setShowAuthToken(false);
        setLoading(false);
        setShowAdvancedConfig(isCustomProvider);
      }
    }
  }, [open, provider, tool, isEditMode, isCustomProvider]);

  const validateToolMetadata = (
    jsonString: string
  ): Record<string, any> | null => {
    if (!jsonString.trim()) {
      return null; // Empty is valid (optional field)
    }
    try {
      const parsed = JSON.parse(jsonString);
      if (typeof parsed !== 'object' || Array.isArray(parsed)) {
        setJsonError('Tool metadata must be a JSON object');
        return null;
      }
      setJsonError(null);
      return parsed;
    } catch (err) {
      setJsonError(
        err instanceof Error
          ? `Invalid JSON: ${err.message}`
          : 'Invalid JSON format'
      );
      return null;
    }
  };

  const handleToolMetadataChange = (value: string | undefined) => {
    setToolMetadata(value || '');
    if (value && value.trim()) {
      validateToolMetadata(value);
    } else {
      setJsonError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate tool_metadata for custom providers
    if (isCustomProvider && toolMetadata.trim()) {
      const validatedMetadata = validateToolMetadata(toolMetadata);
      if (validatedMetadata === null && toolMetadata.trim()) {
        setError('Please fix the JSON configuration errors before submitting.');
        return;
      }
    }

    if (isEditMode && tool && onUpdate) {
      // Edit mode: update existing tool
      setLoading(true);
      setError(null);
      try {
        const updates: Partial<ToolUpdate> = {
          name,
          description: description || undefined,
        };

        // Only include credentials if token was changed (not the placeholder) and provider requires token
        if (
          requiresToken &&
          authToken &&
          authToken.trim() &&
          authToken !== '************'
        ) {
          // Get provider type from provider or fall back to tool's provider type
          const providerType =
            provider?.type_value || tool.tool_provider_type?.type_value;
          const credentialKey = getCredentialKey(providerType);
          updates.credentials = {
            [credentialKey]: authToken.trim(),
          };
        }

        // Include tool_metadata if it was provided
        if (toolMetadata.trim()) {
          const validatedMetadata = validateToolMetadata(toolMetadata);
          if (validatedMetadata !== null) {
            updates.tool_metadata = validatedMetadata;
          }
        } else if (isCustomProvider) {
          // For custom providers, tool_metadata is required
          setError('Tool metadata is required for custom providers.');
          setLoading(false);
          return;
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
      if (!provider || !name || (requiresToken && !authToken)) {
        setError('Please fill in all required fields.');
        return;
      }

      // For custom providers, tool_metadata is required
      if (isCustomProvider && !toolMetadata.trim()) {
        setError('Tool metadata is required for custom providers.');
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

          // For Atlassian, credentials can be empty since it doesn't require a token
          const credentials = requiresToken
            ? {
                [getCredentialKey(provider.type_value)]: authToken.trim(),
              }
            : {};

          // Parse and validate tool_metadata for custom providers
          let parsedMetadata: Record<string, any> | undefined = undefined;
          if (isCustomProvider && toolMetadata.trim()) {
            const validatedMetadata = validateToolMetadata(toolMetadata);
            if (validatedMetadata === null) {
              setError(
                'Please fix the JSON configuration errors before submitting.'
              );
              setLoading(false);
              return;
            }
            parsedMetadata = validatedMetadata;
          }

          const toolData: ToolCreate = {
            name,
            description: description || undefined,
            tool_type_id: mcpToolType.id, // MCP tool type ID
            tool_provider_type_id: provider.id, // Provider type ID
            credentials,
            tool_metadata: parsedMetadata,
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

            {requiresToken && (
              <>
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
                            showAuthToken
                              ? 'Hide auth token'
                              : 'Show auth token'
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
              </>
            )}

            {isCustomProvider && (
              <>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    mt: 2,
                    mb: 1,
                    cursor: 'pointer',
                  }}
                  onClick={() => setShowAdvancedConfig(!showAdvancedConfig)}
                >
                  <Typography
                    variant="subtitle1"
                    sx={{ fontWeight: 600, color: 'primary.main' }}
                  >
                    MCP Server Configuration
                  </Typography>
                  <IconButton size="small">
                    {showAdvancedConfig ? (
                      <ExpandLessIcon />
                    ) : (
                      <ExpandMoreIcon />
                    )}
                  </IconButton>
                </Box>

                <Collapse in={showAdvancedConfig}>
                  <Box sx={{ mb: 2 }}>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ mb: 2 }}
                    >
                      Configure your custom MCP server. Use credential
                      placeholders with <code>{'{{'}</code> and{' '}
                      <code>{'}}'}</code> format.
                    </Typography>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ mb: 2 }}
                    >
                      Example:
                    </Typography>
                    <Box
                      component="pre"
                      sx={{
                        p: 2,
                        bgcolor: 'background.default',
                        border: 1,
                        borderColor: 'divider',
                        borderRadius: theme => theme.shape.borderRadius,
                        fontSize: theme => theme.typography.body2.fontSize,
                        overflow: 'auto',
                        mb: 2,
                      }}
                    >
                      {`{
  "command": "bunx",
  "args": ["--bun", "@notionhq/notion-mcp-server"],
  "env": {
    "NOTION_TOKEN": "{{ TOKEN }}"
  }
}`}
                    </Box>
                    {jsonError && (
                      <Alert severity="error" sx={{ mb: 2 }}>
                        {jsonError}
                      </Alert>
                    )}
                    <Box sx={getEditorWrapperStyle()}>
                      <Editor
                        key={`tool-metadata-${editorTheme}`}
                        height="300px"
                        defaultLanguage="json"
                        theme={editorTheme}
                        value={toolMetadata}
                        onChange={handleToolMetadataChange}
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
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ mt: 1, display: 'block' }}
                    >
                      Required for custom providers. Define the MCP server
                      command, arguments, and environment variables with
                      credential placeholders.
                    </Typography>
                  </Box>
                </Collapse>
              </>
            )}
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
              (!isEditMode && requiresToken && !authToken) ||
              (!isEditMode && isCustomProvider && !toolMetadata.trim()) ||
              loading ||
              !!jsonError
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
