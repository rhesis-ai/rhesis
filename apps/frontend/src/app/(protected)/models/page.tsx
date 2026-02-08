'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Alert, CircularProgress } from '@mui/material';
import { PageContainer } from '@toolpad/core/PageContainer';
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
  AddModelCard,
} from './components';
import type { ValidationStatus } from './types';

export type { ValidationStatus } from './types';

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

        // Load provider types first
        const types = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'ProviderType'",
          limit: 100, // Fetch all providers (default is 10)
        });
        setProviderTypes(types);

        // Load user settings
        try {
          const settings = await usersClient.getUserSettings();
          setUserSettings(settings);
        } catch {
          // Failed to load user settings - continue without them
        }

        // Then load connected models
        try {
          const modelsResponse = await modelsClient.getModels();
          setConnectedModels(modelsResponse.data);
        } catch {
          // Failed to load models - will show empty state
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

  const handleAddLLM = () => {
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
        new Map(prev).set(modelId, {
          isValid: false,
          isValidating: true,
        })
      );

      try {
        const apiFactory = new ApiClientFactory(session.session_token);
        const modelsClient = apiFactory.getModelsClient();
        const result = await modelsClient.testModelConnection(modelId);

        console.log('[MODEL_VALIDATION] Result:', result);

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

        // Extract the actual error message from the API response
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

  // Validate any models set as defaults (generation or evaluation)
  // This ensures users are warned if their default models are misconfigured
  // and clears warnings for models that are no longer defaults
  useEffect(() => {
    if (!session?.session_token || connectedModels.length === 0) {
      return;
    }

    const defaultGenerationId = userSettings?.models?.generation?.model_id;
    const defaultEvaluationId = userSettings?.models?.evaluation?.model_id;

    // Clear validation status for models that are NOT currently defaults
    setModelValidationStatus(prev => {
      const newStatus = new Map(prev);
      connectedModels.forEach(model => {
        const isDefault =
          model.id === defaultGenerationId || model.id === defaultEvaluationId;
        if (!isDefault && newStatus.has(model.id)) {
          // Remove validation status for non-default models
          newStatus.delete(model.id);
        }
      });
      return newStatus;
    });

    // Validate default generation model
    if (defaultGenerationId) {
      const defaultGenerationModel = connectedModels.find(
        m => m.id === defaultGenerationId
      );
      if (defaultGenerationModel) {
        validateModel(defaultGenerationModel.id);
      }
    }

    // Validate default evaluation model
    if (defaultEvaluationId) {
      const defaultEvaluationModel = connectedModels.find(
        m => m.id === defaultEvaluationId
      );
      // Only validate if it's different from generation model
      if (
        defaultEvaluationModel &&
        defaultEvaluationModel.id !== defaultGenerationId
      ) {
        validateModel(defaultEvaluationModel.id);
      }
    }
  }, [
    connectedModels,
    userSettings?.models?.generation?.model_id,
    userSettings?.models?.evaluation?.model_id,
    session?.session_token,
    validateModel,
  ]);

  const handleConnect = async (
    providerId: string,
    modelData: ModelCreate
  ): Promise<Model> => {
    if (!session?.session_token) {
      throw new Error('No session token');
    }

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const modelsClient = apiFactory.getModelsClient();

      const model = await modelsClient.createModel(modelData);
      setConnectedModels(prev => [...prev, model]);
      return model;
    } catch (err) {
      throw err;
    }
  };

  const handleEditClick = (model: Model, event: React.MouseEvent) => {
    event.stopPropagation();
    setModelToEdit(model);
    setSelectedProvider(model.provider_type || null);
    setConnectionDialogOpen(true);
  };

  const handleUpdate = async (modelId: UUID, updates: Partial<ModelCreate>) => {
    if (!session?.session_token) return;

    try {
      const apiFactory = new ApiClientFactory(session.session_token);
      const modelsClient = apiFactory.getModelsClient();

      const updatedModel = await modelsClient.updateModel(modelId, updates);
      setConnectedModels(prev =>
        prev.map(model => (model.id === modelId ? updatedModel : model))
      );

      // Re-validate if this is a default model (generation or evaluation)
      if (
        userSettings?.models?.generation?.model_id === modelId ||
        userSettings?.models?.evaluation?.model_id === modelId
      ) {
        validateModel(modelId);
      }
    } catch (err) {
      throw err;
    }
  };

  const handleDeleteClick = (model: Model, event: React.MouseEvent) => {
    event.stopPropagation();
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

  return (
    <PageContainer title="Models" breadcrumbs={[]}>
      <Box sx={{ mb: 3 }}>
        <Typography color="text.secondary">
          Connect to leading AI model providers to power your evaluation and
          testing workflows.
        </Typography>
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
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
          {/* Connected Model Cards */}
          {connectedModels.map(model => (
            <ConnectedModelCard
              key={model.id}
              model={model}
              userSettings={userSettings}
              validationStatus={modelValidationStatus.get(model.id)}
              onEdit={handleEditClick}
              onDelete={handleDeleteClick}
            />
          ))}

          {/* Add Model Card */}
          <AddModelCard onClick={handleAddLLM} />
        </Box>
      )}

      <ProviderSelectionDialog
        open={providerSelectionOpen}
        onClose={() => setProviderSelectionOpen(false)}
        onSelectProvider={handleProviderSelect}
        providers={providerTypes}
      />

      <ConnectionDialog
        open={connectionDialogOpen}
        provider={selectedProvider}
        model={modelToEdit}
        mode={modelToEdit ? 'edit' : 'create'}
        userSettings={userSettings}
        onClose={() => {
          setConnectionDialogOpen(false);
          // Delay clearing state to prevent button text flicker during closing animation
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
    </PageContainer>
  );
}
