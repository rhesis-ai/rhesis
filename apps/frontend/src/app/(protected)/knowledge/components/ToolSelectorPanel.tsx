'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { TOOL_PROVIDER_ICONS } from '@/config/tool-providers';

/** Providers supported via the deterministic REST extract path. */
const REST_PROVIDERS = ['notion', 'github'];

interface ToolSelectorPanelProps {
  open: boolean;
  onClose: () => void;
  onSelectTool: (tool: Tool) => void;
  sessionToken: string;
}

export default function ToolSelectorPanel({
  open,
  onClose,
  onSelectTool,
  sessionToken,
}: ToolSelectorPanelProps) {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTools = useCallback(async () => {
    if (!sessionToken) return;
    try {
      setLoading(true);
      setError(null);
      const apiFactory = new ApiClientFactory(sessionToken);
      const toolsClient = apiFactory.getToolsClient();

      const response = await toolsClient.getTools({ limit: 100 });
      const allTools = response.data || [];

      // Keep only Notion and GitHub tools
      const supported = allTools.filter(tool =>
        REST_PROVIDERS.includes(tool.tool_provider_type?.type_value ?? '')
      );

      setTools(supported);

      if (supported.length === 0) {
        setError(
          'No Notion or GitHub tools configured. Please add one in Settings > Integrations > Tools.'
        );
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to load tools. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  }, [sessionToken]);

  useEffect(() => {
    if (open) loadTools();
  }, [open, loadTools]);

  const getToolIcon = (tool: Tool) => {
    const provider = tool.tool_provider_type?.type_value || 'custom';
    return TOOL_PROVIDER_ICONS[provider] ?? <SmartToyIcon />;
  };

  const providerLabel = (tool: Tool) => {
    const v = tool.tool_provider_type?.type_value ?? '';
    return v.charAt(0).toUpperCase() + v.slice(1) || 'Unknown provider';
  };

  if (!open) return null;

  return (
    <Box sx={{ mt: 0 }}>
      {loading ? (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '200px',
          }}
        >
          <CircularProgress />
        </Box>
      ) : error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : tools.length === 0 ? (
        <Alert severity="info">
          No tools available. Please configure a Notion or GitHub tool in
          Settings &gt; Integrations &gt; Tools.
        </Alert>
      ) : (
        <List>
          {tools.map((tool, index) => (
            <React.Fragment key={tool.id}>
              {index > 0 && <Divider />}
              <ListItem disablePadding>
                <ListItemButton onClick={() => onSelectTool(tool)}>
                  <ListItemIcon>{getToolIcon(tool)}</ListItemIcon>
                  <ListItemText
                    primary={tool.name}
                    secondary={providerLabel(tool)}
                    primaryTypographyProps={{ fontWeight: 500 }}
                  />
                </ListItemButton>
              </ListItem>
            </React.Fragment>
          ))}
        </List>
      )}
    </Box>
  );
}
