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
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import SearchIcon from '@mui/icons-material/Search';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import SaveIcon from '@mui/icons-material/Save';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { MCPItem } from '@/utils/api-client/services-client';

interface MCPImportDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  sessionToken: string;
}

interface ExtractedPage {
  id: string;
  title: string;
  url: string;
  content: string;
}

const MCP_SERVER_NAME = 'notionApi';

export default function MCPImportDialog({
  open,
  onClose,
  onSuccess,
  sessionToken,
}: MCPImportDialogProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<MCPItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [extracting, setExtracting] = useState(false);
  const [extractedPages, setExtractedPages] = useState<ExtractedPage[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const notifications = useNotifications();

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setError('Please enter a search query');
      return;
    }

    try {
      setSearching(true);
      setError(null);
      setSearchResults([]);
      setSelectedIds(new Set());
      setExtractedPages([]);

      const clientFactory = new ApiClientFactory(sessionToken);
      const servicesClient = clientFactory.getServicesClient();

      const results = await servicesClient.searchMCP(
        searchQuery.trim(),
        MCP_SERVER_NAME
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

  const handleExtract = async () => {
    if (selectedIds.size === 0) {
      setError('Please select at least one page to extract');
      return;
    }

    try {
      setExtracting(true);
      setError(null);

      const clientFactory = new ApiClientFactory(sessionToken);
      const servicesClient = clientFactory.getServicesClient();

      // Extract all selected pages in parallel
      const selectedItems = searchResults.filter(item =>
        selectedIds.has(item.id)
      );
      const extractPromises = selectedItems.map(async item => {
        const result = await servicesClient.extractMCP(
          item.id,
          MCP_SERVER_NAME
        );
        return {
          id: item.id,
          title: item.title,
          url: item.url,
          content: result.content,
        };
      });

      const extracted = await Promise.all(extractPromises);
      setExtractedPages(extracted);

      notifications.show(
        `Successfully extracted ${extracted.length} page${extracted.length > 1 ? 's' : ''}`,
        {
          severity: 'success',
          autoHideDuration: 4000,
        }
      );
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : 'Failed to extract content. Please try again.';
      setError(errorMessage);
      notifications.show('Extraction failed: ' + errorMessage, {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setExtracting(false);
    }
  };

  const handleSaveAsSources = async () => {
    if (extractedPages.length === 0) {
      setError('No pages to save');
      return;
    }

    try {
      setSaving(true);
      setError(null);

      const clientFactory = new ApiClientFactory(sessionToken);
      const sourcesClient = clientFactory.getSourcesClient();

      // Create a source for each extracted page
      const savePromises = extractedPages.map(page =>
        sourcesClient.createSourceFromContent(
          page.title,
          page.content,
          undefined, // No description
          {
            source_type: 'Notion',
            mcp_server: MCP_SERVER_NAME,
            mcp_id: page.id,
            url: page.url,
            imported_at: new Date().toISOString(),
          }
        )
      );

      await Promise.all(savePromises);

      notifications.show(
        `Successfully saved ${extractedPages.length} source${extractedPages.length > 1 ? 's' : ''}`,
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
          : 'Failed to save sources. Please try again.';
      setError(errorMessage);
      notifications.show('Save failed: ' + errorMessage, {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    if (!searching && !extracting && !saving) {
      setSearchQuery('');
      setSearchResults([]);
      setSelectedIds(new Set());
      setExtractedPages([]);
      setError(null);
      onClose();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !searching) {
      handleSearch();
    }
  };

  const isProcessing = searching || extracting || saving;

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
            <Typography variant="h6">Import from Notion</Typography>
          </Box>
          <IconButton onClick={handleClose} disabled={isProcessing}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 1 }}>
          {/* Search Section */}
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Search Notion Pages
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
                disabled={isProcessing}
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
          {searchResults.length > 0 && extractedPages.length === 0 && (
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
                          disabled={extracting}
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
                            secondary={item.url}
                            primaryTypographyProps={{ fontWeight: 500 }}
                            secondaryTypographyProps={{
                              sx: {
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              },
                            }}
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
                  onClick={handleExtract}
                  disabled={selectedIds.size === 0 || extracting}
                  startIcon={
                    extracting ? (
                      <CircularProgress size={20} />
                    ) : (
                      <CloudDownloadIcon />
                    )
                  }
                >
                  {extracting
                    ? 'Extracting...'
                    : `Extract ${selectedIds.size} Page${selectedIds.size !== 1 ? 's' : ''}`}
                </Button>
              </Box>
            </Box>
          )}

          {/* Preview Section */}
          {extractedPages.length > 0 && (
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Extracted Content Preview ({extractedPages.length} page
                {extractedPages.length !== 1 ? 's' : ''})
              </Typography>
              <Paper
                variant="outlined"
                sx={{
                  maxHeight: '400px',
                  overflow: 'auto',
                  p: 2,
                  bgcolor: 'grey.50',
                }}
              >
                {extractedPages.map((page, index) => (
                  <Box key={page.id}>
                    {index > 0 && <Divider sx={{ my: 2 }} />}
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle1" fontWeight={600}>
                        {page.title}
                      </Typography>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{
                          display: 'block',
                          mb: 1,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {page.url}
                      </Typography>
                      <Typography
                        variant="body2"
                        component="pre"
                        sx={{
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          fontFamily: 'monospace',
                          fontSize: '0.875rem',
                          maxHeight: '200px',
                          overflow: 'auto',
                          bgcolor: 'white',
                          p: 1,
                          borderRadius: 1,
                        }}
                      >
                        {page.content.slice(0, 500)}
                        {page.content.length > 500 && '...'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {page.content.length} characters
                      </Typography>
                    </Box>
                  </Box>
                ))}
              </Paper>
            </Box>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose} disabled={isProcessing}>
          Cancel
        </Button>
        {extractedPages.length > 0 && (
          <Button
            variant="contained"
            onClick={handleSaveAsSources}
            disabled={saving}
            startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
          >
            {saving ? 'Saving...' : 'Save as Sources'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
