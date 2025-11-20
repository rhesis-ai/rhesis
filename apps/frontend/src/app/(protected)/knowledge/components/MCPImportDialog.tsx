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
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import SearchIcon from '@mui/icons-material/Search';
import SaveIcon from '@mui/icons-material/Save';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { MCPItem } from '@/utils/api-client/services-client';
import { Tool } from '@/utils/api-client/interfaces/tool';

interface MCPImportDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  sessionToken: string;
  tool?: Tool | null;
}

export default function MCPImportDialog({
  open,
  onClose,
  onSuccess,
  sessionToken,
  tool,
}: MCPImportDialogProps) {
  const theme = useTheme();
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<MCPItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const notifications = useNotifications();

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
      const errorMessage =
        err instanceof Error
          ? err.message
          : 'Failed to search. Please try again.';
      setError(errorMessage);
      notifications.show('Search failed: ' + errorMessage, {
        severity: 'error',
        autoHideDuration: 6000,
      });
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
        // Extract content
        const result = await servicesClient.extractMCP(item.id, tool.id);

        // Save as source
        await sourcesClient.createSourceFromContent(
          item.title,
          result.content,
          undefined, // No description
          {
            source_type: tool.tool_provider_type?.type_value || 'MCP',
            mcp_tool_id: tool.id,
            mcp_id: item.id,
            url: item.url,
            imported_at: new Date().toISOString(),
          }
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
    if (!searching && !importing) {
      setSearchQuery('');
      setSearchResults([]);
      setSelectedIds(new Set());
      setError(null);
      onClose();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !searching) {
      handleSearch();
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
            <Typography variant="h6">
              Import from{' '}
              {tool?.tool_provider_type?.type_value
                ? tool.tool_provider_type.type_value.charAt(0).toUpperCase() +
                  tool.tool_provider_type.type_value.slice(1)
                : 'MCP'}
            </Typography>
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
          {/* Search Section */}
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Search{' '}
              {tool?.tool_provider_type?.type_value
                ? tool.tool_provider_type.type_value.charAt(0).toUpperCase() +
                  tool.tool_provider_type.type_value.slice(1)
                : 'MCP'}{' '}
              Pages
            </Typography>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <TextField
                fullWidth
                placeholder="Enter search query..."
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
                  searching ? <CircularProgress size={20} /> : <SearchIcon />
                }
                sx={{ minWidth: '120px' }}
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
                                    tool.tool_provider_type.type_value.slice(1)
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
              <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
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
              </Box>
            </Box>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose} disabled={isProcessing}>
          Cancel
        </Button>
      </DialogActions>
    </Dialog>
  );
}
