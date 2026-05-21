'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Box, Alert, CircularProgress, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { FilterButton } from '@/components/common/FilterButton';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab } from '@/components/common/Fab';
import { SearchPill } from '@/components/common/SearchPill';
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
  MCPProviderSelectionDialog,
  MCPConnectionDialog,
  MCPFilterDrawer,
  MCPFilters,
} from './components';
import {
  EMPTY_MCP_FILTERS,
  hasActiveMCPFilters,
} from './components/MCPFilterDrawer';
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
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [toolToDelete, setToolToDelete] = useState<Tool | null>(null);

  // Toolbar state
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<MCPFilters>(EMPTY_MCP_FILTERS);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);

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

        const toolTypesData = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'ToolType' and type_value eq 'mcp'",
          limit: 1,
        });
        if (toolTypesData.length > 0) {
          setMcpToolType(toolTypesData[0]);
        }

        const providerTypesData = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'ToolProviderType'",
          limit: 100,
        });
        setProviderTypes(providerTypesData);

        try {
          const toolsResponse = await toolsClient.getTools({ limit: 100 });
          const allTools = toolsResponse.data || [];
          if (toolTypesData.length > 0) {
            const mcpToolTypeId = toolTypesData[0].id;
            setTools(
              allTools.filter(tool => tool.tool_type_id === mcpToolTypeId)
            );
          } else {
            setTools([]);
          }
        } catch {
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

  const handleProviderSelect = (provider: TypeLookup) => {
    setSelectedProvider(provider);
    setProviderSelectionOpen(false);
    setConnectionDialogOpen(true);
  };

  const handleConnect = async (
    _providerId: string,
    toolData: ToolCreate
  ): Promise<Tool> => {
    if (!session?.session_token) throw new Error('No session token');
    const apiFactory = new ApiClientFactory(session.session_token);
    const toolsClient = apiFactory.getToolsClient();
    const tool = await toolsClient.createTool(toolData);
    setTools(prev => [...(prev || []), tool]);
    notifications.show('MCP connection created successfully', {
      severity: 'success',
    });
    return tool;
  };

  const handleUpdate = async (toolId: UUID, updates: Partial<ToolUpdate>) => {
    if (!session?.session_token) return;
    const apiFactory = new ApiClientFactory(session.session_token);
    const toolsClient = apiFactory.getToolsClient();
    const updatedTool = await toolsClient.updateTool(toolId, updates);
    setTools(prev =>
      prev.map(tool => (tool.id === toolId ? updatedTool : tool))
    );
    notifications.show('MCP connection updated successfully', {
      severity: 'success',
    });
  };

  const handleDeleteClick = (tool: Tool) => {
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

  // Derive available providers from loaded tools for the filter drawer
  const availableProviders = useMemo(
    () =>
      Array.from(
        new Set(
          tools
            .map(t => t.tool_provider_type?.type_value)
            .filter((v): v is string => Boolean(v))
        )
      ).sort(),
    [tools]
  );

  const filteredTools = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return tools.filter(tool => {
      const searchMatch =
        !q ||
        tool.name?.toLowerCase().includes(q) ||
        tool.description?.toLowerCase().includes(q) ||
        tool.tool_provider_type?.type_value?.toLowerCase().includes(q);

      const providerMatch =
        filters.providers.length === 0 ||
        (tool.tool_provider_type?.type_value &&
          filters.providers.includes(tool.tool_provider_type.type_value));

      return searchMatch && providerMatch;
    });
  }, [tools, searchQuery, filters]);

  return (
    <PageLayout
      title="MCP"
      description="Connect to Model Context Protocol (MCP) providers to import knowledge sources and enhance your evaluation workflows."
      breadcrumbs={[]}
      actions={
        <Fab
          icon={<AddIcon />}
          tooltip="Add MCP connection"
          aria-label="Add MCP connection"
          onClick={() => setProviderSelectionOpen(true)}
        />
      }
    >
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Toolbar — matches metrics/behaviors 3-col grid pattern */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: '1fr auto 1fr',
          alignItems: 'center',
          mb: 3,
          gap: 2,
        }}
      >
        {/* Left: Filter icon + Search pill */}
        <Box sx={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <FilterButton
            onClick={() => setFilterDrawerOpen(true)}
            hasActiveFilters={hasActiveMCPFilters(filters)}
          />
          <SearchPill
            value={searchQuery}
            onChange={v => setSearchQuery(v)}
            placeholder="Search MCP connections..."
          />
        </Box>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : filteredTools.length === 0 ? (
        <Box sx={{ py: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            {tools.length === 0
              ? 'No MCP connections yet. Use the + button to add one.'
              : 'No connections match your search or filters.'}
          </Typography>
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
            gap: '24px',
          }}
        >
          {filteredTools.map(tool => (
            <ConnectedToolCard
              key={tool.id}
              tool={tool}
              onDelete={handleDeleteClick}
            />
          ))}
        </Box>
      )}

      {/* Filter drawer */}
      <MCPFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={filters}
        availableProviders={availableProviders}
        onApply={f => {
          setFilters(f);
        }}
      />

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
        tool={null}
        mode="create"
        onClose={() => {
          setConnectionDialogOpen(false);
          setTimeout(() => setSelectedProvider(null), 200);
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
    </PageLayout>
  );
}
