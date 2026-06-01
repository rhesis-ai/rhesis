import React from 'react';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import {
  ProviderSelectionDialog as BaseProviderSelectionDialog,
  type ProviderDialogItem,
} from '@/components/common/ProviderSelectionDialog';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import {
  SUPPORTED_PROVIDERS,
  LOCAL_PROVIDERS,
  EMBEDDING_PROVIDERS,
  PROVIDER_ICONS,
} from '@/config/model-providers';

interface ProviderSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelectProvider: (provider: TypeLookup) => void;
  providers: TypeLookup[];
  modelType?: 'language' | 'embedding';
}

function buildModelProviderItems(
  providers: TypeLookup[],
  modelType: 'language' | 'embedding'
): ProviderDialogItem[] {
  const fe = process.env.NEXT_PUBLIC_FRONTEND_ENV?.toLowerCase();
  const isLocalMode = fe === 'local';

  const selectable = providers.filter(provider => {
    if (
      provider.type_value === 'rhesis' ||
      provider.type_value === 'polyphemus'
    ) {
      return false;
    }
    if (modelType === 'embedding') {
      return EMBEDDING_PROVIDERS.includes(provider.type_value);
    }
    return true;
  });

  const getTier = (isSupported: boolean, isLocal: boolean) => {
    if (isSupported && !isLocal) return 1;
    if (isLocal) return 2;
    return 3;
  };

  const sorted = [...selectable].sort((a, b) => {
    const aSupported = SUPPORTED_PROVIDERS.includes(a.type_value);
    const bSupported = SUPPORTED_PROVIDERS.includes(b.type_value);
    const aLocal = LOCAL_PROVIDERS.includes(a.type_value);
    const bLocal = LOCAL_PROVIDERS.includes(b.type_value);
    const aTier = getTier(aSupported, aLocal);
    const bTier = getTier(bSupported, bLocal);
    if (aTier !== bTier) return aTier - bTier;
    return a.type_value.localeCompare(b.type_value);
  });

  return sorted.map(provider => {
    const isSupported = SUPPORTED_PROVIDERS.includes(provider.type_value);
    const isLocal = LOCAL_PROVIDERS.includes(provider.type_value);
    const isEnabled = isSupported && (!isLocal || isLocalMode);
    const chips: ProviderDialogItem['chips'] = [];
    if (isLocal) chips.push({ label: 'Local deployment' });
    if (!isSupported && !isLocal) chips.push({ label: 'Coming Soon' });

    return {
      provider,
      name: provider.description || provider.type_value,
      icon: PROVIDER_ICONS[provider.type_value] || (
        <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />
      ),
      enabled: isEnabled,
      chips: chips.length > 0 ? chips : undefined,
    };
  });
}

export function ProviderSelectionDialog({
  open,
  onClose,
  onSelectProvider,
  providers,
  modelType = 'language',
}: ProviderSelectionDialogProps) {
  const title =
    modelType === 'embedding'
      ? 'Select Embedder Provider'
      : 'Select Language Model Provider';

  const items = buildModelProviderItems(providers, modelType);

  return (
    <BaseProviderSelectionDialog
      open={open}
      onClose={onClose}
      onSelectProvider={onSelectProvider}
      title={title}
      items={items}
    />
  );
}
