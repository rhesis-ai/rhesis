'use client';

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
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';

export interface ProviderDialogChip {
  label: string;
}

export interface ProviderDialogItem {
  provider: TypeLookup;
  name: string;
  icon: React.ReactNode;
  enabled: boolean;
  chips?: ProviderDialogChip[];
}

export interface ProviderSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelectProvider: (provider: TypeLookup) => void;
  title: string;
  items: ProviderDialogItem[];
  emptyMessage?: string;
}

/**
 * Shared provider picker dialog (models, MCP, etc.).
 * Callers supply pre-sorted items with enablement and chip metadata.
 */
export function ProviderSelectionDialog({
  open,
  onClose,
  onSelectProvider,
  title,
  items,
  emptyMessage = 'No providers available. Please try again later.',
}: ProviderSelectionDialogProps) {
  if (items.length === 0) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>{title}</DialogTitle>
        <DialogContent>
          <Box sx={{ py: 2, textAlign: 'center' }}>
            <Typography color="text.secondary">{emptyMessage}</Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <List>
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
                  backgroundColor: item.enabled
                    ? 'action.hover'
                    : 'transparent',
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
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
}

export default ProviderSelectionDialog;
