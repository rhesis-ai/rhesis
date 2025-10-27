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
  PROVIDER_ICONS,
  type ProviderInfo,
} from '@/config/model-providers';

interface ProviderSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelectProvider: (provider: TypeLookup) => void;
  providers: TypeLookup[];
}

export function ProviderSelectionDialog({
  open,
  onClose,
  onSelectProvider,
  providers,
}: ProviderSelectionDialogProps) {
  // Filter out system-managed providers (like 'rhesis') that users cannot create
  const userSelectableProviders = providers.filter(
    provider => provider.type_value !== 'rhesis'
  );

  if (!userSelectableProviders || userSelectableProviders.length === 0) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>Select LLM Provider</DialogTitle>
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

  // Sort providers: enabled first (alphabetically), then coming soon (alphabetically)
  const sortedProviders = [...userSelectableProviders].sort((a, b) => {
    const aSupported = SUPPORTED_PROVIDERS.includes(a.type_value);
    const bSupported = SUPPORTED_PROVIDERS.includes(b.type_value);

    // If support status differs, supported comes first
    if (aSupported !== bSupported) {
      return bSupported ? 1 : -1;
    }

    // Within same support status, sort alphabetically
    return a.type_value.localeCompare(b.type_value);
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Select Model Provider</DialogTitle>
      <DialogContent>
        <List>
          {sortedProviders.map(provider => {
            const isSupported = SUPPORTED_PROVIDERS.includes(
              provider.type_value
            );
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
                onClick={() => isSupported && onSelectProvider(provider)}
                disabled={!isSupported}
                sx={{
                  borderRadius: theme => theme.shape.borderRadius * 0.25,
                  my: 0.5,
                  opacity: isSupported ? 1 : 0.5,
                  cursor: isSupported ? 'pointer' : 'not-allowed',
                  '&:hover': {
                    backgroundColor: isSupported
                      ? 'action.hover'
                      : 'transparent',
                  },
                  '&.Mui-disabled': {
                    opacity: 0.5,
                  },
                }}
              >
                <ListItemIcon sx={{ opacity: isSupported ? 1 : 0.4 }}>
                  {providerInfo.icon}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography>{providerInfo.name}</Typography>
                      {!isSupported && (
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
                  secondary={providerInfo.description}
                  secondaryTypographyProps={{
                    sx: { opacity: isSupported ? 1 : 0.6 },
                  }}
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
