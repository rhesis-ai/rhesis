'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { Box, Alert, CircularProgress } from '@mui/material';
import { BuildIcon } from '@/components/icons';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import GridToolbar, {
  directoryToolbarProps,
} from '@/components/common/GridToolbar';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
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
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

export default function ToolsPage() {
  const { data: session } = useSession();
  const notifications = useNotifications();
  const canRead = useCan(Capability.Tool.READ);
  const canCreateTool = useCan(Capability.Tool.CREATE);
  useDocumentTitle('Tools');
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

  // TODO: remove once Confluence is supported
  const supportedProviderTypes = useMemo(
    () => providerTypes.filter(pt => pt.type_value !== 'confluence'),
    [providerTypes]
  );

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

  const openConnectionDrawer = () => {
    setToolToEdit(null);
    setConnectionDrawerOpen(true);
  };

  if (!canRead) return <AccessDenied resource="tool connections" />;

  return (
    <PageLayout
      title="Tools"
      description="Connect tools and external services to import knowledge sources and enhance your evaluation workflows."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Can capability={Capability.Tool.CREATE}>
            <Fab
              icon={<FabAddIcon />}
              tooltip="Add tool connection"
              aria-label="Add tool connection"
              onClick={openConnectionDrawer}
            />
          </Can>
        </FabGroup>
      }
    >
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box sx={{ mt: 2, mb: 2 }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : tools.length === 0 ? (
          <EntityEmptyState
            card
            icon={BuildIcon}
            title="No tool connections yet"
            description="Connect tools and external services to import knowledge sources and enhance your evaluation workflows."
            actionLabel={canCreateTool ? 'Add tool connection' : undefined}
            onAction={canCreateTool ? openConnectionDrawer : undefined}
          />
        ) : (
          <>
            <GridToolbar
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              searchPlaceholder="Search tool connections..."
              onFilterClick={() => setFilterDrawerOpen(true)}
              hasActiveFilters={hasActiveToolFilters(filters)}
              activeFilterCount={countActiveToolFilters(filters)}
              {...directoryToolbarProps}
            />

            {filteredTools.length === 0 ? (
              <EntityEmptyState
                card
                showAddIcon={false}
                icon={BuildIcon}
                title="No connections match your search or filters"
                description="Try adjusting your search or filters to find the tool connections you're looking for."
                actionLabel="Reset filters"
                onAction={() => {
                  setSearchQuery('');
                  setFilters(EMPTY_TOOL_FILTERS);
                }}
              />
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
          </>
        )}
      </Box>

      <ToolFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={filters}
        availableProviders={availableProviders}
        onApply={f => setFilters(f)}
      />

      <ToolConnectionDrawer
        open={connectionDrawerOpen}
        providers={supportedProviderTypes}
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
