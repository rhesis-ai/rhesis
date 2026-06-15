'use client';

import React from 'react';
import {
  Box,
  Chip,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import {
  SUPPORTED_PROVIDERS,
  LOCAL_PROVIDERS,
  EMBEDDING_PROVIDERS,
  PROVIDER_ICONS,
} from '@/config/model-providers';

interface ProviderItem {
  provider: TypeLookup;
  name: string;
  icon: React.ReactNode;
  enabled: boolean;
  chips?: { label: string }[];
}

function buildModelProviderItems(
  providers: TypeLookup[],
  modelType: 'language' | 'embedding'
): ProviderItem[] {
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
    const chips: { label: string }[] = [];
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

interface ProviderSelectionPanelProps {
  providers: TypeLookup[];
  modelType: 'language' | 'embedding';
  onSelectProvider: (provider: TypeLookup) => void;
}

export function ProviderSelectionPanel({
  providers,
  modelType,
  onSelectProvider,
}: ProviderSelectionPanelProps) {
  const items = buildModelProviderItems(providers, modelType);

  if (items.length === 0) {
    return (
      <Box sx={{ py: 4, textAlign: 'center' }}>
        <Typography color="text.secondary">
          No providers available. Please try again later.
        </Typography>
      </Box>
    );
  }

  return (
    <List disablePadding>
      {items.map(item => (
        <ListItemButton
          key={item.provider.id}
          onClick={() => item.enabled && onSelectProvider(item.provider)}
          disabled={!item.enabled}
          sx={{
            borderRadius: theme => theme.shape.borderRadius * 0.25,
            my: 0.5,
            opacity: item.enabled ? 1 : 0.5,
            cursor: item.enabled ? 'pointer' : 'not-allowed',
            '&:hover': {
              backgroundColor: item.enabled ? 'action.hover' : 'transparent',
            },
            '&.Mui-disabled': { opacity: 0.5 },
          }}
        >
          <ListItemIcon sx={{ opacity: item.enabled ? 1 : 0.4 }}>
            {item.icon}
          </ListItemIcon>
          <ListItemText
            primary={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography>{item.name}</Typography>
                {item.chips?.map(chip => (
                  <Chip
                    key={chip.label}
                    label={chip.label}
                    size="small"
                    color="default"
                    sx={{
                      height: 20,
                      fontSize: theme => theme.typography.caption.fontSize,
                      fontWeight: 500,
                    }}
                  />
                ))}
              </Box>
            }
          />
        </ListItemButton>
      ))}
    </List>
  );
}
