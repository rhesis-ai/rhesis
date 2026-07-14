'use client';

import React, {
  useState,
  useCallback,
  useEffect,
  useMemo,
  forwardRef,
  useImperativeHandle,
} from 'react';
import {
  Button,
  TextField,
  Box,
  Alert,
  CircularProgress,
  FormControlLabel,
  Checkbox,
  Typography,
  List,
  ListItem,
  ListItemText,
  Divider,
  Paper,
  Link,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { safeRandomUUID } from '@/utils/uuid';
import { useNotifications } from '@/components/common/NotificationContext';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { UUID } from 'crypto';
import { getErrorMessage } from '@/utils/entity-error-handler';
import { ExtractedSource } from '@/utils/api-client/services-client';
import { useTypeLookups } from '@/hooks/useLookups';
import {
  drawerOutlinedFieldSx,
  drawerOutlineButtonSx,
} from '@/components/common/drawerFormFieldSx';

export interface ToolImportPanelHandle {
  triggerPrimary: () => Promise<void>;
}

export interface PanelFooterState {
  primaryLabel: string;
  primaryLoading: boolean;
  primaryDisabled: boolean;
  isPreview: boolean;
  onBack: () => void;
}

interface UrlItem {
  id: string;
  url: string;
  status: 'pending' | 'importing' | 'success' | 'error';
  error?: string;
  title?: string;
}

interface PreviewItem {
  urlItemId: string;
  inputUrl: string;
  sources: ExtractedSource[];
}

interface ToolImportPanelProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  sessionToken: string;
  tool?: Tool | null;
  onFooterStateChange: (state: PanelFooterState) => void;
}

const PREVIEW_THRESHOLD = 5;

function getProviderLabel(provider: string): {
  checkbox: string;
  placeholder: string;
} {
  if (provider === 'notion') {
    return {
      checkbox: 'Include subpages',
      placeholder: 'Paste Notion page URL...',
    };
  }
  if (provider === 'github') {
    return {
      checkbox: 'Include subdirectories and files',
      placeholder: 'Paste GitHub file or directory URL...',
    };
  }
  if (provider === 'gitlab') {
    return {
      checkbox: '',
      placeholder: 'Paste GitLab issue or merge request URL...',
    };
  }
  if (provider === 'shortcut') {
    return {
      checkbox: '',
      placeholder: 'Paste Shortcut story or epic URL...',
    };
  }
  if (provider === 'asana') {
    return {
      checkbox: '',
      placeholder: 'Paste Asana task or project URL...',
    };
  }
  return {
    checkbox: 'Include linked items',
    placeholder: 'Paste URL...',
  };
}

