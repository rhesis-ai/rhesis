import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  IconButton,
  Alert,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';

import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { alpha, useTheme } from '@mui/material/styles';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import {
  Tool,
  ToolCreate,
  ToolUpdate,
} from '@/utils/api-client/interfaces/tool';
import { UUID } from 'crypto';
import { TOOL_PROVIDER_ICONS } from '@/config/tool-providers';
import { getErrorMessage } from '@/utils/entity-error-handler';
import { BORDER_RADIUS } from '@/styles/theme-constants';

/**
 * Get the credential key name for a given provider
 */
function getCredentialKey(providerType: string | undefined): string {
  switch (providerType) {
    case 'notion':
      return 'NOTION_TOKEN';
    case 'github':
      return 'GITHUB_PERSONAL_ACCESS_TOKEN';
    case 'gitlab':
      return 'GITLAB_PERSONAL_ACCESS_TOKEN';
    case 'shortcut':
      return 'SHORTCUT_API_TOKEN';
    case 'asana':
      return 'ASANA_ACCESS_TOKEN';
    case 'jira':
      return 'JIRA_API_TOKEN';
    case 'confluence':
      return 'CONFLUENCE_API_TOKEN';
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

interface ToolConnectionDrawerProps {
  open: boolean;
  provider?: TypeLookup | null;
  providers?: TypeLookup[];
  toolType?: TypeLookup | null;
  tool?: Tool | null; // For edit mode
  mode?: 'create' | 'edit';
  onClose: () => void;
  onConnect?: (providerId: string, toolData: ToolCreate) => Promise<Tool>;
  onUpdate?: (toolId: UUID, updates: Partial<ToolUpdate>) => Promise<void>;
}

export function ToolConnectionDrawer({
  open,
  provider: providerProp,
  providers = [],
  tool,
  mode = 'create',
  onClose,
  onConnect,
  onUpdate,
}: ToolConnectionDrawerProps) {
  const { data: session } = useSession();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [authToken, setAuthToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAuthToken, setShowAuthToken] = useState(false);

  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{
    is_authenticated: string;
    message: string;
    additional_metadata?: {
      spaces?: Array<{ key: string; name: string }>;
      [key: string]: unknown;
    };
  } | null>(null);
  const [connectionTested, setConnectionTested] = useState(false);
  // Tracks whether the user has modified credential fields in edit mode.
  // A re-test is only required when this is true.
  const [credentialsModified, setCredentialsModified] = useState(false);
  const [scopeMetadataModified, setScopeMetadataModified] = useState(false);

  // Snapshot of non-credential fields when the drawer opens in edit mode,
  // used to detect whether anything has actually changed.
  const [initialName, setInitialName] = useState('');
  const [initialDescription, setInitialDescription] = useState('');
  const [initialRepositoryUrl, setInitialRepositoryUrl] = useState('');
  const [initialProjectNamespace, setInitialProjectNamespace] = useState('');
  const [initialGitlabApiUrl, setInitialGitlabApiUrl] = useState('');
  const [initialSpaceKey, setInitialSpaceKey] = useState('');
  const [initialWorkspaceGid, setInitialWorkspaceGid] = useState('');

  // GitHub repository fields
  const [repositoryUrl, setRepositoryUrl] = useState('');

  // GitLab project fields
  const [projectNamespace, setProjectNamespace] = useState('');
  const [gitlabApiUrl, setGitlabApiUrl] = useState('');

  // Asana workspace scope
  const [workspaceGid, setWorkspaceGid] = useState('');

  // Jira and Confluence fields
  const [instanceUrl, setInstanceUrl] = useState('');
  const [username, setUsername] = useState('');

  // Jira space selection
  const [availableSpaces, setAvailableSpaces] = useState<
    Array<{ key: string; name: string }>
  >([]);
  const [selectedSpaceKey, setSelectedSpaceKey] = useState<string>('');
  const [showSpaceSelector, setShowSpaceSelector] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<TypeLookup | null>(
    providerProp ?? null
  );

  const theme = useTheme();
  const isEditMode = mode === 'edit';
  const provider = providerProp ?? selectedProvider;

  // Check if provider requires authentication token
  const providerType =
    provider?.type_value || tool?.tool_provider_type?.type_value;
  const requiresToken = true; // All providers now require tokens

  useEffect(() => {
    if (open && !isEditMode) {
      setSelectedProvider(providerProp ?? providers[0] ?? null);
    }
  }, [open, isEditMode, providerProp, providers]);

  // Reset form when drawer opens
  useEffect(() => {
    if (open) {
      if (providerProp) {
        setSelectedProvider(providerProp);
      }

      const currentProviderType =
        provider?.type_value || tool?.tool_provider_type?.type_value;

      if (isEditMode && tool) {
        // Edit mode: populate with existing tool data
        setName(tool.name || '');
        setDescription(tool.description || '');
        setInitialName(tool.name || '');
        setInitialDescription(tool.description || '');
        setAuthToken('************');

        // Extract repository URL from tool_metadata for GitHub
        if (
          currentProviderType === 'github' &&
          tool.tool_metadata?.repository
        ) {
          const repo = tool.tool_metadata.repository;
          if (repo.owner && repo.repo) {
            const repoUrl = `https://github.com/${repo.owner}/${repo.repo}`;
            setRepositoryUrl(repoUrl);
            setInitialRepositoryUrl(repoUrl);
          }
        } else {
          setRepositoryUrl('');
          setInitialRepositoryUrl('');
        }

        if (
          currentProviderType === 'gitlab' &&
          typeof tool.tool_metadata?.project?.namespace === 'string'
        ) {
          setProjectNamespace(tool.tool_metadata.project.namespace);
          setInitialProjectNamespace(tool.tool_metadata.project.namespace);
        } else {
          setProjectNamespace('');
          setInitialProjectNamespace('');
        }
        setGitlabApiUrl('');
        setInitialGitlabApiUrl('');

        if (
          currentProviderType === 'asana' &&
          typeof tool.tool_metadata?.workspace_gid === 'string'
        ) {
          setWorkspaceGid(tool.tool_metadata.workspace_gid);
          setInitialWorkspaceGid(tool.tool_metadata.workspace_gid);
        } else {
          setWorkspaceGid('');
          setInitialWorkspaceGid('');
        }

        // Note: Jira/Confluence URL and username are stored in encrypted credentials
        // We cannot display them in edit mode as they're encrypted
        // Show placeholder to indicate existing values
        setInstanceUrl('************');
        setUsername('************');

        // Extract space_key from tool_metadata if it exists (for Jira)
        if (currentProviderType === 'jira' && tool.tool_metadata?.space_key) {
          setSelectedSpaceKey(tool.tool_metadata.space_key);
          setInitialSpaceKey(tool.tool_metadata.space_key);
        } else {
          setSelectedSpaceKey('');
          setInitialSpaceKey('');
        }
        setAvailableSpaces([]);
        setShowSpaceSelector(false);

        setError(null);
        setShowAuthToken(false);
        setLoading(false);
        setTestResult(null);
        setConnectionTested(false);
        setCredentialsModified(false);
        setScopeMetadataModified(false);
      } else if (provider) {
        // Create mode: reset to defaults
        setName('');
        setDescription('');
        setAuthToken('');
        setRepositoryUrl('');
        setProjectNamespace('');
        setGitlabApiUrl('');
        setWorkspaceGid('');
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
        setShowAuthToken(false);
        setLoading(false);
        setTestResult(null);
        setConnectionTested(false);
        setCredentialsModified(false);
        setScopeMetadataModified(false);
      }
    }
  }, [open, provider, tool, isEditMode, session?.user?.email]);

  // Reset connection test status when critical credential fields change
  // Note: name and description changes don't affect connection validity
  useEffect(() => {
    if (!isEditMode) {
      // In create mode, reset whenever credential-related fields change
      setConnectionTested(false);
      setTestResult(null);
    } else {
      // In edit mode, derive modified state from current field values so that
      // reverting a field back to the placeholder resets the flag correctly.
      const tokenChanged = Boolean(authToken && authToken !== '************');
      const urlChanged = Boolean(instanceUrl && instanceUrl !== '************');
      const usernameChanged = Boolean(username && username !== '************');
      const scopeMetadataChanged =
        repositoryUrl !== initialRepositoryUrl ||
        projectNamespace !== initialProjectNamespace ||
        selectedSpaceKey !== initialSpaceKey ||
        workspaceGid !== initialWorkspaceGid;
      const gitlabApiUrlChanged = gitlabApiUrl !== initialGitlabApiUrl;
      const credentialsChanged =
        tokenChanged || urlChanged || usernameChanged || gitlabApiUrlChanged;

      setCredentialsModified(credentialsChanged);
      setScopeMetadataModified(scopeMetadataChanged);
      if (credentialsChanged || scopeMetadataChanged) {
        setConnectionTested(false);
        setTestResult(null);
      }
    }
  }, [
    authToken,
    provider,
    isEditMode,
    repositoryUrl,
    instanceUrl,
    username,
    projectNamespace,
    selectedSpaceKey,
    gitlabApiUrl,
    workspaceGid,
    initialRepositoryUrl,
    initialProjectNamespace,
    initialSpaceKey,
    initialWorkspaceGid,
    initialGitlabApiUrl,
  ]);

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

  const parseGitLabProjectUrl = (url: string): { namespace: string } | null => {
    if (!url || !url.trim()) {
      return null;
    }

    const trimmedUrl = url.trim();

    if (/^https?:\/\//i.test(trimmedUrl)) {
      try {
        const parsed = new URL(normalizeUrl(trimmedUrl));
        const path = parsed.pathname.replace(/^\/+|\/+$/g, '');
        const namespace = path.split('/-/')[0];
        if (namespace.includes('/')) {
          return { namespace };
        }
      } catch {
        return null;
      }
    }

    const shortPattern = /^([^/\s]+\/[^/\s]+(?:\/[^/\s]+)*)$/;
    const match = trimmedUrl.match(shortPattern);
    if (match && match[1].includes('/')) {
      return { namespace: match[1] };
    }

    return null;
  };

  const buildGitLabCredentials = (
    token: string,
    apiUrl: string
  ): Record<string, string> => {
    const credentials: Record<string, string> = {
      GITLAB_PERSONAL_ACCESS_TOKEN: token.trim(),
    };
    const trimmedApiUrl = apiUrl.trim();
    if (trimmedApiUrl) {
      credentials.GITLAB_API_URL = normalizeUrl(trimmedApiUrl).replace(
        /\/$/,
        ''
      );
      if (!credentials.GITLAB_API_URL.endsWith('/api/v4')) {
        credentials.GITLAB_API_URL = `${credentials.GITLAB_API_URL}/api/v4`;
      }
    }
    return credentials;
  };

  const buildAsanaMetadata = (
    workspace: string
  ): Record<string, unknown> | undefined => {
    const trimmed = workspace.trim();
    return trimmed ? { workspace_gid: trimmed } : undefined;
  };

  const buildScopeMetadataFromForm = (
    currentProviderType: string | undefined
  ): Record<string, unknown> | undefined => {
    if (!currentProviderType) {
      return undefined;
    }

    if (currentProviderType === 'github' && repositoryUrl.trim()) {
      const repoData = parseRepositoryUrl(repositoryUrl);
      return repoData ? { repository: repoData } : undefined;
    }

    if (currentProviderType === 'gitlab' && projectNamespace.trim()) {
      const projectData = parseGitLabProjectUrl(projectNamespace);
      return projectData ? { project: projectData } : undefined;
    }

    if (currentProviderType === 'jira' && selectedSpaceKey) {
      return { space_key: selectedSpaceKey };
    }

    if (currentProviderType === 'asana') {
      return buildAsanaMetadata(workspaceGid);
    }

    return undefined;
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
        tool_metadata?: Record<string, unknown>;
      };

      if (
        isEditMode &&
        tool?.id &&
        !credentialsModified &&
        !scopeMetadataModified
      ) {
        // Edit mode, no config changes — test existing stored credentials
        testRequest = {
          tool_id: tool.id,
        };
      } else if (
        isEditMode &&
        tool?.id &&
        !credentialsModified &&
        scopeMetadataModified
      ) {
        // Scope-only edit — reuse stored credentials with updated metadata
        const currentProviderType =
          provider?.type_value || tool.tool_provider_type?.type_value;
        const parsedMetadata = buildScopeMetadataFromForm(currentProviderType);

        if (
          currentProviderType === 'github' &&
          repositoryUrl.trim() &&
          !parsedMetadata
        ) {
          setError(
            'Invalid repository URL. Please use format: https://github.com/owner/repo or owner/repo'
          );
          setTestingConnection(false);
          return;
        }
        if (
          currentProviderType === 'gitlab' &&
          projectNamespace.trim() &&
          !parsedMetadata
        ) {
          setError(
            'Invalid project path. Please use format: group/project or https://gitlab.com/group/project'
          );
          setTestingConnection(false);
          return;
        }

        // When the Asana workspace field is cleared, buildScopeMetadataFromForm
        // returns undefined and JSON would drop the key, so the backend would
        // test against the stored workspace_gid. Send an explicit empty object
        // so the test reflects the cleared scope.
        const scopeMetadata =
          currentProviderType === 'asana' && !workspaceGid.trim()
            ? {}
            : parsedMetadata;

        testRequest = {
          tool_id: tool.id,
          tool_metadata: scopeMetadata,
        };
      } else if (isEditMode && tool?.id && credentialsModified) {
        // Edit mode with changed credentials — test new credentials directly
        const currentProviderType =
          provider?.type_value || tool.tool_provider_type?.type_value;

        if (!currentProviderType) {
          setError('Provider type not available. Please try again.');
          setTestingConnection(false);
          return;
        }

        const tokenIsPlaceholder = authToken === '************';
        const urlIsPlaceholder = instanceUrl === '************';
        const usernameIsPlaceholder = username === '************';

        if (
          currentProviderType === 'jira' ||
          currentProviderType === 'confluence'
        ) {
          if (urlIsPlaceholder || usernameIsPlaceholder || tokenIsPlaceholder) {
            setError(
              'Please re-enter the URL, email, and API token to test updated credentials.'
            );
            setTestingConnection(false);
            return;
          }
        } else if (tokenIsPlaceholder) {
          setError(
            'Please re-enter your API token to test updated credentials.'
          );
          setTestingConnection(false);
          return;
        }

        const credentialKey = getCredentialKey(currentProviderType);
        let credentials: Record<string, string> = {};
        let parsedMetadata: Record<string, unknown> | undefined = undefined;

        if (currentProviderType === 'jira') {
          const normalizedUrl = normalizeUrl(instanceUrl);
          credentials = {
            JIRA_URL: normalizedUrl,
            JIRA_USERNAME: username.trim(),
            JIRA_API_TOKEN: authToken.trim(),
          };
        } else if (currentProviderType === 'confluence') {
          const normalizedUrl = normalizeUrl(instanceUrl);
          credentials = {
            CONFLUENCE_URL: normalizedUrl,
            CONFLUENCE_USERNAME: username.trim(),
            CONFLUENCE_API_TOKEN: authToken.trim(),
          };
        } else if (currentProviderType === 'gitlab') {
          credentials = buildGitLabCredentials(authToken, gitlabApiUrl);
        } else {
          credentials = {
            [credentialKey]: authToken.trim(),
          };
        }

        if (currentProviderType === 'github' && repositoryUrl.trim()) {
          const repoData = parseRepositoryUrl(repositoryUrl);
          if (!repoData) {
            setError(
              'Invalid repository URL. Please use format: https://github.com/owner/repo or owner/repo'
            );
            setTestingConnection(false);
            return;
          }
          parsedMetadata = { repository: repoData };
        }

        if (currentProviderType === 'gitlab' && projectNamespace.trim()) {
          const projectData = parseGitLabProjectUrl(projectNamespace);
          if (!projectData) {
            setError(
              'Invalid project path. Please use format: group/project or https://gitlab.com/group/project'
            );
            setTestingConnection(false);
            return;
          }
          parsedMetadata = { project: projectData };
        }

        testRequest = {
          provider_type_id: tool.tool_provider_type?.id,
          credentials,
          tool_metadata: parsedMetadata,
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
        let parsedMetadata: Record<string, unknown> | undefined = undefined;

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
        } else if (provider.type_value === 'gitlab') {
          credentials = buildGitLabCredentials(authToken, gitlabApiUrl);
        }
        // Handle other providers
        else {
          credentials = {
            [credentialKey]: authToken.trim(),
          };
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

        if (provider.type_value === 'gitlab' && projectNamespace.trim()) {
          const projectData = parseGitLabProjectUrl(projectNamespace);
          if (!projectData) {
            setError(
              'Invalid project path. Please use format: group/project or https://gitlab.com/group/project'
            );
            setTestingConnection(false);
            return;
          }
          parsedMetadata = {
            ...(parsedMetadata || {}),
            project: projectData,
          };
        }

        testRequest = {
          provider_type_id: provider.id,
          credentials,
          tool_metadata: parsedMetadata,
        };
      }

      const result = await servicesClient.testToolConnection(testRequest);
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

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();

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
          if (currentProviderType === 'gitlab') {
            updates.credentials = buildGitLabCredentials(
              authToken,
              gitlabApiUrl
            );
          } else {
            const credentialKey = getCredentialKey(currentProviderType);
            updates.credentials = {
              [credentialKey]: authToken.trim(),
            };
          }
        } else if (
          currentProviderType === 'gitlab' &&
          gitlabApiUrl !== initialGitlabApiUrl &&
          gitlabApiUrl.trim()
        ) {
          setError('Re-enter your GitLab token when updating the API URL.');
          setLoading(false);
          return;
        }

        let metadataToUpdate: Record<string, unknown> | undefined = undefined;

        // GitHub requires repository metadata
        if (providerType === 'github') {
          if (!repositoryUrl.trim()) {
            setError('Repository URL is required for GitHub integrations');
            setLoading(false);
            return;
          }
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
        }

        // Jira requires space_key metadata
        if (providerType === 'jira') {
          if (!selectedSpaceKey) {
            setError('Jira space selection is required');
            setLoading(false);
            return;
          }
          metadataToUpdate = {
            ...(metadataToUpdate || tool.tool_metadata || {}),
            space_key: selectedSpaceKey,
          };
        }

        if (providerType === 'gitlab') {
          if (!projectNamespace.trim()) {
            setError('Project namespace is required for GitLab integrations');
            setLoading(false);
            return;
          }
          const projectData = parseGitLabProjectUrl(projectNamespace);
          if (!projectData) {
            setError(
              'Invalid project path. Please use format: group/project or https://gitlab.com/group/project'
            );
            setLoading(false);
            return;
          }
          metadataToUpdate = {
            ...(metadataToUpdate || tool.tool_metadata || {}),
            project: projectData,
          };
        }

        if (providerType === 'asana') {
          metadataToUpdate = {
            ...(metadataToUpdate || tool.tool_metadata || {}),
            ...(buildAsanaMetadata(workspaceGid) || {}),
          };
          if (!workspaceGid.trim() && metadataToUpdate.workspace_gid) {
            delete metadataToUpdate.workspace_gid;
          }
        }

        if (metadataToUpdate) {
          updates.tool_metadata = metadataToUpdate;
        }

        await onUpdate(tool.id, updates);
        // Don't reset loading state - let dialog close with "Updating..." text
        onClose();
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Failed to update tool connection'
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

      if (onConnect) {
        setLoading(true);
        setError(null);
        try {
          if (!provider) {
            setError('Provider not found. Please try again.');
            setLoading(false);
            return;
          }

          // Build credentials based on provider type
          let credentials: Record<string, string> = {};
          let parsedMetadata: Record<string, unknown> | undefined = undefined;

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
          } else if (provider.type_value === 'gitlab') {
            credentials = buildGitLabCredentials(authToken, gitlabApiUrl);
          }
          // Handle other providers
          else {
            credentials = {
              [getCredentialKey(provider.type_value)]: authToken.trim(),
            };
          }

          // GitHub requires repository metadata
          if (providerType === 'github') {
            if (!repositoryUrl.trim()) {
              setError('Repository URL is required for GitHub integrations');
              setLoading(false);
              return;
            }
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

          // Jira requires space_key metadata
          if (providerType === 'jira') {
            if (!selectedSpaceKey) {
              setError('Jira space selection is required');
              setLoading(false);
              return;
            }
            parsedMetadata = {
              ...(parsedMetadata || {}),
              space_key: selectedSpaceKey,
            };
          }

          if (providerType === 'gitlab') {
            if (!projectNamespace.trim()) {
              setError('Project namespace is required for GitLab integrations');
              setLoading(false);
              return;
            }
            const projectData = parseGitLabProjectUrl(projectNamespace);
            if (!projectData) {
              setError(
                'Invalid project path. Please use format: group/project or https://gitlab.com/group/project'
              );
              setLoading(false);
              return;
            }
            parsedMetadata = {
              ...(parsedMetadata || {}),
              project: projectData,
            };
          }

          if (providerType === 'asana') {
            parsedMetadata = {
              ...(parsedMetadata || {}),
              ...(buildAsanaMetadata(workspaceGid) || {}),
            };
          }

          const toolData: ToolCreate = {
            name,
            description: description || undefined,
            tool_provider_type_id: provider.id,
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
  const providerIconKey = provider?.type_value ?? '';
  const providerIcon = TOOL_PROVIDER_ICONS[providerIconKey] || (
    <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.medium }} />
  );

  const displayName = provider?.type_value
    ? provider.type_value.charAt(0).toUpperCase() + provider.type_value.slice(1)
    : 'Tool Provider';

  const basicFieldsChanged =
    isEditMode &&
    (name !== initialName ||
      description !== initialDescription ||
      repositoryUrl !== initialRepositoryUrl ||
      projectNamespace !== initialProjectNamespace ||
      workspaceGid !== initialWorkspaceGid ||
      selectedSpaceKey !== initialSpaceKey);

  const saveDisabled =
    (!provider && !tool?.tool_provider_type) ||
    !name ||
    (!isEditMode && !authToken) ||
    (!isEditMode && providerType === 'gitlab' && !projectNamespace.trim()) ||
    (!isEditMode &&
      (providerType === 'jira' || providerType === 'confluence') &&
      (!instanceUrl || !username)) ||
    (isEditMode &&
      (providerType === 'jira' || providerType === 'confluence') &&
      (instanceUrl ||
        username ||
        (authToken && authToken !== '************')) &&
      (!instanceUrl || !username)) ||
    (!isEditMode && !connectionTested) ||
    (isEditMode &&
      (credentialsModified || scopeMetadataModified) &&
      !connectionTested) ||
    (isEditMode &&
      !credentialsModified &&
      !scopeMetadataModified &&
      !basicFieldsChanged) ||
    loading;

  const sectionHeadingSx = {
    fontWeight: 700,
    fontSize: theme.typography.h6.fontSize,
    lineHeight: '25px',
    color: 'text.primary',
  } as const;

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={isEditMode ? `Update ${displayName}` : `Connect ${displayName}`}
      onSave={() => void handleSubmit()}
      saveDisabled={saveDisabled}
      saveButtonText={isEditMode ? 'Update' : 'Connect'}
      loading={loading}
      error={error ?? undefined}
      width={640}
    >
      <Stack spacing={2}>
        {!isEditMode && providers.length > 0 && (
          <FormControl fullWidth>
            <InputLabel id="tool-provider-label">Provider</InputLabel>
            <Select
              labelId="tool-provider-label"
              value={provider?.id ?? ''}
              label="Provider"
              onChange={e => {
                const next = providers.find(p => p.id === e.target.value);
                setSelectedProvider(next ?? null);
                setConnectionTested(false);
                setTestResult(null);
                setError(null);
              }}
            >
              {providers.map(p => (
                <MenuItem key={p.id} value={p.id}>
                  {p.type_value.charAt(0).toUpperCase() + p.type_value.slice(1)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}

        <Stack spacing={3}>
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
        </Stack>

        {/* Authentication */}
        {requiresToken && (
          <Stack spacing={3}>
            <Typography sx={sectionHeadingSx}>Authentication</Typography>

            {(providerType === 'jira' || providerType === 'confluence') && (
              <>
                <TextField
                  label="Atlassian Organization URL"
                  fullWidth
                  required={!isEditMode}
                  value={instanceUrl}
                  onChange={e => setInstanceUrl(e.target.value)}
                  onFocus={_e => {
                    if (isEditMode && instanceUrl === '************') {
                      setInstanceUrl('');
                    }
                  }}
                  onBlur={e => {
                    if (isEditMode && !e.target.value) {
                      setInstanceUrl('************');
                    }
                  }}
                  placeholder={
                    providerType === 'jira'
                      ? 'https://your-domain.atlassian.net'
                      : 'https://your-domain.atlassian.net/wiki'
                  }
                />
                <TextField
                  label="Email"
                  fullWidth
                  required={!isEditMode}
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  onFocus={_e => {
                    if (isEditMode && username === '************') {
                      setUsername('');
                    }
                  }}
                  onBlur={e => {
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
              onFocus={_e => {
                if (isEditMode && authToken === '************') {
                  setAuthToken('');
                }
              }}
              onBlur={e => {
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

            {providerType === 'github' && (
              <TextField
                label="Repository URL"
                fullWidth
                required
                value={repositoryUrl}
                onChange={e => setRepositoryUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                helperText="Specify the GitHub repository for this connection"
              />
            )}

            {providerType === 'gitlab' && (
              <>
                <TextField
                  label="Project namespace"
                  fullWidth
                  required
                  value={projectNamespace}
                  onChange={e => setProjectNamespace(e.target.value)}
                  placeholder="my-group/my-project"
                  helperText="GitLab project path (group/project) or full project URL on any host"
                />
                <TextField
                  label="GitLab API URL (optional)"
                  fullWidth
                  value={gitlabApiUrl}
                  onChange={e => setGitlabApiUrl(e.target.value)}
                  placeholder="https://gitlab.example.com"
                  helperText="Leave blank for gitlab.com; use for self-managed instances"
                />
              </>
            )}

            {providerType === 'asana' && (
              <TextField
                label="Workspace GID (optional)"
                fullWidth
                value={workspaceGid}
                onChange={e => setWorkspaceGid(e.target.value)}
                placeholder="1234567890"
                helperText="Optional Asana workspace scope for search and import"
              />
            )}

            <Box>
              <Button
                variant="outlined"
                size="medium"
                onClick={handleTestConnection}
                disabled={Boolean(
                  testingConnection ||
                  loading ||
                  !authToken ||
                  (providerType === 'github' && !repositoryUrl.trim()) ||
                  (providerType === 'gitlab' && !projectNamespace.trim()) ||
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
                    (!instanceUrl || !username))
                )}
                sx={{ minWidth: 150 }}
              >
                {testingConnection ? 'Testing...' : 'Test Connection'}
              </Button>
              {testResult && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    borderRadius: BORDER_RADIUS.xs,
                    px: '30px',
                    py: '12px',
                    mt: 2,
                    ...(testResult.is_authenticated === 'Yes'
                      ? {
                          backgroundColor: alpha(
                            theme.palette.primary.main,
                            0.12
                          ),
                          color: theme.palette.primary.main,
                        }
                      : {
                          backgroundColor: alpha(
                            theme.palette.error.main,
                            0.12
                          ),
                          color: theme.palette.error.main,
                        }),
                  }}
                >
                  <Box
                    sx={{
                      flexShrink: 0,
                      pr: '12px',
                      pt: '7px',
                      pb: '7px',
                      display: 'flex',
                    }}
                  >
                    {testResult.is_authenticated === 'Yes' ? (
                      <CheckCircleIcon
                        sx={{ fontSize: 22, color: 'inherit' }}
                      />
                    ) : (
                      <ErrorIcon sx={{ fontSize: 22, color: 'inherit' }} />
                    )}
                  </Box>
                  <Box
                    sx={{
                      flex: 1,
                      py: '8px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <Typography
                      variant="h6"
                      sx={{
                        fontWeight: 700,
                        lineHeight: '25px',
                        color: 'inherit',
                      }}
                    >
                      {testResult.is_authenticated === 'Yes'
                        ? 'Connection Successful'
                        : 'Connection Failed'}
                    </Typography>
                    <Typography variant="body1" sx={{ color: 'inherit' }}>
                      {testResult.message}
                    </Typography>
                  </Box>
                </Box>
              )}
            </Box>
          </Stack>
        )}

        {/* Jira Space Selection */}
        {showSpaceSelector &&
          availableSpaces.length > 0 &&
          providerType === 'jira' && (
            <Stack spacing={3}>
              <Box>
                <Typography sx={sectionHeadingSx}>Space Selection</Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ mt: 0.5, display: 'block' }}
                >
                  Select the Jira space for issue creation
                </Typography>
              </Box>
              <FormControl fullWidth required>
                <InputLabel>Jira Space</InputLabel>
                <Select
                  value={selectedSpaceKey}
                  onChange={e => setSelectedSpaceKey(e.target.value)}
                  label="Jira Space"
                  required
                >
                  {availableSpaces.map(space => (
                    <MenuItem key={space.key} value={space.key}>
                      {space.name} ({space.key})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>
          )}

        {!isEditMode && !connectionTested && !testResult && (
          <Alert severity="info">
            Please test the connection before saving the tool configuration.
          </Alert>
        )}
        {isEditMode &&
          (credentialsModified || scopeMetadataModified) &&
          !connectionTested &&
          !testResult && (
            <Alert severity="info">
              {credentialsModified
                ? 'Please test the connection with the updated credentials before saving.'
                : 'Please test the connection with the updated scope before saving.'}
            </Alert>
          )}
      </Stack>
    </BaseDrawer>
  );
}
