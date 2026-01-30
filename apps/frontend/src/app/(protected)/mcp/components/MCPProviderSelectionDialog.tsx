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

  // Custom order: Notion first, then GitHub, then Jira, then Confluence, then custom
  const providerOrder: Record<string, number> = {
    notion: 1,
    github: 2,
    jira: 3,
    confluence: 4,
    custom: 5,
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
            // Enable Notion, GitHub, Jira, Confluence, and custom providers
            const isEnabled =
              provider.type_value === 'notion' ||
              provider.type_value === 'github' ||
              provider.type_value === 'jira' ||
              provider.type_value === 'confluence' ||
              provider.type_value === 'custom';

            // Use clean provider names based on type_value
            let providerName: string;
            switch (provider.type_value) {
              case 'notion':
                providerName = 'Notion';
                break;
              case 'github':
                providerName = 'GitHub';
                break;
              case 'jira':
                providerName = 'Jira';
                break;
              case 'confluence':
                providerName = 'Confluence';
                break;
              case 'atlassian':
                providerName = 'Atlassian';
                break;
              case 'custom':
                providerName = 'Custom provider';
                break;
              default:
                providerName = provider.type_value;
            }

            const providerInfo = {
              id: provider.type_value,
              name: providerName,
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
