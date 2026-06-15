'use client';

import React, { useState, useEffect } from 'react';
import { Box, Alert, CircularProgress, Menu, MenuItem } from '@mui/material';
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
import { ProviderCard, ToolConnectionDrawer } from './components';
import { useNotifications } from '@/components/common/NotificationContext';

export default function ToolsPage() {
  const { data: session } = useSession();
  const notifications = useNotifications();
  const [providerTypes, setProviderTypes] = useState<TypeLookup[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [connectionDrawerOpen, setConnectionDrawerOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<TypeLookup | null>(
    null
  );
  const [toolToEdit, setToolToEdit] = useState<Tool | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [toolToDelete, setToolToDelete] = useState<Tool | null>(null);

  // FAB menu
  const [fabAnchorEl, setFabAnchorEl] = useState<null | HTMLElement>(null);
  const fabMenuOpen = Boolean(fabAnchorEl);

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

  const handleFabClick = (event: React.MouseEvent<HTMLElement>) => {
    setFabAnchorEl(event.currentTarget);
  };

  const handleFabMenuClose = () => {
    setFabAnchorEl(null);
  };

  const handleConnectClick = (providerType: TypeLookup) => {
    handleFabMenuClose();
    setSelectedProvider(providerType);
    setToolToEdit(null);
    setConnectionDrawerOpen(true);
  };

  const handleEditClick = (tool: Tool) => {
    const pt =
      providerTypes.find(p => p.id === tool.tool_provider_type_id) ?? null;
    setSelectedProvider(pt);
    setToolToEdit(tool);
    setConnectionDrawerOpen(true);
  };

  const handleDeleteClick = (tool: Tool) => {
    setToolToDelete(tool);
    setDeleteDialogOpen(true);
  };

  const handleToolCreate = async (
    _providerId: string,
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

  // Zip each provider type with its existing connection (or null)
  const providerCards = providerTypes.map(pt => ({
    providerType: pt,
    tool: tools.find(t => t.tool_provider_type_id === pt.id) ?? null,
  }));

  // Only show unconnected providers in the FAB menu
  const unconnectedProviders = providerTypes.filter(
    pt => !tools.find(t => t.tool_provider_type_id === pt.id)
  );

  return (
    <PageLayout
      title="Tools"
      description="Connect tools and external services to import knowledge sources and enhance your evaluation workflows."
      breadcrumbs={[]}
      actions={
        !loading && (
          <FabGroup>
            <Fab
              icon={<FabAddIcon />}
              tooltip={
                unconnectedProviders.length === 0
                  ? 'All tools are connected'
                  : 'Connect a tool'
              }
              aria-label="Connect a tool"
              disabled={unconnectedProviders.length === 0}
              onClick={handleFabClick}
            />
            <Menu
              anchorEl={fabAnchorEl}
              open={fabMenuOpen}
              onClose={handleFabMenuClose}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
              {unconnectedProviders.map(pt => (
                <MenuItem key={pt.id} onClick={() => handleConnectClick(pt)}>
                  {pt.type_value.charAt(0).toUpperCase() +
                    pt.type_value.slice(1)}
                </MenuItem>
              ))}
            </Menu>
          </FabGroup>
        )
      }
    >
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}


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
            gap: '24px',
          }}
        >
          {providerCards.map(({ providerType, tool }) => (
            <ProviderCard
              key={providerType.id}
              providerType={providerType}
              tool={tool}
              onConnect={handleConnectClick}
              onEdit={handleEditClick}
              onDelete={handleDeleteClick}
            />
          ))}
        </Box>
      )}

      <ToolConnectionDrawer
        open={connectionDrawerOpen}
        provider={selectedProvider}
        tool={toolToEdit}
        mode={toolToEdit ? 'edit' : 'create'}
        onClose={() => {
          setConnectionDrawerOpen(false);
          setTimeout(() => {
            setToolToEdit(null);
            setSelectedProvider(null);
          }, 300);
        }}
        onConnect={handleToolCreate}
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
