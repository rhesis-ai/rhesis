'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Alert,
  CircularProgress,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import TerminalIcon from '@mui/icons-material/Terminal';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { MCP_PROVIDER_ICONS } from '@/config/mcp-providers';

interface MCPToolSelectorDialogProps {
  open: boolean;
  onClose: () => void;
  onSelectTool: (tool: Tool) => void;
  sessionToken: string;
}

export default function MCPToolSelectorDialog({
  open,
  onClose,
  onSelectTool,
  sessionToken,
}: MCPToolSelectorDialogProps) {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // No need to keep selection state – click selects and proceeds immediately

  useEffect(() => {
    if (open) {
      loadMCPTools();
    }
  }, [open, sessionToken]);

  const loadMCPTools = async () => {
    if (!sessionToken) return;

    try {
      setLoading(true);
      setError(null);
      const apiFactory = new ApiClientFactory(sessionToken);
      const toolsClient = apiFactory.getToolsClient();
      const typeLookupClient = apiFactory.getTypeLookupClient();

      // Get MCP tool type ID
      const toolTypes = await typeLookupClient.getTypeLookups({
        $filter: "type_name eq 'ToolType' and type_value eq 'mcp'",
        limit: 1,
      });

      if (toolTypes.length === 0) {
        setError('No MCP tool type found. Please configure MCP tools first.');
        setLoading(false);
        return;
      }

      // Get all tools
      const toolsResponse = await toolsClient.getTools({ limit: 100 });
      const allTools = toolsResponse.data || [];

      // Filter for MCP tools only
      const mcpToolTypeId = toolTypes[0].id;
      const mcpTools = allTools.filter(
        tool => tool.tool_type_id === mcpToolTypeId
      );

      setTools(mcpTools);

      if (mcpTools.length === 0) {
        setError(
          'No MCP tools configured. Please add an MCP tool in the MCPs page.'
        );
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to load MCP tools. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTool = (tool: Tool) => {
    onSelectTool(tool);
    handleClose();
  };

  const handleClose = () => {
    if (!loading) {
      // setSelectedTool(null); // No longer needed
      setError(null);
      onClose();
    }
  };

  const getToolIcon = (tool: Tool) => {
    const providerName = tool.tool_provider_type?.type_value || 'custom';
    const providerIcon = MCP_PROVIDER_ICONS[providerName];
    if (providerIcon) {
      return providerIcon;
    }
    return <SmartToyIcon />;
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center" gap={1}>
            <TerminalIcon />
            <Typography variant="h6">Select MCP Tool</Typography>
          </Box>
          <IconButton onClick={handleClose} disabled={loading}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ mt: 1 }}>
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
              No MCP tools available. Please configure MCP tools in Settings
              &gt; Integrations &gt; MCPs.
            </Alert>
          ) : (
            <List>
              {tools.map((tool, index) => (
                <React.Fragment key={tool.id}>
                  {index > 0 && <Divider />}
                  <ListItem disablePadding>
                    <ListItemButton onClick={() => handleSelectTool(tool)}>
                      <ListItemIcon>{getToolIcon(tool)}</ListItemIcon>
                      <ListItemText
                        primary={tool.name}
                        secondary={
                          tool.tool_provider_type?.type_value
                            ? tool.tool_provider_type.type_value
                                .charAt(0)
                                .toUpperCase() +
                              tool.tool_provider_type.type_value.slice(1)
                            : 'Unknown provider'
                        }
                        primaryTypographyProps={{ fontWeight: 500 }}
                      />
                    </ListItemButton>
                  </ListItem>
                </React.Fragment>
              ))}
            </List>
          )}
        </Box>
      </DialogContent>

      {/* No footer actions – selection happens on click */}
    </Dialog>
  );
}