const ToolImportPanel = forwardRef<ToolImportPanelHandle, ToolImportPanelProps>(
  function ToolImportPanel(
    { open, onClose, onSuccess, sessionToken, tool, onFooterStateChange },
    ref
  ) {
    const [importing, setImporting] = useState(false);
    const [previewing, setPreviewing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [includeChildren, setIncludeChildren] = useState(false);
    const [previewItems, setPreviewItems] = useState<PreviewItem[] | null>(
      null
    );
    const notifications = useNotifications();

    const [urlItems, setUrlItems] = useState<UrlItem[]>([
      { id: safeRandomUUID(), url: '', status: 'pending' },
    ]);

    const { data: toolSourceTypes } = useTypeLookups(
      sessionToken ?? '',
      "type_name eq 'SourceType' and type_value eq 'Tool'",
      open && !!sessionToken
    );
    const toolSourceTypeId = toolSourceTypes?.[0]?.id as UUID | undefined;

    const pendingItems = useMemo(
      () =>
        urlItems.filter(item => item.url.trim() && item.status === 'pending'),
      [urlItems]
    );

    const totalPreviewCount =
      previewItems?.reduce((sum, p) => sum + p.sources.length, 0) ?? 0;

    const handleBack = useCallback(() => {
      if (importing) return;
      if (previewItems) {
        setPreviewItems(null);
        setUrlItems(prev =>
          prev.map(i => ({
            ...i,
            status: 'pending',
            error: undefined,
            title: undefined,
          }))
        );
      } else {
        setUrlItems([{ id: safeRandomUUID(), url: '', status: 'pending' }]);
        setError(null);
        setIncludeChildren(false);
        setPreviewItems(null);
        onClose();
      }
    }, [importing, previewItems, onClose]);

    const handleUrlChange = (id: string, url: string) => {
      setUrlItems(prev =>
        prev.map(item =>
          item.id === id
            ? {
                ...item,
                url,
                status: 'pending',
                error: undefined,
                title: undefined,
              }
            : item
        )
      );
    };

    const handleAddUrl = () => {
      setUrlItems(prev => [
        ...prev,
        { id: safeRandomUUID(), url: '', status: 'pending' },
      ]);
    };

    const isValidUrl = (url: string): boolean => {
      try {
        new URL(url);
        return true;
      } catch {
        return false;
      }
    };

    const commitImport = useCallback(
      async (items: PreviewItem[]) => {
        if (!tool) return;

        setImporting(true);
        setError(null);

        const clientFactory = new ApiClientFactory(sessionToken);
        const sourcesClient = clientFactory.getSourcesClient();

        const provider = tool.tool_provider_type?.type_value ?? 'tool';
        let successCount = 0;
        let errorCount = 0;

        for (const preview of items) {
          try {
            for (const source of preview.sources) {
              await sourcesClient.createSourceFromContent(
                source.title || preview.inputUrl,
                source.content,
                undefined,
                {
                  provider,
                  mcp_tool_id: tool.id,
                  url: source.url ?? preview.inputUrl,
                  imported_at: new Date().toISOString(),
                },
                toolSourceTypeId
              );
            }
            setUrlItems(prev =>
              prev.map(i =>
                i.id === preview.urlItemId
                  ? {
                      ...i,
                      status: 'success',
                      title: preview.sources[0]?.title ?? preview.inputUrl,
                    }
                  : i
              )
            );
            successCount += preview.sources.length;
          } catch (err) {
            const msg = getErrorMessage(err) || 'Failed to import';
            setUrlItems(prev =>
              prev.map(i =>
                i.id === preview.urlItemId
                  ? { ...i, status: 'error', error: msg }
                  : i
              )
            );
            errorCount++;
          }
        }

        setImporting(false);
        setPreviewItems(null);

        const label = provider.charAt(0).toUpperCase() + provider.slice(1);

        if (successCount > 0) {
          notifications.show(
            `Successfully imported ${successCount} source${successCount !== 1 ? 's' : ''} from ${label}`,
            { severity: 'success', autoHideDuration: 4000 }
          );
        }
        if (errorCount > 0) {
          notifications.show(
            `Failed to import ${errorCount} item${errorCount !== 1 ? 's' : ''}. Check the errors above.`,
            { severity: 'error', autoHideDuration: 6000 }
          );
        }
        if (successCount > 0 && errorCount === 0) onSuccess?.();
      },
      [tool, sessionToken, toolSourceTypeId, notifications, onSuccess]
    );

    const handleImportOrPreview = useCallback(async () => {
      if (!tool) {
        setError('No tool selected');
        return;
      }
      if (pendingItems.length === 0) {
        setError('Please add at least one URL');
        return;
      }

      const invalidItems = pendingItems.filter(item => !isValidUrl(item.url));
      if (invalidItems.length > 0) {
        setUrlItems(prev =>
          prev.map(item =>
            invalidItems.find(i => i.id === item.id)
              ? { ...item, status: 'error', error: 'Invalid URL' }
              : item
          )
        );
        return;
      }

      setPreviewing(true);
      setError(null);

      const clientFactory = new ApiClientFactory(sessionToken);
      const servicesClient = clientFactory.getServicesClient();

      const fetched: PreviewItem[] = [];
      let fetchError = false;

      for (const item of pendingItems) {
        try {
          const result = await servicesClient.extractTool(tool.id, {
            url: item.url,
            include_children: includeChildren,
          });
          fetched.push({
            urlItemId: item.id,
            inputUrl: item.url,
            sources: result.sources,
          });
        } catch (err) {
          const msg = getErrorMessage(err) || 'Failed to fetch this URL';
          setUrlItems(prev =>
            prev.map(i =>
              i.id === item.id ? { ...i, status: 'error', error: msg } : i
            )
          );
          fetchError = true;
        }
      }

      setPreviewing(false);

      if (fetchError && fetched.length === 0) return;

      const total = fetched.reduce((sum, p) => sum + p.sources.length, 0);

      if (total > PREVIEW_THRESHOLD) {
        setPreviewItems(fetched);
      } else {
        await commitImport(fetched);
      }
    }, [tool, pendingItems, includeChildren, sessionToken, commitImport]);

    useImperativeHandle(
      ref,
      () => ({
        triggerPrimary: async () => {
          if (previewItems) {
            await commitImport(previewItems);
          } else {
            await handleImportOrPreview();
          }
        },
      }),
      [previewItems, commitImport, handleImportOrPreview]
    );

    useEffect(() => {
      const count = pendingItems.length;
      const state: PanelFooterState = previewItems
        ? {
            primaryLabel: importing
              ? 'Importing...'
              : `Import ${totalPreviewCount} source${totalPreviewCount !== 1 ? 's' : ''}`,
            primaryLoading: importing,
            primaryDisabled: importing,
            isPreview: true,
            onBack: handleBack,
          }
        : {
            primaryLabel: previewing
              ? 'Fetching...'
              : `Import ${count} URL${count !== 1 ? 's' : ''}`,
            primaryLoading: previewing,
            primaryDisabled: previewing || importing || count === 0 || !tool,
            isPreview: false,
            onBack: handleBack,
          };
      onFooterStateChange(state);
    }, [
      previewItems,
      importing,
      previewing,
      pendingItems.length,
      totalPreviewCount,
      tool,
      handleBack,
      onFooterStateChange,
    ]);

    const provider = tool?.tool_provider_type?.type_value ?? 'resource';
    const providerLabels = getProviderLabel(provider);
    const showChildrenOption = provider === 'notion' || provider === 'github';

    if (!open) return null;

    // ── Preview confirmation screen ───────────────────────────────────────────
    if (previewItems) {
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 1 }}>
          <Alert severity="info" icon={false}>
            <Typography variant="body2" fontWeight={600} gutterBottom>
              This will import {totalPreviewCount} source
              {totalPreviewCount !== 1 ? 's' : ''}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Review the pages below before confirming.
            </Typography>
          </Alert>

          <Paper variant="outlined" sx={{ maxHeight: 320, overflow: 'auto' }}>
            <List dense disablePadding>
              {previewItems.flatMap((preview, pi) =>
                preview.sources.map((source, si) => (
                  <React.Fragment
                    key={source.url || `${preview.urlItemId}-${si}`}
                  >
                    {(pi > 0 || si > 0) && <Divider component="li" />}
                    <ListItem>
                      <ListItemText
                        primary={
                          source.url ? (
                            <Link
                              href={source.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              underline="hover"
                              variant="body2"
                            >
                              {source.title || source.url}
                            </Link>
                          ) : (
                            <Typography variant="body2">
                              {source.title || preview.inputUrl}
                            </Typography>
                          )
                        }
                      />
                    </ListItem>
                  </React.Fragment>
                ))
              )}
            </List>
          </Paper>
        </Box>
      );
    }

    // ── URL entry screen ──────────────────────────────────────────────────────
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 1 }}>
        {!tool && (
          <Alert severity="error">
            No tool selected. Please go back and select a tool.
          </Alert>
        )}

        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {urlItems.map(item => (
            <TextField
              key={item.id}
              fullWidth
              placeholder={providerLabels.placeholder}
              value={item.url}
              onChange={e => handleUrlChange(item.id, e.target.value)}
              disabled={previewing || importing || item.status === 'success'}
              error={item.status === 'error'}
              helperText={
                item.status === 'error' ? (
                  <Box
                    component="span"
                    sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
                  >
                    <ErrorIcon fontSize="inherit" color="error" />
                    {item.error ||
                      'Import failed. Check the URL and try again.'}
                  </Box>
                ) : item.status === 'success' ? (
                  <Box
                    component="span"
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      color: 'success.main',
                    }}
                  >
                    <CheckCircleIcon fontSize="inherit" />
                    {item.title && item.title !== item.url
                      ? `Imported: ${item.title}`
                      : 'Imported successfully'}
                  </Box>
                ) : (
                  ''
                )
              }
              sx={drawerOutlinedFieldSx}
              InputProps={{
                endAdornment:
                  item.status === 'importing' ? (
                    <CircularProgress size={20} />
                  ) : item.status === 'success' ? (
                    <CheckCircleIcon color="success" />
                  ) : item.status === 'error' ? (
                    <ErrorIcon color="error" />
                  ) : null,
              }}
            />
          ))}

          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={handleAddUrl}
            disabled={previewing || importing}
            sx={{ ...drawerOutlineButtonSx, alignSelf: 'flex-start' }}
          >
            Add another URL
          </Button>

          {showChildrenOption && (
            <FormControlLabel
              control={
                <Checkbox
                  checked={includeChildren}
                  onChange={e => setIncludeChildren(e.target.checked)}
                  disabled={previewing || importing}
                  size="small"
                />
              }
              label={
                <Typography variant="body2">
                  {providerLabels.checkbox}
                </Typography>
              }
            />
          )}
        </Box>
      </Box>
    );
  }
);

export default ToolImportPanel;
