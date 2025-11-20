'use client';

import React, { useState, useEffect } from 'react';
import { Box, Typography, Alert, CircularProgress } from '@mui/material';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  Tool,
  ToolCreate,
  ToolUpdate,
} from '@/utils/api-client/interfaces/tool';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { DeleteModal } from '@/components/common/DeleteModal';
import { UUID } from 'crypto';
import {
  ConnectedToolCard,
  AddToolCard,
  MCPProviderSelectionDialog,
  MCPConnectionDialog,
} from './components';
import { useNotifications } from '@/components/common/NotificationContext';

export default function MCPSPage() {
  const { data: session } = useSession();
  const notifications = useNotifications();
  const [tools, setTools] = useState<Tool[]>([]);
  const [mcpToolType, setMcpToolType] = useState<TypeLookup | null>(null);
  const [providerTypes, setProviderTypes] = useState<TypeLookup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<TypeLookup | null>(
    null
  );
  const [providerSelectionOpen, setProviderSelectionOpen] = useState(false);
  const [connectionDialogOpen, setConnectionDialogOpen] = useState(false);
  const [toolToEdit, setToolToEdit] = useState<Tool | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [toolToDelete, setToolToDelete] = useState<Tool | null>(null);

  useEffect(() => {
    async function loadData() {
      if (!session?.session_token) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const apiFactory = new ApiClientFactory(session.session_token);
        const toolsClient = apiFactory.getToolsClient();
        const typeLookupClient = apiFactory.getTypeLookupClient();

        // Load MCP tool type
        const toolTypesData = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'ToolType' and type_value eq 'mcp'",
          limit: 1,
        });
        if (toolTypesData.length > 0) {
          setMcpToolType(toolTypesData[0]);
        }

        // Load provider types (for MCP providers)
        const providerTypesData = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'ToolProviderType'",
          limit: 100,
        });
        setProviderTypes(providerTypesData);

        // Load MCP tools only (filter by tool_type = 'mcp')
        try {
          const toolsResponse = await toolsClient.getTools({ limit: 100 });
          const allTools = toolsResponse.data || [];
          // Filter for MCP tools only
          if (toolTypesData.length > 0) {
            const mcpToolTypeId = toolTypesData[0].id;
            const mcpTools = allTools.filter(
              tool => tool.tool_type_id === mcpToolTypeId
            );
            setTools(mcpTools);
          } else {
            setTools([]);
          }
        } catch {
          // Failed to load tools - will show empty state
          setTools([]);
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load MCP connections'
        );
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [session]);

  const handleAddMCP = () => {
    setProviderSelectionOpen(true);
  };

  const handleProviderSelect = (provider: TypeLookup) => {
    setSelectedProvider(provider);
    setProviderSelectionOpen(false);
    setConnectionDialogOpen(true);
  };

  const handleConnect = async (
    providerId: string,
    toolData: ToolCreate
  ): Promise<Tool> => {
    if (!session?.session_token) {
      throw new Error('No session token');
    }

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const toolsClient = apiFactory.getToolsClient();

      const tool = await toolsClient.createTool(toolData);
      setTools(prev => [...(prev || []), tool]);
      notifications.show('MCP connection created successfully', {
        severity: 'success',
      });
      return tool;
    } catch (err) {
      throw err;
    }
  };

  const handleEditClick = (tool: Tool, event: React.MouseEvent) => {
    event.stopPropagation();
    setToolToEdit(tool);
    // Find the provider type for this tool
    const provider = providerTypes.find(
      p => p.id === tool.tool_provider_type_id
    );
    setSelectedProvider(provider || null);
    setConnectionDialogOpen(true);
  };

  const handleUpdate = async (toolId: UUID, updates: Partial<ToolUpdate>) => {
    if (!session?.session_token) return;

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const toolsClient = apiFactory.getToolsClient();

      const updatedTool = await toolsClient.updateTool(toolId, updates);
      setTools(prev =>
        prev.map(tool => (tool.id === toolId ? updatedTool : tool))
      );
      notifications.show('MCP connection updated successfully', {
        severity: 'success',
      });
    } catch (err) {
      throw err;
    }
  };

  const handleDeleteClick = (tool: Tool, event: React.MouseEvent) => {
    event.stopPropagation();
    setToolToDelete(tool);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!session?.session_token || !toolToDelete) return;

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const toolsClient = apiFactory.getToolsClient();

      await toolsClient.deleteTool(toolToDelete.id);
      setTools(prev => prev.filter(tool => tool.id !== toolToDelete.id));
      setDeleteDialogOpen(false);
      setToolToDelete(null);
      notifications.show('MCP connection deleted successfully', {
        severity: 'success',
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to delete MCP connection'
      );
      notifications.show('Failed to delete MCP connection', {
        severity: 'error',
      });
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ maxWidth: 1200, mx: 'auto' }}>
        <Box sx={{ mb: 3 }}>
          <Typography variant="h4" sx={{ mb: 1 }}>
            MCPs
          </Typography>
          <Typography color="text.secondary">
            Connect to Model Context Protocol (MCP) providers to import
            knowledge sources and enhance your evaluation workflows.
          </Typography>
          {error && (
            <Alert
              severity="error"
              sx={{ mt: 2 }}
              onClose={() => setError(null)}
            >
              {error}
            </Alert>
          )}
        </Box>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, 1fr)',
                md: 'repeat(3, 1fr)',
              },
              gap: 3,
              width: '100%',
              px: 0,
            }}
          >
            {/* Connected MCP Cards */}
            {tools.map(tool => (
              <ConnectedToolCard
                key={tool.id}
                tool={tool}
                onEdit={handleEditClick}
                onDelete={handleDeleteClick}
              />
            ))}

            {/* Add MCP Card */}
            <AddToolCard onClick={handleAddMCP} />
          </Box>
        )}
      </Box>

      <MCPProviderSelectionDialog
        open={providerSelectionOpen}
        onClose={() => setProviderSelectionOpen(false)}
        onSelectProvider={handleProviderSelect}
        providers={providerTypes}
      />

      <MCPConnectionDialog
        open={connectionDialogOpen}
        provider={selectedProvider}
        mcpToolType={mcpToolType}
        tool={toolToEdit}
        mode={toolToEdit ? 'edit' : 'create'}
        onClose={() => {
          setConnectionDialogOpen(false);
          // Delay clearing state to prevent button text flicker during closing animation
          setTimeout(() => {
            setSelectedProvider(null);
            setToolToEdit(null);
          }, 200);
        }}
        onConnect={handleConnect}
        onUpdate={handleUpdate}
      />

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => {
          setDeleteDialogOpen(false);
          setToolToDelete(null);
        }}
        onConfirm={handleDeleteConfirm}
        itemType="MCP connection"
        itemName={toolToDelete?.name}
        title="Delete MCP Connection"
      />
    </Box>
  );
}
