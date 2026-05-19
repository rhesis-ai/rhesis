'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Box, Alert, CircularProgress, Typography } from '@mui/material';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import AddIcon from '@mui/icons-material/Add';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab } from '@/components/common/Fab';
import { SearchPill } from '@/components/common/SearchPill';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Model, ModelCreate } from '@/utils/api-client/interfaces/model';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import { DeleteModal } from '@/components/common/DeleteModal';
import { UUID } from 'crypto';
import {
  ProviderSelectionDialog,
  ConnectionDialog,
  ConnectedModelCard,
} from './components';
import PolyphemusAccessModal from '@/components/common/PolyphemusAccessModal';
import { BORDER_RADIUS } from '@/styles/theme';
import type { ValidationStatus } from './types';

export type { ValidationStatus } from './types';

type ModelTypeFilter = 'all' | 'language' | 'embedding';

export default function ModelsPage() {
  const { data: session } = useSession();
  const [connectedModels, setConnectedModels] = useState<Model[]>([]);
  const [providerTypes, setProviderTypes] = useState<TypeLookup[]>([]);
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modelValidationStatus, setModelValidationStatus] = useState<
    Map<string, ValidationStatus>
  >(new Map());
  const [selectedProvider, setSelectedProvider] = useState<TypeLookup | null>(
    null
  );
  const [providerSelectionOpen, setProviderSelectionOpen] = useState(false);
  const [connectionDialogOpen, setConnectionDialogOpen] = useState(false);
  const [modelToEdit, setModelToEdit] = useState<Model | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [modelToDelete, setModelToDelete] = useState<Model | null>(null);
  const [selectedModelType, setSelectedModelType] = useState<
    'language' | 'embedding'
  >('language');
  const [polyphemusModalOpen, setPolyphemusModalOpen] = useState(false);
  const [organization, setOrganization] = useState<any>(null);

  // Toolbar state
  const [searchQuery, setSearchQuery] = useState('');
  const [modelTypeFilter, setModelTypeFilter] =
    useState<ModelTypeFilter>('all');

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

        const types = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'ProviderType'",
          limit: 100,
        });
        setProviderTypes(types);

        try {
          const settings = await usersClient.getUserSettings();
          setUserSettings(settings);
        } catch {
          // continue without user settings
        }

        if (session.user?.organization_id) {
          try {
            const organizationsClient = apiFactory.getOrganizationsClient();
            const org = await organizationsClient.getOrganization(
              session.user.organization_id
            );
            setOrganization(org);
          } catch {
            // continue without organization
          }
        }

        try {
          const modelsResponse = await modelsClient.getModels();
          setConnectedModels(modelsResponse.data);
        } catch {
          // show empty state
        }
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
    setProviderSelectionOpen(true);
  };

  const handleAddEmbeddingModel = () => {
    handleFabMenuClose();
    setSelectedModelType('embedding');
    setProviderSelectionOpen(true);
  };

  const handleProviderSelect = (provider: TypeLookup) => {
    setSelectedProvider(provider);
    setProviderSelectionOpen(false);
    setConnectionDialogOpen(true);
  };

  const refreshUserSettings = async () => {
    if (!session?.session_token) return;
    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const usersClient = apiFactory.getUsersClient();
      const settings = await usersClient.getUserSettings();
      setUserSettings(settings);
    } catch (_err) {}
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

  const handleEditClick = (model: Model, event: React.MouseEvent) => {
    event.stopPropagation();
    setModelToEdit(model);
    setSelectedProvider(model.provider_type || null);
    setSelectedModelType(model.model_type || 'language');
    setConnectionDialogOpen(true);
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

    return typeMatch && searchMatch;
  });

  return (
    <PageLayout
      title="Models"
      description="Connect language models for test generation and language-model-as-judge evaluation, and embedding models for platform use. Set your defaults for generation, evaluation, and execution."
      breadcrumbs={[]}
      actions={
        <>
          <Fab
            icon={<AddIcon />}
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
            <MenuItem onClick={handleAddLanguageModel}>Language model</MenuItem>
            <MenuItem onClick={handleAddEmbeddingModel}>
              Embedding model
            </MenuItem>
          </Menu>
        </>
      }
    >
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Toolbar — 3-col grid mirroring metrics/behaviors */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: '1fr auto 1fr',
          alignItems: 'center',
          mb: 3,
          gap: 2,
        }}
      >
        {/* Left: Search pill */}
        <Box sx={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <SearchPill
            value={searchQuery}
            onChange={v => setSearchQuery(v)}
            placeholder="Search models..."
          />
        </Box>

        {/* Center: Type filter pill tabs */}
        <Box sx={{ display: 'flex', justifyContent: 'center' }}>
          {typeFilterOptions.map(({ value, label }, idx, arr) => {
            const isSelected = modelTypeFilter === value;
            const isFirst = idx === 0;
            const isLast = idx === arr.length - 1;
            return (
              <Box
                key={value}
                component="button"
                onClick={() => setModelTypeFilter(value)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  px: '16px',
                  py: '8px',
                  fontSize: 14,
                  fontWeight: 700,
                  lineHeight: '22px',
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: 'primary.main',
                  borderLeft: isFirst ? '1px solid' : 'none',
                  borderRight: isLast ? '1px solid' : 'none',
                  borderRadius: isFirst
                    ? `${BORDER_RADIUS.pill} 0 0 ${BORDER_RADIUS.pill}`
                    : isLast
                      ? `0 ${BORDER_RADIUS.pill} ${BORDER_RADIUS.pill} 0`
                      : 0,
                  bgcolor: isSelected ? 'primary.main' : 'transparent',
                  color: isSelected ? '#fff' : 'primary.main',
                  transition: 'background-color 0.15s, color 0.15s',
                  '&:hover': {
                    bgcolor: isSelected
                      ? 'primary.dark'
                      : theme => `${theme.palette.primary.main}0f`,
                  },
                  whiteSpace: 'nowrap',
                }}
              >
                {label}
              </Box>
            );
          })}
        </Box>
      </Box>

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
              onEdit={handleEditClick}
              onDelete={handleDeleteClick}
              onRequestAccess={handleRequestPolyphemusAccess}
            />
          ))}
        </Box>
      )}

      <ProviderSelectionDialog
        open={providerSelectionOpen}
        onClose={() => setProviderSelectionOpen(false)}
        onSelectProvider={handleProviderSelect}
        providers={providerTypes}
        modelType={selectedModelType}
      />

      <ConnectionDialog
        open={connectionDialogOpen}
        provider={selectedProvider}
        model={modelToEdit}
        mode={modelToEdit ? 'edit' : 'create'}
        modelType={selectedModelType}
        userSettings={userSettings}
        onClose={() => {
          setConnectionDialogOpen(false);
          setTimeout(() => {
            setSelectedProvider(null);
            setModelToEdit(null);
          }, 200);
        }}
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
        organization={organization}
      />
    </PageLayout>
  );
}
