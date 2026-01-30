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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import dynamic from 'next/dynamic';
import { useTheme } from '@mui/material/styles';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import {
  Tool,
  ToolCreate,
  ToolUpdate,
} from '@/utils/api-client/interfaces/tool';
import { UUID } from 'crypto';
import { MCP_PROVIDER_ICONS } from '@/config/mcp-providers';
import { useNotifications } from '@/components/common/NotificationContext';
import { getErrorMessage } from '@/utils/entity-error-handler';

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
    case 'jira':
      return 'JIRA_API_TOKEN';
    case 'confluence':
      return 'CONFLUENCE_API_TOKEN';
    case 'custom':
      return 'TOKEN';
    default:
      return 'TOKEN';
  }
}

/**
 * Normalize URL to ensure it has https:// scheme
 */
function normalizeUrl(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) {
    return '';
  }
  // If URL doesn't start with http:// or https://, add https://
  if (!/^https?:\/\//i.test(trimmed)) {
    return `https://${trimmed}`;
  }
  return trimmed;
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
  const { data: session } = useSession();
  const notifications = useNotifications();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [authToken, setAuthToken] = useState('');
  const [toolMetadata, setToolMetadata] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAuthToken, setShowAuthToken] = useState(false);
  const [showAdvancedConfig, setShowAdvancedConfig] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{
    is_authenticated: string;
    message: string;
    additional_metadata?: {
      spaces?: Array<{ key: string; name: string }>;
      [key: string]: any;
    };
  } | null>(null);
  const [connectionTested, setConnectionTested] = useState(false);

  // GitHub repository fields
  const [repositoryUrl, setRepositoryUrl] = useState('');

  // Jira and Confluence fields
  const [instanceUrl, setInstanceUrl] = useState('');
  const [username, setUsername] = useState('');

  // Jira space selection
  const [availableSpaces, setAvailableSpaces] = useState<
    Array<{ key: string; name: string }>
  >([]);
  const [selectedSpaceKey, setSelectedSpaceKey] = useState<string>('');
  const [showSpaceSelector, setShowSpaceSelector] = useState(false);

  const isEditMode = mode === 'edit';

  // Check if provider requires authentication token
  const providerType =
    provider?.type_value || tool?.tool_provider_type?.type_value;
  const requiresToken = true; // All providers now require tokens
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

      if (isEditMode && tool) {
        // Edit mode: populate with existing tool data
        setName(tool.name || '');
        setDescription(tool.description || '');
        setAuthToken('************');
        setToolMetadata(
          tool.tool_metadata ? JSON.stringify(tool.tool_metadata, null, 2) : ''
        );

        // Extract repository URL from tool_metadata for GitHub
        if (
          currentProviderType === 'github' &&
          tool.tool_metadata?.repository
        ) {
          const repo = tool.tool_metadata.repository;
          if (repo.owner && repo.repo) {
            setRepositoryUrl(`https://github.com/${repo.owner}/${repo.repo}`);
          }
        } else {
          setRepositoryUrl('');
        }

        // Note: Jira/Confluence URL and username are stored in encrypted credentials
        // We cannot display them in edit mode as they're encrypted
        // Show placeholder to indicate existing values
        setInstanceUrl('************');
        setUsername('************');

        // Extract space_key from tool_metadata if it exists (for Jira)
        if (currentProviderType === 'jira' && tool.tool_metadata?.space_key) {
          setSelectedSpaceKey(tool.tool_metadata.space_key);
        } else {
          setSelectedSpaceKey('');
        }
        setAvailableSpaces([]);
        setShowSpaceSelector(false);

        setError(null);
        setJsonError(null);
        setShowAuthToken(false);
        setLoading(false);
        setShowAdvancedConfig(!!tool.tool_metadata);
        setTestResult(null);
        setConnectionTested(true); // Skip test requirement in edit mode
      } else if (provider) {
        // Create mode: reset to defaults
        setName('');
        setDescription('');
        setAuthToken('');
        setToolMetadata('');
        setRepositoryUrl('');
        setInstanceUrl('');
        // Pre-fill email with logged-in user's email for Jira/Confluence
        const isAtlassian =
          currentProviderType === 'jira' ||
          currentProviderType === 'confluence';
        setUsername(
          isAtlassian && session?.user?.email ? session.user.email : ''
        );
        setSelectedSpaceKey('');
        setAvailableSpaces([]);
        setShowSpaceSelector(false);
        setError(null);
        setJsonError(null);
        setShowAuthToken(false);
        setLoading(false);
        setShowAdvancedConfig(isCustomProvider);
        setTestResult(null);
        setConnectionTested(false);
      }
    }
  }, [
    open,
    provider,
    tool,
    isEditMode,
    isCustomProvider,
    session?.user?.email,
  ]);

  // Reset connection test status when critical credential fields change
  // Note: name and description changes don't affect connection validity
  useEffect(() => {
    if (!isEditMode) {
      // In create mode, reset only when credential fields change
      // (not when name/description change, as they don't affect connection)
      setConnectionTested(false);
      setTestResult(null);
    } else {
      // In edit mode, reset if any credential field was changed
      const tokenChanged = authToken && authToken !== '************';
      const urlChanged = instanceUrl && instanceUrl !== '************';
      const usernameChanged = username && username !== '************';

      if (tokenChanged || urlChanged || usernameChanged) {
        setConnectionTested(false);
        setTestResult(null);
      }
    }
  }, [
    authToken,
    toolMetadata,
    provider,
    isEditMode,
    repositoryUrl,
    instanceUrl,
    username,
  ]);

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

  const parseRepositoryUrl = (
    url: string
  ): { owner: string; repo: string; full_name: string } | null => {
    if (!url || !url.trim()) {
      return null;
    }

    const trimmedUrl = url.trim();
    // Support both full URLs and owner/repo format
    const githubUrlPattern =
      /(?:https?:\/\/)?(?:www\.)?github\.com\/([^/]+)\/([^/]+)/;
    const shortPattern = /^([^/]+)\/([^/]+)$/;

    let match = trimmedUrl.match(githubUrlPattern);
    if (!match) {
      match = trimmedUrl.match(shortPattern);
    }

    if (match) {
      const owner = match[1];
      const repo = match[2].replace(/\.git$/, ''); // Remove .git suffix if present
      return {
        owner,
        repo,
        full_name: `${owner}/${repo}`,
      };
    }

    return null;
  };

  const handleTestConnection = async () => {
    if (!session?.session_token) {
      setError('Session not available. Please try again.');
      return;
    }

    // In create mode, we need to validate required fields first
    if (!isEditMode) {
      if (!provider || (requiresToken && !authToken)) {
        setError('Please fill in all required fields before testing.');
        return;
      }
      if (isCustomProvider && !toolMetadata.trim()) {
        setError('Tool metadata is required for custom providers.');
        return;
      }
    }

    // In edit mode, we need the tool ID
    if (isEditMode && !tool?.id) {
      setError('Tool ID not available. Please save the connection first.');
      return;
    }

    setTestingConnection(true);
    setError(null);
    setTestResult(null);

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const servicesClient = apiFactory.getServicesClient();

      let testRequest: {
        tool_id?: string;
        provider_type_id?: string;
        credentials?: Record<string, string>;
        tool_metadata?: Record<string, any>;
      };

      if (isEditMode) {
        // In edit mode, use existing tool ID
        testRequest = {
          tool_id: tool!.id,
        };
      } else {
        // In create mode, use direct parameters
        if (!provider) {
          setError('Provider not found. Please try again.');
          setTestingConnection(false);
          return;
        }

        const credentialKey = getCredentialKey(provider.type_value);
        let credentials: Record<string, string> = {};
        let parsedMetadata: Record<string, any> | undefined = undefined;

        // Handle Jira credentials
        if (provider.type_value === 'jira') {
          const normalizedUrl = normalizeUrl(instanceUrl);
          credentials = {
            JIRA_URL: normalizedUrl,
            JIRA_USERNAME: username.trim(),
            JIRA_API_TOKEN: authToken.trim(),
          };
        }
        // Handle Confluence credentials
        else if (provider.type_value === 'confluence') {
          const normalizedUrl = normalizeUrl(instanceUrl);
          credentials = {
            CONFLUENCE_URL: normalizedUrl,
            CONFLUENCE_USERNAME: username.trim(),
            CONFLUENCE_API_TOKEN: authToken.trim(),
          };
        }
        // Handle other providers
        else {
          credentials = {
            [credentialKey]: authToken.trim(),
          };
        }
        if (isCustomProvider && toolMetadata.trim()) {
          const validatedMetadata = validateToolMetadata(toolMetadata);
          if (validatedMetadata === null) {
            setError(
              'Please fix the JSON configuration errors before testing.'
            );
            setTestingConnection(false);
            return;
          }
          parsedMetadata = validatedMetadata;
        }

        // Add repository metadata for GitHub if provided
        if (provider.type_value === 'github' && repositoryUrl.trim()) {
          const repoData = parseRepositoryUrl(repositoryUrl);
          if (!repoData) {
            setError(
              'Invalid repository URL. Please use format: https://github.com/owner/repo or owner/repo'
            );
            setTestingConnection(false);
            return;
          }
          parsedMetadata = {
            ...(parsedMetadata || {}),
            repository: repoData,
          };
        }

        testRequest = {
          provider_type_id: provider.id,
          credentials,
          tool_metadata: parsedMetadata,
        };
      }

      // Test the connection
      const result = await servicesClient.testMCPConnection(testRequest);
      setTestResult(result);

      // Mark as tested if successful
      if (result.is_authenticated === 'Yes') {
        setConnectionTested(true);

        // Check if we have spaces in additional_metadata (for Jira)
        if (
          providerType === 'jira' &&
          result.additional_metadata?.spaces &&
          result.additional_metadata.spaces.length > 0
        ) {
          setAvailableSpaces(result.additional_metadata.spaces);
          setShowSpaceSelector(true);
        } else {
          setAvailableSpaces([]);
          setShowSpaceSelector(false);
        }
      } else {
        setConnectionTested(false);
        setAvailableSpaces([]);
        setShowSpaceSelector(false);
      }
    } catch (err) {
      // Display error in testResult (under the button) instead of error state (at top)
      // This matches the success message display pattern
      const errorMessage =
        getErrorMessage(err) || 'Failed to test connection. Please try again.';
      setTestResult({
        is_authenticated: 'No',
        message: errorMessage,
      });
      setConnectionTested(false);
    } finally {
      setTestingConnection(false);
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

        // Get provider type from provider or fall back to tool's provider type
        const currentProviderType =
          provider?.type_value || tool.tool_provider_type?.type_value;

        // Handle Jira/Confluence credentials
        // For Jira/Confluence, we must update credentials if ANY field changed (URL, email, or token)
        // because all three are stored together in the encrypted credentials field
        if (
          currentProviderType === 'jira' ||
          currentProviderType === 'confluence'
        ) {
          const hasUrl = instanceUrl && instanceUrl !== '************';
          const hasUsername = username && username !== '************';
          const hasToken =
            authToken && authToken.trim() && authToken !== '************';

          if (hasUrl || hasUsername || hasToken) {
            if (!hasUrl || !hasUsername) {
              setError(
                'Both URL and email are required for Jira/Confluence connections.'
              );
              setLoading(false);
              return;
            }

            if (!hasToken) {
              setError(
                'API token is required when updating URL or email. Please re-enter your API token.'
              );
              setLoading(false);
              return;
            }

            const normalizedUrl = normalizeUrl(instanceUrl);
            if (currentProviderType === 'jira') {
              updates.credentials = {
                JIRA_URL: normalizedUrl,
                JIRA_USERNAME: username.trim(),
                JIRA_API_TOKEN: authToken.trim(),
              };
            } else {
              updates.credentials = {
                CONFLUENCE_URL: normalizedUrl,
                CONFLUENCE_USERNAME: username.trim(),
                CONFLUENCE_API_TOKEN: authToken.trim(),
              };
            }
          }
        }
        // Handle other providers - only update if token was changed
        else if (
          authToken &&
          authToken.trim() &&
          authToken !== '************'
        ) {
          const credentialKey = getCredentialKey(currentProviderType);
          updates.credentials = {
            [credentialKey]: authToken.trim(),
          };
        }

        // Include tool_metadata if it was provided
        let metadataToUpdate: Record<string, any> | undefined = undefined;

        // For non-Jira/Confluence providers, handle metadata
        if (toolMetadata.trim()) {
          const validatedMetadata = validateToolMetadata(toolMetadata);
          if (validatedMetadata !== null) {
            metadataToUpdate = validatedMetadata;
          }
        } else if (isCustomProvider) {
          // For custom providers, tool_metadata is required
          setError('Tool metadata is required for custom providers.');
          setLoading(false);
          return;
        }

        // Add or update repository metadata for GitHub
        if (providerType === 'github') {
          if (repositoryUrl.trim()) {
            const repoData = parseRepositoryUrl(repositoryUrl);
            if (!repoData) {
              setError(
                'Invalid repository URL. Please use format: https://github.com/owner/repo or owner/repo'
              );
              setLoading(false);
              return;
            }
            metadataToUpdate = {
              ...(metadataToUpdate || tool.tool_metadata || {}),
              repository: repoData,
            };
          } else {
            // Remove repository metadata if URL is empty
            metadataToUpdate = {
              ...(metadataToUpdate || tool.tool_metadata || {}),
            };
            delete metadataToUpdate.repository;
          }
        }

        // Add or update space_key metadata for Jira
        if (providerType === 'jira' && selectedSpaceKey) {
          metadataToUpdate = {
            ...(metadataToUpdate || tool.tool_metadata || {}),
            space_key: selectedSpaceKey,
          };
        }

        if (metadataToUpdate) {
          updates.tool_metadata = metadataToUpdate;
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
      // Create mode: require connection test
      if (!connectionTested) {
        setError('Please test the connection before saving the tool.');
        return;
      }

      // Validate that test was successful
      if (!testResult || testResult.is_authenticated !== 'Yes') {
        setError('Connection test must be successful before saving.');
        return;
      }

      // Validate required fields
      if (!provider || !name || !authToken) {
        setError('Please fill in all required fields.');
        return;
      }

      // Validate Jira/Confluence specific fields
      if (
        (provider.type_value === 'jira' ||
          provider.type_value === 'confluence') &&
        (!instanceUrl || !username)
      ) {
        setError('Please fill in all required fields (URL and email).');
        return;
      }

      // Validate Jira space selection
      if (
        provider.type_value === 'jira' &&
        showSpaceSelector &&
        !selectedSpaceKey
      ) {
        setError('Please select a Jira space.');
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

          // Build credentials based on provider type
          let credentials: Record<string, string> = {};
          let parsedMetadata: Record<string, any> | undefined = undefined;

          // Handle Jira credentials
          if (provider.type_value === 'jira') {
            const normalizedUrl = normalizeUrl(instanceUrl);
            credentials = {
              JIRA_URL: normalizedUrl,
              JIRA_USERNAME: username.trim(),
              JIRA_API_TOKEN: authToken.trim(),
            };
          }
          // Handle Confluence credentials
          else if (provider.type_value === 'confluence') {
            const normalizedUrl = normalizeUrl(instanceUrl);
            credentials = {
              CONFLUENCE_URL: normalizedUrl,
              CONFLUENCE_USERNAME: username.trim(),
              CONFLUENCE_API_TOKEN: authToken.trim(),
            };
          }
          // Handle other providers
          else {
            credentials = {
              [getCredentialKey(provider.type_value)]: authToken.trim(),
            };
          }

          // Parse and validate tool_metadata for custom providers
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

          // Add repository metadata for GitHub if provided
          if (providerType === 'github' && repositoryUrl.trim()) {
            const repoData = parseRepositoryUrl(repositoryUrl);
            if (!repoData) {
              setError(
                'Invalid repository URL. Please use format: https://github.com/owner/repo or owner/repo'
              );
              setLoading(false);
              return;
            }
            parsedMetadata = {
              ...(parsedMetadata || {}),
              repository: repoData,
            };
          }

          // Add space_key metadata for Jira if selected
          if (providerType === 'jira' && selectedSpaceKey) {
            parsedMetadata = {
              ...(parsedMetadata || {}),
              space_key: selectedSpaceKey,
            };
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

  const displayName = provider?.type_value
    ? provider.type_value.charAt(0).toUpperCase() + provider.type_value.slice(1)
    : 'MCP Provider';

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
              {displayName}
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
            />

            <TextField
              label="Description"
              fullWidth
              multiline
              rows={2}
              value={description}
              onChange={e => setDescription(e.target.value)}
            />

            {requiresToken && (
              <>
                <Typography
                  variant="subtitle1"
                  sx={{ fontWeight: 600, mb: 1, color: 'primary.main', mt: 1 }}
                >
                  Authentication
                </Typography>

                {/* Jira/Confluence specific fields */}
                {(providerType === 'jira' || providerType === 'confluence') && (
                  <>
                    <TextField
                      label="Atlassian Organization URL"
                      fullWidth
                      required={!isEditMode}
                      value={instanceUrl}
                      onChange={e => setInstanceUrl(e.target.value)}
                      onFocus={e => {
                        // Clear placeholder when user clicks on field in edit mode
                        if (isEditMode && instanceUrl === '************') {
                          setInstanceUrl('');
                        }
                      }}
                      onBlur={e => {
                        // Restore placeholder if field is empty in edit mode
                        if (isEditMode && !e.target.value) {
                          setInstanceUrl('************');
                        }
                      }}
                      placeholder={
                        providerType === 'jira'
                          ? 'https://your-domain.atlassian.net'
                          : 'https://your-domain.atlassian.net/wiki'
                      }
<<<<<<< HEAD
                      helperText={
                        isEditMode
                          ? instanceUrl !== '************' && instanceUrl !== ''
                            ? 'New URL will replace the current one'
                            : 'Click to update the URL'
                          : providerType === 'jira'
                            ? 'Your Jira instance URL'
                            : 'Your Confluence instance URL'
                      }
=======
>>>>>>> dc18692db (chore: change nomenclature from jira projects to jira spaces)
                    />

                    <TextField
                      label="Email"
                      fullWidth
                      required={!isEditMode}
                      value={username}
                      onChange={e => setUsername(e.target.value)}
                      onFocus={e => {
                        // Clear placeholder when user clicks on field in edit mode
                        if (isEditMode && username === '************') {
                          setUsername('');
                        }
                      }}
                      onBlur={e => {
                        // Restore placeholder if field is empty in edit mode
                        if (isEditMode && !e.target.value) {
                          setUsername('************');
                        }
                      }}
                      placeholder="your-email@example.com"
                    />
                  </>
                )}

                <TextField
                  label={
                    providerType === 'jira' || providerType === 'confluence'
                      ? 'API Token'
                      : 'Authentication token'
                  }
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
                        ? 'New API token will replace the current one'
                        : 'Click to update the API token'
                      : undefined
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
                <Box sx={{ mt: 1 }}>
                  <Button
                    variant="outlined"
                    size="medium"
                    onClick={handleTestConnection}
                    disabled={
                      testingConnection ||
                      loading ||
                      !authToken ||
                      // For Jira/Confluence: in create mode, always require URL and username
                      // In edit mode, only require them if any credential field was touched
                      (!isEditMode &&
                        (providerType === 'jira' ||
                          providerType === 'confluence') &&
                        (!instanceUrl || !username)) ||
                      (isEditMode &&
                        (providerType === 'jira' ||
                          providerType === 'confluence') &&
                        (instanceUrl ||
                          username ||
                          (authToken && authToken !== '************')) &&
                        (!instanceUrl || !username)) ||
                      (isCustomProvider && !toolMetadata.trim())
                    }
                    sx={{ minWidth: 150 }}
                  >
                    {testingConnection ? 'Testing...' : 'Test Connection'}
                  </Button>
                  {testResult && (
                    <Alert
                      severity={
                        testResult.is_authenticated === 'Yes'
                          ? 'success'
                          : 'error'
                      }
                      icon={
                        testResult.is_authenticated === 'Yes' ? (
                          <CheckCircleIcon />
                        ) : (
                          <ErrorIcon />
                        )
                      }
                      sx={{ mt: 2 }}
                    >
                      <Typography variant="body2" fontWeight={600}>
                        {testResult.is_authenticated === 'Yes'
                          ? 'Connection Successful'
                          : 'Connection Failed'}
                      </Typography>
                      <Typography variant="body2" sx={{ mt: 0.5 }}>
                        {testResult.message}
                      </Typography>
                    </Alert>
                  )}
                </Box>

                {/* Jira Space Selection */}
                {showSpaceSelector &&
                  availableSpaces.length > 0 &&
                  providerType === 'jira' && (
                    <Box sx={{ mt: 2 }}>
                      <Typography
                        variant="subtitle1"
                        sx={{
                          fontWeight: 600,
                          mb: 1,
                          color: 'primary.main',
                        }}
                      >
                        Space Selection
                      </Typography>
                      <FormControl fullWidth required>
                        <InputLabel>Jira Space</InputLabel>
                        <Select
                          value={selectedSpaceKey}
                          onChange={e => setSelectedSpaceKey(e.target.value)}
                          label="Jira Space"
                        >
                          {availableSpaces.map(space => (
                            <MenuItem key={space.key} value={space.key}>
                              {space.name} ({space.key})
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ mt: 0.5, display: 'block' }}
                      >
                        Select the Jira space where issues will be created
                      </Typography>
                    </Box>
                  )}
              </>
            )}

            {/* GitHub Repository Configuration */}
            {providerType === 'github' && (
              <>
                <Typography
                  variant="subtitle1"
                  sx={{ fontWeight: 600, mb: 1, color: 'primary.main', mt: 2 }}
                >
                  Repository Scope (Optional)
                </Typography>

                <TextField
                  label="Repository URL"
                  fullWidth
                  value={repositoryUrl}
                  onChange={e => setRepositoryUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
                  helperText="Optional: Restrict this connection to a specific repository. Leave empty for user-level access to all repositories."
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
                      Provide your API token above, then paste your MCP server
                      config below using <code>{'{{ TOKEN }}'}</code> as a
                      placeholder wherever the token is required.
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
  "command": "npx",
  "args": ["@example/mcp-server"],
  "env": {
    "API_TOKEN": "{{ TOKEN }}"
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

        {/* Connection Test Required Message */}
        {!isEditMode && !connectionTested && !testResult && (
          <Box sx={{ px: 3, pb: 1 }}>
            <Alert severity="info">
              Please test the connection before saving the tool configuration.
            </Alert>
          </Box>
        )}
        {isEditMode && !connectionTested && !testResult && (
          <Box sx={{ px: 3, pb: 1 }}>
            <Alert severity="info">
              Please test the connection with the updated credentials before
              saving.
            </Alert>
          </Box>
        )}

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
              // For Jira/Confluence: in create mode, always require URL and username
              // In edit mode, only require them if any credential field was touched
              (!isEditMode &&
                (providerType === 'jira' || providerType === 'confluence') &&
                (!instanceUrl || !username)) ||
              (isEditMode &&
                (providerType === 'jira' || providerType === 'confluence') &&
                (instanceUrl ||
                  username ||
                  (authToken && authToken !== '************')) &&
                (!instanceUrl || !username)) ||
              (!isEditMode && isCustomProvider && !toolMetadata.trim()) ||
              (!isEditMode && !connectionTested) ||
              (isEditMode && !connectionTested) || // Require test if any credential changed in edit mode
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
