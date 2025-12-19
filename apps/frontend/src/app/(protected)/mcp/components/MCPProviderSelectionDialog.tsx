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

  // Custom order: Notion first, then custom, then GitHub, then Atlassian
  const providerOrder: Record<string, number> = {
    notion: 1,
    github: 2,
    custom: 3,
    atlassian: 4,
  };

  const sortedProviders = [...providers].sort((a, b) => {
    const aOrder = providerOrder[a.type_value] ?? 999;
    const bOrder = providerOrder[b.type_value] ?? 999;
    return aOrder - bOrder;
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
            // Enable Notion, custom, and GitHub providers
            const isEnabled =
              provider.type_value === 'notion' ||
              provider.type_value === 'github' ||
              provider.type_value === 'custom';

            // Customize provider names and descriptions
            let providerName = provider.description || provider.type_value;
            let providerDescription = provider.description || '';

            // Clean up provider names
            if (provider.type_value === 'notion') {
              providerName = providerName
                .replace(/\s*integration$/i, '')
                .trim();
            } else if (provider.type_value === 'custom') {
              providerName = providerName
                .replace(/\s*with manual configuration$/i, '')
                .trim();
            } else if (provider.type_value === 'atlassian') {
              providerName = providerName
                .replace(/\s*for jira and confluence$/i, '')
                .trim();
              providerDescription = providerDescription
                .replace(/\s*for jira and confluence$/i, '')
                .trim();
            } else if (provider.type_value === 'github') {
              providerName = providerName.replace(/\s*repository$/i, '').trim();
              providerDescription = providerDescription
                .replace(/\s*repository$/i, '')
                .trim();
            }

            const providerInfo: MCPProviderInfo = {
              id: provider.type_value,
              name: providerName,
              description: providerDescription,
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
                      {!isEnabled && !isCustom && (
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
