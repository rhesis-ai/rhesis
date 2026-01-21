'use client';

import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Alert,
  CircularProgress,
  IconButton,
  Checkbox,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Paper,
  useTheme,
  Tabs,
  Tab,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import SearchIcon from '@mui/icons-material/Search';
import SaveIcon from '@mui/icons-material/Save';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import LinkIcon from '@mui/icons-material/Link';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { MCPItem } from '@/utils/api-client/services-client';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { UUID } from 'crypto';
import { getErrorMessage } from '@/utils/entity-error-handler';

type ImportMode = 'search' | 'url';

interface UrlImportItem {
  id: string;
  url: string;
  status: 'pending' | 'importing' | 'success' | 'error';
  error?: string;
  title?: string;
}

interface MCPImportDialogProps {
  open: boolean;
  onClose: () => void;
  onBack?: () => void;
  onSuccess?: () => void;
  sessionToken: string;
  tool?: Tool | null;
}

export default function MCPImportDialog({
  open,
  onClose,
  onBack,
  onSuccess,
  sessionToken,
  tool,
}: MCPImportDialogProps) {
  const theme = useTheme();
  const [importMode, setImportMode] = useState<ImportMode>('search');
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<MCPItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toolSourceTypeId, setToolSourceTypeId] = useState<UUID | undefined>(
    undefined
  );
  const notifications = useNotifications();

  // URL import state - array of URL items
  const [urlItems, setUrlItems] = useState<UrlImportItem[]>([
    { id: crypto.randomUUID(), url: '', status: 'pending' },
  ]);

  // Fetch Tool SourceType ID when component mounts or tool changes
  React.useEffect(() => {
    const fetchToolSourceType = async () => {
      if (!sessionToken) return;

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const typeLookupClient = clientFactory.getTypeLookupClient();

        // Fetch Tool SourceType using filter
        const toolSourceTypes = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'SourceType' and type_value eq 'Tool'",
          limit: 1,
        });

        if (toolSourceTypes.length > 0) {
          setToolSourceTypeId(toolSourceTypes[0].id as UUID);
        }
      } catch (err) {
        console.error('Failed to fetch Tool SourceType:', err);
        // Don't set error state here - we'll handle it during import
      }
    };

    fetchToolSourceType();
  }, [sessionToken]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setError('Please enter a search query');
      return;
    }

    if (!tool) {
      setError('No MCP tool selected');
      return;
    }

    try {
      setSearching(true);
      setError(null);
      setSearchResults([]);
      setSelectedIds(new Set());

      const clientFactory = new ApiClientFactory(sessionToken);
      const servicesClient = clientFactory.getServicesClient();

      const results = await servicesClient.searchMCP(
        searchQuery.trim(),
        tool.id
      );

      setSearchResults(results);

      if (results.length === 0) {
        setError('No results found. Try a different search query.');
      }
    } catch (err) {
      // Use getErrorMessage to extract clean error messages from API responses
      // This handles error.data.detail and provides user-friendly messages
      const errorMessage =
        getErrorMessage(err) || 'Failed to search. Please try again.';
      setError(errorMessage);
    } finally {
      setSearching(false);
    }
  };

  const handleToggleSelection = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleSelectAll = () => {
    if (selectedIds.size === searchResults.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(searchResults.map(item => item.id)));
    }
  };

  const handleImportAsSources = async () => {
    if (selectedIds.size === 0) {
      setError('Please select at least one page to import');
      return;
    }

    try {
      setImporting(true);
      setError(null);

      const clientFactory = new ApiClientFactory(sessionToken);
      const servicesClient = clientFactory.getServicesClient();
      const sourcesClient = clientFactory.getSourcesClient();

      // Extract and save all selected pages
      const selectedItems = searchResults.filter(item =>
        selectedIds.has(item.id)
      );

      if (!tool) {
        setError('No MCP tool selected');
        return;
      }

      const importPromises = selectedItems.map(async item => {
        // Extract content - prefer URL if available, otherwise use ID
        const result = await servicesClient.extractMCP(
          item.url ? { url: item.url } : { id: item.id },
          tool.id
        );

        // Save as source
        await sourcesClient.createSourceFromContent(
          item.title,
          result.content,
          undefined, // No description
          {
            provider: tool.tool_provider_type?.type_value || 'mcp',
            mcp_tool_id: tool.id,
            mcp_id: item.id,
            url: item.url,
            imported_at: new Date().toISOString(),
          },
          toolSourceTypeId
        );
      });

      await Promise.all(importPromises);

      const providerName = tool.tool_provider_type?.type_value || 'MCP';
      notifications.show(
        `Successfully imported ${selectedItems.length} source${selectedItems.length > 1 ? 's' : ''} from ${providerName}`,
        {
          severity: 'success',
          autoHideDuration: 4000,
        }
      );

      // Reset and close
      handleClose();
      onSuccess?.();
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : 'Failed to import sources. Please try again.';
      setError(errorMessage);
      notifications.show('Import failed: ' + errorMessage, {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setImporting(false);
    }
  };

  const handleClose = () => {
    if (!isProcessing) {
      setSearchQuery('');
      setSearchResults([]);
      setSelectedIds(new Set());
      setUrlItems([{ id: crypto.randomUUID(), url: '', status: 'pending' }]);
      setError(null);
      setImportMode('search');
      onClose();
    }
  };

  const handleBack = () => {
    if (!isProcessing) {
      setSearchQuery('');
      setSearchResults([]);
      setSelectedIds(new Set());
      setUrlItems([{ id: crypto.randomUUID(), url: '', status: 'pending' }]);
      setError(null);
      setImportMode('search');
      if (onBack) {
        onBack();
      } else {
        onClose();
      }
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !searching) {
      handleSearch();
    }
  };

  // Helper function to extract title from URL
  const extractTitleFromUrl = (url: string): string => {
    try {
      const urlObj = new URL(url);
      const hostname = urlObj.hostname;
      const pathname = urlObj.pathname;

      // GitHub patterns
      if (hostname.includes('github.com')) {
        const patterns = [
          {
            regex: /\/pull\/(\d+)/,
            format: (m: RegExpMatchArray) => `PR #${m[1]}`,
          },
          {
            regex: /\/issues\/(\d+)/,
            format: (m: RegExpMatchArray) => `Issue #${m[1]}`,
          },
          {
            regex: /\/discussions\/(\d+)/,
            format: (m: RegExpMatchArray) => `Discussion #${m[1]}`,
          },
          {
            regex: /\/blob\/[^/]+\/(.+)$/,
            format: (m: RegExpMatchArray) => m[1].split('/').pop() || 'File',
          },
          {
            regex: /\/commit\/([a-f0-9]+)/,
            format: (m: RegExpMatchArray) => `Commit ${m[1].substring(0, 7)}`,
          },
        ];

        for (const { regex, format } of patterns) {
          const match = pathname.match(regex);
          if (match) return format(match);
        }

        // Fallback: repo name
        const parts = pathname.split('/').filter(p => p);
        if (parts.length >= 2) {
          return `${parts[0]}/${parts[1]}`;
        }
      }

      // Notion patterns
      if (hostname.includes('notion.so') || hostname.includes('notion.site')) {
        // Extract page ID from URL
        const pageIdMatch = pathname.match(/([a-f0-9]{32})/);
        if (pageIdMatch) {
          return `Notion Page`;
        }
      }

      // Generic fallback: use last path segment or hostname
      const parts = pathname.split('/').filter(p => p);
      if (parts.length > 0) {
        return parts[parts.length - 1] || hostname;
      }

      return hostname;
    } catch (e) {
      return 'Resource';
    }
  };

  // Validate URL format (basic URL validation)
  const isValidUrl = (url: string): boolean => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  // Add a new empty URL field
  const handleAddUrlField = () => {
    setUrlItems([
      ...urlItems,
      { id: crypto.randomUUID(), url: '', status: 'pending' },
    ]);
  };

  // Update URL input for a specific item
  const handleUrlChange = (id: string, url: string) => {
    setUrlItems(
      urlItems.map(item => (item.id === id ? { ...item, url } : item))
    );
  };

  // Handle importing all URLs
  const handleImportUrls = async () => {
    if (!tool) {
      setError('No MCP tool selected');
      return;
    }

    // Get all pending URLs
    const pendingItems = urlItems.filter(
      item => item.url.trim() && item.status === 'pending'
    );

    if (pendingItems.length === 0) {
      setError('Please add at least one URL to import');
      return;
    }

    // Validate all URLs first
    const invalidItems = pendingItems.filter(item => !isValidUrl(item.url));
    if (invalidItems.length > 0) {
      setUrlItems(
        urlItems.map(item =>
          invalidItems.find(i => i.id === item.id)
            ? {
                ...item,
                status: 'error',
                error: 'Invalid URL format. Please enter a valid URL.',
              }
            : item
        )
      );
      return;
    }

    setImporting(true);
    setError(null);

    const clientFactory = new ApiClientFactory(sessionToken);
    const servicesClient = clientFactory.getServicesClient();
    const sourcesClient = clientFactory.getSourcesClient();

    let successCount = 0;
    let errorCount = 0;

    // Process each URL
    for (const item of pendingItems) {
      try {
        // Set importing status
        setUrlItems(prev =>
          prev.map(i => (i.id === item.id ? { ...i, status: 'importing' } : i))
        );

        // Extract content from URL
        const result = await servicesClient.extractMCP(
          { url: item.url },
          tool.id
        );

        const title = extractTitleFromUrl(item.url);

        // Save as source
        await sourcesClient.createSourceFromContent(
          title,
          result.content,
          undefined,
          {
            provider: tool.tool_provider_type?.type_value || 'mcp',
            mcp_tool_id: tool.id,
            url: item.url,
            imported_at: new Date().toISOString(),
          },
          toolSourceTypeId
        );

        // Update status to success
        setUrlItems(prev =>
          prev.map(i =>
            i.id === item.id ? { ...i, status: 'success', title } : i
          )
        );

        successCount++;
      } catch (err) {
        const errorMessage =
          getErrorMessage(err) || 'Failed to import this URL';

        // Update status to error
        setUrlItems(prev =>
          prev.map(i =>
            i.id === item.id
              ? { ...i, status: 'error', error: errorMessage }
              : i
          )
        );

        errorCount++;
      }
    }

    setImporting(false);

    // Show summary notification
    const providerName = tool.tool_provider_type?.type_value
      ? tool.tool_provider_type.type_value.charAt(0).toUpperCase() +
        tool.tool_provider_type.type_value.slice(1)
      : 'MCP';

    if (successCount > 0) {
      notifications.show(
        `Successfully imported ${successCount} source${successCount > 1 ? 's' : ''} from ${providerName}`,
        {
          severity: 'success',
          autoHideDuration: 4000,
        }
      );
    }

    if (errorCount > 0) {
      notifications.show(
        `Failed to import ${errorCount} URL${errorCount > 1 ? 's' : ''}. Check the error messages above.`,
        {
          severity: 'error',
          autoHideDuration: 6000,
        }
      );
    }

    // If all succeeded, show success and allow closing
    if (successCount > 0 && errorCount === 0) {
      onSuccess?.();
    }
  };

  const isProcessing = searching || importing;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { minHeight: '600px', maxHeight: '90vh' },
      }}
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center" gap={1}>
            <SearchIcon />
            <Typography variant="h6">Import Sources</Typography>
          </Box>
          <IconButton onClick={handleClose} disabled={isProcessing}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 1 }}>
          {!tool && (
            <Alert severity="error">
              No MCP tool selected. Please select a tool first.
            </Alert>
          )}

          {/* Import Mode Tabs */}
          <Tabs
            value={importMode}
            onChange={(_, newValue) => {
              setImportMode(newValue);
              setError(null);
            }}
            sx={{ borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab
              label="Search"
              value="search"
              icon={<SearchIcon />}
              iconPosition="start"
            />
            <Tab
              label="Direct Link"
              value="url"
              icon={<LinkIcon />}
              iconPosition="start"
            />
          </Tabs>

          {/* Search Section */}
          {importMode === 'search' && (
            <>
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  {tool?.tool_provider_type?.type_value === 'github' ? (
                    <>
                      Search{' '}
                      {tool.tool_metadata?.repository ? (
                        <strong>
                          {tool.tool_metadata.repository.full_name}
                        </strong>
                      ) : (
                        'GitHub'
                      )}
                    </>
                  ) : (
                    <>
                      Search{' '}
                      {tool?.tool_provider_type?.type_value
                        ? tool.tool_provider_type.type_value
                            .charAt(0)
                            .toUpperCase() +
                          tool.tool_provider_type.type_value.slice(1)
                        : 'MCP'}{' '}
                      Pages
                    </>
                  )}
                </Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <TextField
                    fullWidth
                    placeholder="Describe the content you want to import..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    onKeyPress={handleKeyPress}
                    disabled={isProcessing}
                    autoFocus
                  />
                  <Button
                    variant="contained"
                    onClick={handleSearch}
                    disabled={isProcessing || !tool}
                    startIcon={
                      searching ? (
                        <CircularProgress size={20} />
                      ) : (
                        <SearchIcon />
                      )
                    }
                  >
                    {searching ? 'Searching...' : 'Search'}
                  </Button>
                </Box>
              </Box>

              {/* Error Display */}
              {error && (
                <Alert severity="error" onClose={() => setError(null)}>
                  {error}
                </Alert>
              )}

              {/* Results Section */}
              {searchResults.length > 0 && (
                <Box>
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      mb: 1,
                    }}
                  >
                    <Typography variant="subtitle2">
                      Search Results ({searchResults.length})
                    </Typography>
                    <Button size="small" onClick={handleSelectAll}>
                      {selectedIds.size === searchResults.length
                        ? 'Deselect All'
                        : 'Select All'}
                    </Button>
                  </Box>
                  <Paper
                    variant="outlined"
                    sx={{ maxHeight: '300px', overflow: 'auto' }}
                  >
                    <List dense>
                      {searchResults.map((item, index) => (
                        <React.Fragment key={item.id}>
                          {index > 0 && <Divider />}
                          <ListItem disablePadding>
                            <ListItemButton
                              onClick={() => handleToggleSelection(item.id)}
                              disabled={importing}
                            >
                              <ListItemIcon>
                                <Checkbox
                                  edge="start"
                                  checked={selectedIds.has(item.id)}
                                  tabIndex={-1}
                                  disableRipple
                                />
                              </ListItemIcon>
                              <ListItemText
                                primary={item.title}
                                secondary={
                                  <Box
                                    component="a"
                                    href={item.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    onClick={e => e.stopPropagation()}
                                    sx={{
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      gap: 0.5,
                                      color: 'primary.main',
                                      textDecoration: 'none',
                                      fontSize: theme.typography.body2.fontSize,
                                      '&:hover': {
                                        textDecoration: 'underline',
                                      },
                                    }}
                                  >
                                    Open in{' '}
                                    {tool?.tool_provider_type?.type_value
                                      ? tool.tool_provider_type.type_value
                                          .charAt(0)
                                          .toUpperCase() +
                                        tool.tool_provider_type.type_value.slice(
                                          1
                                        )
                                      : 'MCP'}
                                    <OpenInNewIcon
                                      sx={{ fontSize: theme.iconSizes.small }}
                                    />
                                  </Box>
                                }
                                primaryTypographyProps={{ fontWeight: 500 }}
                              />
                            </ListItemButton>
                          </ListItem>
                        </React.Fragment>
                      ))}
                    </List>
                  </Paper>
                </Box>
              )}
            </>
          )}

          {/* Direct Link Section */}
          {importMode === 'url' && (
            <>
              <Box>
                {/* URL Input Fields */}
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {urlItems.map((item, index) => (
                    <TextField
                      key={item.id}
                      fullWidth
                      placeholder={`Paste ${tool?.tool_provider_type?.type_value || 'resource'} URL...`}
                      value={item.url}
                      onChange={e => handleUrlChange(item.id, e.target.value)}
                      disabled={item.status !== 'pending'}
                      error={item.status === 'error'}
                      helperText={
                        item.status === 'error'
                          ? item.error
                          : item.status === 'success'
                            ? `Imported as: ${item.title}`
                            : ''
                      }
                      sx={{
                        '& .MuiInputBase-root': {
                          backgroundColor:
                            item.status === 'success'
                              ? theme.palette.success.light + '20'
                              : item.status === 'error'
                                ? theme.palette.error.light + '20'
                                : undefined,
                        },
                      }}
                      InputProps={{
                        endAdornment:
                          item.status === 'success' ? (
                            <CheckCircleIcon color="success" />
                          ) : item.status === 'error' ? (
                            <ErrorIcon color="error" />
                          ) : null,
                      }}
                    />
                  ))}

                  {/* Add More Button */}
                  <Button
                    variant="outlined"
                    startIcon={<AddIcon />}
                    onClick={handleAddUrlField}
                    sx={{ alignSelf: 'flex-start' }}
                  >
                    Add Another URL
                  </Button>
                </Box>
              </Box>

              {/* Error Display */}
              {error && (
                <Alert severity="error" onClose={() => setError(null)}>
                  {error}
                </Alert>
              )}
            </>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 3, pt: 1, justifyContent: 'space-between' }}>
        <Button
          onClick={handleBack}
          disabled={isProcessing}
          startIcon={<ArrowBackIcon />}
        >
          Back
        </Button>

        {/* Search mode import button */}
        {importMode === 'search' && searchResults.length > 0 && (
          <Button
            variant="contained"
            onClick={handleImportAsSources}
            disabled={selectedIds.size === 0 || importing}
            startIcon={
              importing ? <CircularProgress size={20} /> : <SaveIcon />
            }
          >
            {importing
              ? 'Importing...'
              : `Import ${selectedIds.size} as Source${selectedIds.size !== 1 ? 's' : ''}`}
          </Button>
        )}

        {/* URL mode import button */}
        {importMode === 'url' && (
          <Button
            variant="contained"
            onClick={handleImportUrls}
            disabled={
              importing ||
              !urlItems.some(
                item => item.url.trim() && item.status === 'pending'
              ) ||
              !tool
            }
            startIcon={
              importing ? <CircularProgress size={20} /> : <SaveIcon />
            }
          >
            {importing
              ? 'Importing...'
              : `Import ${urlItems.filter(item => item.url.trim() && item.status === 'pending').length} URL${urlItems.filter(item => item.url.trim() && item.status === 'pending').length !== 1 ? 's' : ''}`}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
