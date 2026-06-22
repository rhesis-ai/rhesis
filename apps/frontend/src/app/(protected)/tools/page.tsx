'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Box, Alert, CircularProgress, Typography } from '@mui/material';
import HandymanIcon from '@mui/icons-material/Handyman';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import GridToolbar, {
  directoryToolbarProps,
} from '@/components/common/GridToolbar';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  Tool,
  ToolCreate,
  ToolUpdate,
  TypeLookup,
} from '@/utils/api-client/interfaces/tool';
import { DeleteModal } from '@/components/common/DeleteModal';
import { UUID } from 'crypto';
import {
  ConnectedToolCard,
  ToolConnectionDrawer,
  ToolFilterDrawer,
  ToolFilters,
  EMPTY_TOOL_FILTERS,
  hasActiveToolFilters,
  countActiveToolFilters,
} from './components';
import { useNotifications } from '@/components/common/NotificationContext';

export default function ToolsPage() {
  const { data: session } = useSession();
  const notifications = useNotifications();
  const [tools, setTools] = useState<Tool[]>([]);
  const [providerTypes, setProviderTypes] = useState<TypeLookup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [connectionDrawerOpen, setConnectionDrawerOpen] = useState(false);
  const [toolToEdit, setToolToEdit] = useState<Tool | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [toolToDelete, setToolToDelete] = useState<Tool | null>(null);

  // Toolbar state
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<ToolFilters>(EMPTY_TOOL_FILTERS);
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

        const [providerTypesData, toolsResponse] = await Promise.all([
          typeLookupClient.getTypeLookups({
            $filter: "type_name eq 'ToolProviderType'",
            limit: 100,
          }),
          toolsClient.getTools({ limit: 100 }).catch(() => ({ data: [] })),
        ]);

        setProviderTypes(providerTypesData);
        setTools(toolsResponse.data || []);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load tool connections'
        );
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [session]);

  const handleConnect = async (
    _: string,
    toolData: ToolCreate
  ): Promise<Tool> => {
    if (!session?.session_token) throw new Error('No session token');
    const apiFactory = new ApiClientFactory(session.session_token);
    const tool = await apiFactory.getToolsClient().createTool(toolData);
    setTools(prev => [...prev, tool]);
    notifications.show('Tool connection created successfully', {
      severity: 'success',
    });
    return tool;
  };

  const handleUpdate = async (toolId: UUID, updates: Partial<ToolUpdate>) => {
    if (!session?.session_token) return;
    const apiFactory = new ApiClientFactory(session.session_token);
    const updated = await apiFactory
      .getToolsClient()
      .updateTool(toolId, updates);
    setTools(prev => prev.map(t => (t.id === toolId ? updated : t)));
    notifications.show('Tool connection updated successfully', {
      severity: 'success',
    });
  };

  const handleCardClick = (tool: Tool) => {
    setToolToEdit(tool);
    setConnectionDrawerOpen(true);
  };

  const handleDeleteClick = (tool: Tool) => {
    setToolToDelete(tool);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!session?.session_token || !toolToDelete) return;
    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      await apiFactory.getToolsClient().deleteTool(toolToDelete.id);
      setTools(prev => prev.filter(t => t.id !== toolToDelete.id));
      setDeleteDialogOpen(false);
      setToolToDelete(null);
      notifications.show('Tool connection deleted successfully', {
        severity: 'success',
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to delete tool connection'
      );
      notifications.show('Failed to delete tool connection', {
        severity: 'error',
      });
    }
  };

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
      title="Tools"
      description="Connect tools and external services to import knowledge sources and enhance your evaluation workflows."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Fab
            icon={<FabAddIcon />}
            tooltip="Add tool connection"
            aria-label="Add tool connection"
            onClick={() => {
              setToolToEdit(null);
              setConnectionDrawerOpen(true);
            }}
          />
        </FabGroup>
      }
    >
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <GridToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search tool connections..."
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={hasActiveToolFilters(filters)}
        activeFilterCount={countActiveToolFilters(filters)}
        {...directoryToolbarProps}
      />

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : tools.length === 0 ? (
        <EntityEmptyState
          icon={HandymanIcon}
          title="No tool connections yet"
          description="Connect tools and external services to import knowledge sources and enhance your evaluation workflows."
          actionLabel="Add tool connection"
          onAction={() => setConnectionDrawerOpen(true)}
        />
      ) : filteredTools.length === 0 ? (
        <Box sx={{ py: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            No connections match your search or filters.
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
            gap: 3,
          }}
        >
          {filteredTools.map(tool => (
            <ConnectedToolCard
              key={tool.id}
              tool={tool}
              onDelete={handleDeleteClick}
              onCardClick={handleCardClick}
            />
          ))}
        </Box>
      )}

      <ToolFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={filters}
        availableProviders={availableProviders}
        onApply={f => setFilters(f)}
      />

      <ToolConnectionDrawer
        open={connectionDrawerOpen}
        providers={providerTypes}
        tool={toolToEdit}
        mode={toolToEdit ? 'edit' : 'create'}
        onClose={() => {
          setConnectionDrawerOpen(false);
          setTimeout(() => setToolToEdit(null), 300);
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
        itemType="tool connection"
        itemName={toolToDelete?.name}
        title="Delete Tool Connection"
      />
    </PageLayout>
  );
}
