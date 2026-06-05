'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { Model, ModelCreate } from '@/utils/api-client/interfaces/model';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import { UUID } from 'crypto';
import { PROVIDER_ICONS } from '@/config/model-providers';
import { ProviderSelectionPanel } from './ProviderSelectionPanel';
import { ConnectionForm, type ConnectionFormHandle } from './ConnectionForm';

type Step = 'select' | 'configure';

interface ModelConnectionDrawerProps {
  open: boolean;
  onClose: () => void;
  providers: TypeLookup[];
  modelType: 'language' | 'embedding';
  model?: Model | null;
  mode?: 'create' | 'edit';
  userSettings?: UserSettings | null;
  onConnect?: (providerId: string, modelData: ModelCreate) => Promise<Model>;
  onUpdate?: (modelId: UUID, updates: Partial<ModelCreate>) => Promise<void>;
  onUserSettingsUpdate?: () => Promise<void>;
}

export function ModelConnectionDrawer({
  open,
  onClose,
  providers,
  modelType,
  model,
  mode = 'create',
  userSettings,
  onConnect,
  onUpdate,
  onUserSettingsUpdate,
}: ModelConnectionDrawerProps) {
  const isEditMode = mode === 'edit';

  const [step, setStep] = useState<Step>(isEditMode ? 'configure' : 'select');
  const [selectedProvider, setSelectedProvider] = useState<TypeLookup | null>(
    null
  );
  const [formLoading, setFormLoading] = useState(false);
  const [formCanSave, setFormCanSave] = useState(false);

  const formRef = useRef<ConnectionFormHandle>(null);

  const resetState = useCallback(() => {
    setStep(isEditMode ? 'configure' : 'select');
    setSelectedProvider(null);
    setFormLoading(false);
    setFormCanSave(false);
  }, [isEditMode]);

  useEffect(() => {
    if (!open) {
      resetState();
    }
  }, [open, resetState]);

  // When mode/model changes (page switches from create to edit), sync step
  useEffect(() => {
    if (open) {
      setStep(isEditMode ? 'configure' : 'select');
    }
  }, [isEditMode, open]);

  const handleClose = () => {
    resetState();
    onClose();
  };

  const handleSelectProvider = (provider: TypeLookup) => {
    setSelectedProvider(provider);
    setStep('configure');
  };

  const handleBack = () => {
    setStep('select');
    setSelectedProvider(null);
    setFormCanSave(false);
  };

  // The effective provider: in edit mode use the model's provider, otherwise the selected one
  const activeProvider = isEditMode
    ? (model?.provider_type ?? null)
    : selectedProvider;

  // Compute the drawer title
  const displayName =
    isEditMode && model
      ? model.provider_type?.description ||
        model.provider_type?.type_value ||
        'Provider'
      : activeProvider?.description || activeProvider?.type_value || 'Provider';

  const providerIconKey =
    isEditMode && model
      ? model.icon || model.provider_type?.type_value || 'custom'
      : activeProvider?.type_value || 'custom';

  const providerIcon = PROVIDER_ICONS[providerIconKey] || (
    <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.medium }} />
  );

  const selectTitle =
    modelType === 'embedding'
      ? 'Select Embedder Provider'
      : 'Select Language Model Provider';

  const configureTitle = isEditMode
    ? `Edit ${displayName}`
    : `Connect to ${displayName}`;

  const saveButtonText = isEditMode ? 'Update' : 'Connect';

  if (step === 'select') {
    return (
      <BaseDrawer
        open={open}
        onClose={handleClose}
        title={selectTitle}
        closeButtonText="Cancel"
      >
        <ProviderSelectionPanel
          providers={providers}
          modelType={modelType}
          onSelectProvider={handleSelectProvider}
        />
      </BaseDrawer>
    );
  }

  // In create flow the footer "close" button goes back to provider selection.
  // In edit mode it fully closes the drawer.
  const configureOnClose = isEditMode ? handleClose : handleBack;
  const configureCloseLabel = isEditMode ? 'Cancel' : 'Back';

  return (
    <BaseDrawer
      open={open}
      onClose={configureOnClose}
      title={configureTitle}
      titleIcon={providerIcon}
      onSave={() => formRef.current?.submit()}
      saveButtonText={saveButtonText}
      saveDisabled={!formCanSave}
      loading={formLoading}
      closeButtonText={configureCloseLabel}
      width={640}
    >
      <ConnectionForm
        ref={formRef}
        open={open && step === 'configure'}
        provider={activeProvider}
        model={model}
        mode={mode}
        modelType={modelType}
        userSettings={userSettings}
        onClose={handleClose}
        onConnect={onConnect}
        onUpdate={onUpdate}
        onUserSettingsUpdate={onUserSettingsUpdate}
        onLoadingChange={setFormLoading}
        onCanSaveChange={setFormCanSave}
      />
    </BaseDrawer>
  );
}
