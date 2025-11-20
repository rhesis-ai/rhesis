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
  SUPPORTED_MCP_PROVIDERS,
  MCP_PROVIDER_ICONS,
  type MCPProviderInfo,
} from '@/config/mcp-providers';

interface MCPProviderSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelectProvider: (provider: TypeLookup) => void;
  providers: TypeLookup[];
}

export function MCPProviderSelectionDialog({
  open,
  onClose,
  onSelectProvider,
  providers,
}: MCPProviderSelectionDialogProps) {
  if (!providers || providers.length === 0) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>Select MCP Provider</DialogTitle>
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

  // Sort providers: supported first, then custom, then unsupported (all alphabetically)
  const sortedProviders = [...providers].sort((a, b) => {
    const aSupported = SUPPORTED_MCP_PROVIDERS.includes(a.type_value);
    const bSupported = SUPPORTED_MCP_PROVIDERS.includes(b.type_value);
    const aCustom = a.type_value === 'custom';
    const bCustom = b.type_value === 'custom';

    // Determine tier for each provider
    // Tier 1: Supported
    // Tier 2: Custom (Advanced)
    // Tier 3: Not supported (coming soon)
    const getTier = (isSupported: boolean, isCustom: boolean) => {
      if (isSupported) return 1;
      if (isCustom) return 2;
      return 3;
    };

    const aTier = getTier(aSupported, aCustom);
    const bTier = getTier(bSupported, bCustom);

    // If tiers differ, sort by tier
    if (aTier !== bTier) {
      return aTier - bTier;
    }

    // Within same tier, sort alphabetically
    return a.type_value.localeCompare(b.type_value);
  });

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Select MCP Provider</DialogTitle>
      <DialogContent>
        <List>
          {sortedProviders.map(provider => {
            const isSupported = SUPPORTED_MCP_PROVIDERS.includes(
              provider.type_value
            );
            const isCustom = provider.type_value === 'custom';
            const isEnabled = isSupported || isCustom;

            const providerInfo: MCPProviderInfo = {
              id: provider.type_value,
              name: provider.description || provider.type_value,
              description: provider.description || '',
              icon: MCP_PROVIDER_ICONS[provider.type_value] || (
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
                      {isCustom && (
                        <Chip
                          label="Advanced"
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
                      {!isSupported && !isCustom && (
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
                    sx: { opacity: isEnabled ? 1 : 0.6 },
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
