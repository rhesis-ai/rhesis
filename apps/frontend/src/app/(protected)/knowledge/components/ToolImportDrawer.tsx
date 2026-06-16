'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Link,
} from '@mui/material';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import BaseDrawer from '@/components/common/BaseDrawer';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TOOL_PROVIDER_ICONS, REST_PROVIDERS } from '@/config/tool-providers';
import ToolImportPanel from './ToolImportPanel';

interface ToolImportDrawerProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  sessionToken: string;
}

export default function ToolImportDrawer({
  open,
  onClose,
  onSuccess,
  sessionToken,
}: ToolImportDrawerProps) {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loadingTools, setLoadingTools] = useState(false);
  const [selectedToolId, setSelectedToolId] = useState<string>('');

  const loadTools = useCallback(async () => {
    if (!sessionToken) return;
    try {
      setLoadingTools(true);
      const apiFactory = new ApiClientFactory(sessionToken);
      const response = await apiFactory
        .getToolsClient()
        .getTools({ limit: 100 });
      const supported = (response.data || []).filter(t =>
        REST_PROVIDERS.includes(t.tool_provider_type?.type_value ?? '')
      );
      setTools(supported);
      // Auto-select when there is only one option
      if (supported.length === 1) {
        setSelectedToolId(supported[0].id);
      }
    } catch {
      setTools([]);
    } finally {
      setLoadingTools(false);
    }
  }, [sessionToken]);

  useEffect(() => {
    if (open) {
      loadTools();
    } else {
      setTools([]);
      setSelectedToolId('');
    }
  }, [open, loadTools]);

  const handleClose = () => {
    onClose();
  };

  const selectedTool = tools.find(t => t.id === selectedToolId) ?? null;

  const getProviderIcon = (tool: Tool) => {
    const key = tool.tool_provider_type?.type_value ?? '';
    return TOOL_PROVIDER_ICONS[key] ?? <SmartToyIcon />;
  };

  const providerLabel = (tool: Tool) => {
    const v = tool.tool_provider_type?.type_value ?? '';
    return v.charAt(0).toUpperCase() + v.slice(1);
  };

  return (
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title="Import from Tool"
      titleIcon={<CloudDownloadIcon color="primary" />}
      width={900}
      closeButtonText="Cancel"
    >
      {loadingTools ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : tools.length === 0 ? (
        <Alert severity="info">
          No tools configured. Connect a Notion or GitHub tool in{' '}
          <Link href="/tools" underline="hover">
            Settings &rsaquo; Tools
          </Link>{' '}
          first.
        </Alert>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Only show the selector when there is more than one option */}
          {tools.length > 1 && (
            <FormControl fullWidth>
              <InputLabel id="tool-select-label">Source</InputLabel>
              <Select
                labelId="tool-select-label"
                value={selectedToolId}
                label="Source"
                onChange={e => setSelectedToolId(e.target.value)}
              >
                {tools.map(tool => (
                  <MenuItem
                    key={tool.id}
                    value={tool.id}
                    sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                  >
                    <Box
                      component="span"
                      sx={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        '& svg': { width: 18, height: 18 },
                      }}
                    >
                      {getProviderIcon(tool)}
                    </Box>
                    {providerLabel(tool)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          <ToolImportPanel
            open={open}
            onClose={handleClose}
            onSuccess={onSuccess}
            sessionToken={sessionToken}
            tool={selectedTool}
          />
        </Box>
      )}
    </BaseDrawer>
  );
}
