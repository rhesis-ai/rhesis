'use client';

import React from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  List,
  ListItemButton,
  ListItemText,
  Typography,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import BaseDrawer from '@/components/common/BaseDrawer';
import EndpointsIcon from '@/components/EndpointsIcon';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import {
  EndpointOption,
  formatEnvironment,
  formatEndpointLabel,
  getEnvironmentColor,
} from './playgroundEndpointUtils';

interface PlaygroundEndpointDrawerProps {
  open: boolean;
  onClose: () => void;
  endpointOptions: EndpointOption[];
  selectedEndpointId: string | null;
  isLoading: boolean;
  error: string | null;
  onSelect: (endpointId: string) => void;
}

export default function PlaygroundEndpointDrawer({
  open,
  onClose,
  endpointOptions,
  selectedEndpointId,
  isLoading,
  error,
  onSelect,
}: PlaygroundEndpointDrawerProps) {
  const handleSelect = (endpointId: string) => {
    onSelect(endpointId);
    onClose();
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Select Endpoint"
      titleIcon={<EndpointsIcon />}
      closeButtonText="Close"
    >
      {isLoading ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 2 }}>
          <CircularProgress size={20} />
          <Typography variant="body2" color="text.secondary">
            Loading endpoints...
          </Typography>
        </Box>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : endpointOptions.length === 0 ? (
        <Alert severity="info">
          No endpoints available. Please create an endpoint in a project first.
        </Alert>
      ) : (
        <List disablePadding sx={{ mx: -1 }}>
          {endpointOptions.map(option => {
            const isSelected = option.endpointId === selectedEndpointId;
            return (
              <ListItemButton
                key={option.endpointId}
                selected={isSelected}
                onClick={() => handleSelect(option.endpointId)}
                sx={{
                  borderRadius: BORDER_RADIUS.sm,
                  mb: 0.5,
                  alignItems: 'flex-start',
                }}
              >
                <ListItemText
                  primary={formatEndpointLabel(option)}
                  primaryTypographyProps={{
                    variant: 'body2',
                    sx: { color: theme => theme.palette.greyscale.body },
                  }}
                  secondary={
                    <Typography
                      component="span"
                      variant="caption"
                      sx={{
                        display: 'inline-block',
                        mt: 0.5,
                        px: 1,
                        py: 0.25,
                        borderRadius: BORDER_RADIUS.pill,
                        bgcolor: theme => theme.palette.greyscale.surface2,
                        color: getEnvironmentColor(option.environment),
                        fontWeight: 600,
                      }}
                    >
                      {formatEnvironment(option.environment)}
                    </Typography>
                  }
                />
                {isSelected && (
                  <CheckIcon
                    fontSize="small"
                    sx={{ color: 'primary.main', mt: 0.5 }}
                  />
                )}
              </ListItemButton>
            );
          })}
        </List>
      )}
    </BaseDrawer>
  );
}
