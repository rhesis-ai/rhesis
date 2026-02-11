import React from 'react';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Typography,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import {
  SUPPORTED_PROVIDERS,
  LOCAL_PROVIDERS,
  EMBEDDING_PROVIDERS,
  PROVIDER_ICONS,
  type ProviderInfo,
} from '@/config/model-providers';

interface ProviderSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelectProvider: (provider: TypeLookup) => void;
  providers: TypeLookup[];
  modelType?: 'llm' | 'embedding';
}

export function ProviderSelectionDialog({
  open,
  onClose,
  onSelectProvider,
  providers,
  modelType = 'llm',
}: ProviderSelectionDialogProps) {
  // Filter out system-managed providers (like 'rhesis') that users cannot create
  // and filter by model type (embedding providers for embedding models)
  const userSelectableProviders = providers.filter(provider => {
    if (provider.type_value === 'rhesis') return false;

    // For embedding models, only show providers that support embeddings
    if (modelType === 'embedding') {
      return EMBEDDING_PROVIDERS.includes(provider.type_value);
    }

    // For LLM models, show all supported providers
    return true;
  });

  // Check if frontend is running in local mode by detecting localhost in the app URL
  const isLocalMode =
    process.env.NEXT_PUBLIC_APP_URL?.includes('localhost') || false;

  if (!userSelectableProviders || userSelectableProviders.length === 0) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>
          {modelType === 'embedding'
            ? 'Select Embedder Provider'
            : 'Select LLM Provider'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ py: 2, textAlign: 'center' }}>
            <Typography color="text.secondary">
              No providers available. Please try again later.
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  }

  // Sort providers: supported first, then local deployment, then unsupported (all alphabetically)
  const sortedProviders = [...userSelectableProviders].sort((a, b) => {
    const aSupported = SUPPORTED_PROVIDERS.includes(a.type_value);
    const bSupported = SUPPORTED_PROVIDERS.includes(b.type_value);
    const aLocal = LOCAL_PROVIDERS.includes(a.type_value);
    const bLocal = LOCAL_PROVIDERS.includes(b.type_value);

    // Determine tier for each provider
    // Tier 1: Supported and not local (fully enabled)
    // Tier 2: Local deployment (supported but local-only)
    // Tier 3: Not supported (coming soon)
    const getTier = (isSupported: boolean, isLocal: boolean) => {
      if (isSupported && !isLocal) return 1;
      if (isLocal) return 2;
      return 3;
    };

    const aTier = getTier(aSupported, aLocal);
    const bTier = getTier(bSupported, bLocal);

    // If tiers differ, sort by tier
    if (aTier !== bTier) {
      return aTier - bTier;
    }

    // Within same tier, sort alphabetically
    return a.type_value.localeCompare(b.type_value);
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {modelType === 'embedding'
          ? 'Select Embedder Provider'
          : 'Select LLM Provider'}
      </DialogTitle>
      <DialogContent>
        <List>
          {sortedProviders.map(provider => {
            const isSupported = SUPPORTED_PROVIDERS.includes(
              provider.type_value
            );
            const isLocal = LOCAL_PROVIDERS.includes(provider.type_value);
            // Enable local providers only when FRONTEND_ENV is 'local'
            const isEnabled = isSupported && (!isLocal || isLocalMode);

            const providerInfo: ProviderInfo = {
              id: provider.type_value,
              name: provider.description || provider.type_value,
              description: provider.description || '',
              icon: PROVIDER_ICONS[provider.type_value] || (
                <SmartToyIcon
                  sx={{ fontSize: theme => theme.iconSizes.large }}
                />
              ),
            };

            return (
              <ListItemButton
                key={provider.id}
                onClick={() => isEnabled && onSelectProvider(provider)}
                disabled={!isEnabled}
                sx={{
                  borderRadius: theme => theme.shape.borderRadius * 0.25,
                  my: 0.5,
                  opacity: isEnabled ? 1 : 0.5,
                  cursor: isEnabled ? 'pointer' : 'not-allowed',
                  '&:hover': {
                    backgroundColor: isEnabled ? 'action.hover' : 'transparent',
                  },
                  '&.Mui-disabled': {
                    opacity: 0.5,
                  },
                }}
              >
                <ListItemIcon sx={{ opacity: isEnabled ? 1 : 0.4 }}>
                  {providerInfo.icon}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography>{providerInfo.name}</Typography>
                      {isLocal && (
                        <Chip
                          label="Local deployment"
                          size="small"
                          color="default"
                          sx={{
                            height: 20,
                            fontSize: theme =>
                              theme.typography.caption.fontSize,
                            fontWeight: 500,
                          }}
                        />
                      )}
                      {!isSupported && !isLocal && (
                        <Chip
                          label="Coming Soon"
                          size="small"
                          color="default"
                          sx={{
                            height: 20,
                            fontSize: theme =>
                              theme.typography.caption.fontSize,
                            fontWeight: 500,
                          }}
                        />
                      )}
                    </Box>
                  }
                />
              </ListItemButton>
            );
          })}
        </List>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
}
