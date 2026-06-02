'use client';

import React, { useState } from 'react';
import { Button, TextField, Box, Alert, CircularProgress } from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { UUID } from 'crypto';
import { getErrorMessage } from '@/utils/entity-error-handler';

interface UrlItem {
  id: string;
  url: string;
  status: 'pending' | 'importing' | 'success' | 'error';
  error?: string;
  title?: string;
}

interface ToolImportPanelProps {
  open: boolean;
  onClose: () => void;
  onBack?: () => void;
  onSuccess?: () => void;
  sessionToken: string;
  tool?: Tool | null;
}

export default function ToolImportPanel({
  open,
  onClose,
  onBack,
  onSuccess,
  sessionToken,
  tool,
}: ToolImportPanelProps) {
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toolSourceTypeId, setToolSourceTypeId] = useState<UUID | undefined>(
    undefined
  );
  const notifications = useNotifications();

  const [urlItems, setUrlItems] = useState<UrlItem[]>([
    { id: crypto.randomUUID(), url: '', status: 'pending' },
  ]);

  // Fetch the "Tool" SourceType ID once
  React.useEffect(() => {
    if (!sessionToken) return;
    const fetchSourceType = async () => {
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const typeLookupClient = clientFactory.getTypeLookupClient();
        const results = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'SourceType' and type_value eq 'Tool'",
          limit: 1,
        });
        if (results.length > 0) setToolSourceTypeId(results[0].id as UUID);
      } catch (err) {
        console.error('Failed to fetch Tool SourceType:', err);
      }
    };
    fetchSourceType();
  }, [sessionToken]);

  const reset = () => {
    setUrlItems([{ id: crypto.randomUUID(), url: '', status: 'pending' }]);
    setError(null);
  };

  const handleBack = () => {
    if (!importing) {
      reset();
      if (onBack) {
        onBack();
      } else {
        onClose();
      }
    }
  };

  const handleUrlChange = (id: string, url: string) => {
    setUrlItems(prev =>
      prev.map(item => (item.id === id ? { ...item, url } : item))
    );
  };

  const handleAddUrl = () => {
    setUrlItems(prev => [
      ...prev,
      { id: crypto.randomUUID(), url: '', status: 'pending' },
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

  const handleImport = async () => {
    if (!tool) {
      setError('No tool selected');
      return;
    }

    const pendingItems = urlItems.filter(
      item => item.url.trim() && item.status === 'pending'
    );
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

    setImporting(true);
    setError(null);

    const clientFactory = new ApiClientFactory(sessionToken);
    const servicesClient = clientFactory.getServicesClient();
    const sourcesClient = clientFactory.getSourcesClient();

    let successCount = 0;
    let errorCount = 0;

    for (const item of pendingItems) {
      setUrlItems(prev =>
        prev.map(i => (i.id === item.id ? { ...i, status: 'importing' } : i))
      );

      try {
        const result = await servicesClient.extractTool(tool.id, {
          url: item.url,
        });

        // Create one source per extracted document
        const provider = tool.tool_provider_type?.type_value ?? 'tool';
        for (const source of result.sources) {
          await sourcesClient.createSourceFromContent(
            source.title || item.url,
            source.content,
            undefined,
            {
              provider,
              mcp_tool_id: tool.id,
              url: source.url ?? item.url,
              imported_at: new Date().toISOString(),
            },
            toolSourceTypeId
          );
        }

        setUrlItems(prev =>
          prev.map(i =>
            i.id === item.id
              ? {
                  ...i,
                  status: 'success',
                  title: result.sources[0]?.title ?? item.url,
                }
              : i
          )
        );
        successCount++;
      } catch (err) {
        const msg = getErrorMessage(err) || 'Failed to import this URL';
        setUrlItems(prev =>
          prev.map(i =>
            i.id === item.id ? { ...i, status: 'error', error: msg } : i
          )
        );
        errorCount++;
      }
    }

    setImporting(false);

    const providerName = tool.tool_provider_type?.type_value ?? 'Tool';
    const label = providerName.charAt(0).toUpperCase() + providerName.slice(1);

    if (successCount > 0) {
      notifications.show(
        `Successfully imported ${successCount} source${successCount !== 1 ? 's' : ''} from ${label}`,
        { severity: 'success', autoHideDuration: 4000 }
      );
    }
    if (errorCount > 0) {
      notifications.show(
        `Failed to import ${errorCount} URL${errorCount !== 1 ? 's' : ''}. Check the errors above.`,
        { severity: 'error', autoHideDuration: 6000 }
      );
    }
    if (successCount > 0 && errorCount === 0) onSuccess?.();
  };

  const pendingCount = urlItems.filter(
    i => i.url.trim() && i.status === 'pending'
  ).length;
  const provider = tool?.tool_provider_type?.type_value ?? 'resource';

  if (!open) return null;

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

      {/* URL inputs */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {urlItems.map(item => (
          <TextField
            key={item.id}
            fullWidth
            placeholder={`Paste ${provider} URL...`}
            value={item.url}
            onChange={e => handleUrlChange(item.id, e.target.value)}
            disabled={item.status !== 'pending'}
            error={item.status === 'error'}
            helperText={
              item.status === 'error'
                ? item.error
                : item.status === 'success'
                  ? `Imported: ${item.title}`
                  : ''
            }
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
          startIcon={<AddIcon />}
          onClick={handleAddUrl}
          disabled={importing}
          sx={{ alignSelf: 'flex-start' }}
        >
          Add another URL
        </Button>
      </Box>

      {/* Footer */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', pt: 2 }}>
        <Button
          onClick={handleBack}
          disabled={importing}
          startIcon={<ArrowBackIcon />}
        >
          Back
        </Button>
        <Button
          variant="contained"
          onClick={handleImport}
          disabled={importing || pendingCount === 0 || !tool}
          startIcon={importing ? <CircularProgress size={20} /> : <SaveIcon />}
        >
          {importing
            ? 'Importing...'
            : `Import ${pendingCount} URL${pendingCount !== 1 ? 's' : ''}`}
        </Button>
      </Box>
    </Box>
  );
}
