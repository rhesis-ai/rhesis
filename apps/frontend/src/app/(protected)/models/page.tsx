'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Box, Alert, CircularProgress, Typography } from '@mui/material';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import GridToolbar, {
  ToolbarPillTabs,
  directoryToolbarProps,
} from '@/components/common/GridToolbar';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useOrganization } from '@/contexts/OrganizationContext';
import { Model, ModelCreate } from '@/utils/api-client/interfaces/model';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import { DeleteModal } from '@/components/common/DeleteModal';
import { UUID } from 'crypto';
import { ConnectedModelCard } from './components';
import { ModelConnectionDrawer } from './components/ModelConnectionDrawer';
import ModelFilterDrawer, {
  EMPTY_MODEL_FILTERS,
  hasActiveModelFilters,
  countActiveModelFilters,
  type ModelFilters,
} from './components/ModelFilterDrawer';
import { filterUniqueValidOptions } from '@/components/common/BaseDrawer';
import PolyphemusAccessModal from '@/components/common/PolyphemusAccessModal';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import type { ValidationStatus } from './types';

export type { ValidationStatus } from './types';

type ModelTypeFilter = 'all' | 'language' | 'embedding';

export default function ModelsPage() {
  const { data: session } = useSession();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Model.READ
  );
  const canEditModel = useCan(Capability.Model.UPDATE);
  const canDeleteModel = useCan(Capability.Model.DELETE);

  const [connectedModels, setConnectedModels] = useState<Model[]>([]);
  const [providerTypes, setProviderTypes] = useState<TypeLookup[]>([]);
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modelValidationStatus, setModelValidationStatus] = useState<
    Map<string, ValidationStatus>
  >(new Map());
  const [addModelDrawerOpen, setAddModelDrawerOpen] = useState(false);
  const [modelToEdit, setModelToEdit] = useState<Model | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [modelToDelete, setModelToDelete] = useState<Model | null>(null);
  const [selectedModelType, setSelectedModelType] = useState<
    'language' | 'embedding'
  >('language');
  const [polyphemusModalOpen, setPolyphemusModalOpen] = useState(false);
  const { organization } = useOrganization();

  // Toolbar state
  const [searchQuery, setSearchQuery] = useState('');
  const [modelTypeFilter, setModelTypeFilter] =
    useState<ModelTypeFilter>('all');
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [drawerFilters, setDrawerFilters] =
    useState<ModelFilters>(EMPTY_MODEL_FILTERS);
  const [statusOptions, setStatusOptions] = useState<string[]>([]);

  // FAB menu anchor
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
        const modelsClient = apiFactory.getModelsClient();
        const typeLookupClient = apiFactory.getTypeLookupClient();
        const usersClient = apiFactory.getUsersClient();

        const [types, settings, modelsResponse, statuses] = await Promise.all([
          typeLookupClient.getTypeLookups({
            $filter: "type_name eq 'ProviderType'",
            limit: 100,
          }),
          usersClient.getUserSettings().catch(() => null),
          modelsClient.getModels().catch(() => null),
          apiFactory
            .getStatusClient()
            .getStatuses({
              sort_by: 'name',
              sort_order: 'asc',
              entity_type: 'Model',
            })
            .catch(() => null),
        ]);

        setProviderTypes(types);
        if (settings) setUserSettings(settings);
        if (modelsResponse) setConnectedModels(modelsResponse.data);
        if (statuses)
          setStatusOptions(
            filterUniqueValidOptions(statuses).map(status => status.name)
          );
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load providers'
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

  const handleAddLanguageModel = () => {
    handleFabMenuClose();
    setSelectedModelType('language');
    setModelToEdit(null);
    setAddModelDrawerOpen(true);
  };

  const handleAddEmbeddingModel = () => {
    handleFabMenuClose();
    setSelectedModelType('embedding');
    setModelToEdit(null);
    setAddModelDrawerOpen(true);
  };

  const refreshUserSettings = async () => {
    if (!session?.session_token) return;
    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const usersClient = apiFactory.getUsersClient();
      const settings = await usersClient.getUserSettings();
      setUserSettings(settings);
    } catch (error) {
      console.error('Failed to refresh user settings:', error);
    }
  };

  const validateModel = useCallback(
    async (modelId: UUID) => {
      if (!session?.session_token) return;

      setModelValidationStatus(prev =>
        new Map(prev).set(modelId, { isValid: false, isValidating: true })
      );

      try {
        const apiFactory = new ApiClientFactory(session.session_token);
        const modelsClient = apiFactory.getModelsClient();
        const result = await modelsClient.testModelConnection(modelId);

        setModelValidationStatus(prev =>
          new Map(prev).set(modelId, {
            isValid: result.status === 'success',
            isValidating: false,
            errorMessage:
              result.status === 'success' ? undefined : result.message,
          })
        );
      } catch (error) {
        console.error('[MODEL_VALIDATION] Error:', error);
        const errorMessage =
          error instanceof Error
            ? error.message
            : 'Failed to validate model configuration';
        setModelValidationStatus(prev =>
          new Map(prev).set(modelId, {
            isValid: false,
            isValidating: false,
            errorMessage,
          })
        );
      }
    },
    [session?.session_token]
  );

  // Validate default models whenever they change
  useEffect(() => {
    if (!session?.session_token || connectedModels.length === 0) return;

    const defaultGenerationId = userSettings?.models?.generation?.model_id;
    const defaultEvaluationId = userSettings?.models?.evaluation?.model_id;
    const defaultExecutionId = userSettings?.models?.execution?.model_id;
    const defaultEmbeddingId = userSettings?.models?.embedding?.model_id;

    setModelValidationStatus(prev => {
      const newStatus = new Map(prev);
      connectedModels.forEach(model => {
        const isDefault =
          model.id === defaultGenerationId ||
          model.id === defaultEvaluationId ||
          model.id === defaultExecutionId ||
          model.id === defaultEmbeddingId;
        if (!isDefault && newStatus.has(model.id)) {
          newStatus.delete(model.id);
        }
      });
      return newStatus;
    });

    if (defaultGenerationId) {
      const m = connectedModels.find(m => m.id === defaultGenerationId);
      if (m) validateModel(m.id);
    }
    if (defaultEvaluationId) {
      const m = connectedModels.find(m => m.id === defaultEvaluationId);
      if (m && m.id !== defaultGenerationId) validateModel(m.id);
    }
    if (defaultExecutionId) {
      const m = connectedModels.find(m => m.id === defaultExecutionId);
      if (m && m.id !== defaultGenerationId && m.id !== defaultEvaluationId)
        validateModel(m.id);
    }
    if (defaultEmbeddingId) {
      const m = connectedModels.find(m => m.id === defaultEmbeddingId);
      if (
        m &&
        m.id !== defaultGenerationId &&
        m.id !== defaultEvaluationId &&
        m.id !== defaultExecutionId
      )
        validateModel(m.id);
    }
  }, [
    connectedModels,
    userSettings?.models?.generation?.model_id,
    userSettings?.models?.evaluation?.model_id,
    userSettings?.models?.execution?.model_id,
    userSettings?.models?.embedding?.model_id,
    session?.session_token,
    validateModel,
  ]);

  const handleConnect = async (
    _providerId: string,
    modelData: ModelCreate
  ): Promise<Model> => {
    if (!session?.session_token) throw new Error('No session token');
    const apiFactory = new ApiClientFactory(session.session_token);
    const modelsClient = apiFactory.getModelsClient();
    const model = await modelsClient.createModel(modelData);
    setConnectedModels(prev => [...prev, model]);
    return model;
  };

  const handleCardClick = (model: Model) => {
    setModelToEdit(model);
    setSelectedModelType(model.model_type || 'language');
    setAddModelDrawerOpen(true);
  };

  const handleUpdate = async (modelId: UUID, updates: Partial<ModelCreate>) => {
    if (!session?.session_token) return;
    const apiFactory = new ApiClientFactory(session.session_token);
    const modelsClient = apiFactory.getModelsClient();
    const updatedModel = await modelsClient.updateModel(modelId, updates);
    setConnectedModels(prev =>
      prev.map(model => (model.id === modelId ? updatedModel : model))
    );
    if (
      userSettings?.models?.generation?.model_id === modelId ||
      userSettings?.models?.evaluation?.model_id === modelId ||
      userSettings?.models?.execution?.model_id === modelId ||
      userSettings?.models?.embedding?.model_id === modelId
    ) {
      validateModel(modelId);
    }
  };

  const handleDeleteClick = (model: Model) => {
    setModelToDelete(model);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!session?.session_token || !modelToDelete) return;
    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const modelsClient = apiFactory.getModelsClient();
      await modelsClient.deleteModel(modelToDelete.id);
      setConnectedModels(prev =>
        prev.filter(model => model.id !== modelToDelete.id)
      );
      setDeleteDialogOpen(false);
      setModelToDelete(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete model');
    }
  };

  const handleRequestPolyphemusAccess = (_model: Model) => {
    setPolyphemusModalOpen(true);
  };

  const handlePolyphemusAccessSuccess = async () => {
    await refreshUserSettings();
  };

  // Filter models by type and search query
  const typeFilterOptions: { value: ModelTypeFilter; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'language', label: 'Language' },
    { value: 'embedding', label: 'Embedding' },
  ];

  const filteredModels = connectedModels.filter(model => {
    const typeMatch =
      modelTypeFilter === 'all' ||
      (modelTypeFilter === 'language'
        ? !model.model_type || model.model_type === 'language'
        : model.model_type === modelTypeFilter);

    const q = searchQuery.toLowerCase();
    const searchMatch =
      !q ||
      model.name?.toLowerCase().includes(q) ||
      model.description?.toLowerCase().includes(q) ||
      model.model_name?.toLowerCase().includes(q);

    const providerMatch =
      drawerFilters.providers.length === 0 ||
      (model.provider_type?.type_value &&
        drawerFilters.providers.includes(model.provider_type.type_value));

    const statusMatch =
      drawerFilters.status === '' ||
      model.status?.name?.toLowerCase() === drawerFilters.status.toLowerCase();

    return typeMatch && searchMatch && providerMatch && statusMatch;
  });

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="models" />;

  return (
    <PageLayout
      title="Models"
      description="Connect language models for test generation and language-model-as-judge evaluation, and embedding models for platform use. Set your defaults for generation, evaluation, and execution."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Can capability={Capability.Model.CREATE}>
            <Fab
              icon={<FabAddIcon />}
              tooltip="Add model"
              aria-label="Add model"
              onClick={handleFabClick}
            />
            <Menu
              anchorEl={fabAnchorEl}
              open={fabMenuOpen}
              onClose={handleFabMenuClose}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
              <MenuItem onClick={handleAddLanguageModel}>
                Language model
              </MenuItem>
              <MenuItem onClick={handleAddEmbeddingModel}>
                Embedding model
              </MenuItem>
            </Menu>
          </Can>
        </FabGroup>
      }
    >
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <GridToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search models..."
        onFilterClick={() => setFilterDrawerOpen(true)}
        hasActiveFilters={hasActiveModelFilters(drawerFilters)}
        activeFilterCount={countActiveModelFilters(drawerFilters)}
        {...directoryToolbarProps}
        middleContent={
          <ToolbarPillTabs
            tabs={typeFilterOptions}
            activeValue={modelTypeFilter}
            onChange={v => setModelTypeFilter(v as ModelTypeFilter)}
          />
        }
      />

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : filteredModels.length === 0 ? (
        <Box sx={{ py: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            {connectedModels.length === 0
              ? 'No models connected yet. Use the + button to add one.'
              : 'No models match your search.'}
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
          {filteredModels.map(model => (
            <ConnectedModelCard
              key={model.id}
              model={model}
              userSettings={userSettings}
              isVerified={userSettings?.is_verified}
              validationStatus={modelValidationStatus.get(model.id)}
              onCardClick={canEditModel ? handleCardClick : undefined}
              onDelete={canDeleteModel ? handleDeleteClick : undefined}
              onRequestAccess={handleRequestPolyphemusAccess}
            />
          ))}
        </Box>
      )}

      <ModelFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        providerOptions={providerTypes}
        statusOptions={statusOptions}
        onApply={setDrawerFilters}
      />

      <ModelConnectionDrawer
        open={addModelDrawerOpen}
        onClose={() => {
          setAddModelDrawerOpen(false);
          setTimeout(() => {
            setModelToEdit(null);
          }, 200);
        }}
        providers={providerTypes}
        modelType={selectedModelType}
        model={modelToEdit}
        mode={modelToEdit ? 'edit' : 'create'}
        userSettings={userSettings}
        onConnect={handleConnect}
        onUpdate={handleUpdate}
        onUserSettingsUpdate={refreshUserSettings}
      />

      <DeleteModal
        open={deleteDialogOpen}
        onClose={() => {
          setDeleteDialogOpen(false);
          setModelToDelete(null);
        }}
        onConfirm={handleDeleteConfirm}
        itemType="model connection"
        itemName={modelToDelete?.name}
        title="Delete Model Connection"
      />

      <PolyphemusAccessModal
        open={polyphemusModalOpen}
        onClose={() => setPolyphemusModalOpen(false)}
        onSuccess={handlePolyphemusAccessSuccess}
        userEmail={session?.user?.email || ''}
        organization={organization ?? undefined}
      />
    </PageLayout>
  );
}
