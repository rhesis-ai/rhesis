'use client';

import React from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  type SelectChangeEvent,
  MenuItem,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { useEndpointOptions } from '@/hooks/useEndpoints';

interface EndpointSelectorProps {
  selectedEndpointId: string | null;
  onEndpointChange: (endpointId: string | null) => void;
}

/**
 * EndpointSelector Component
 * Allows users to select an endpoint from available projects
 * Displays format: "Project Name > Endpoint Name (Environment)"
 */
export default function EndpointSelector({
  selectedEndpointId,
  onEndpointChange,
}: EndpointSelectorProps) {
  const { data: session } = useSession();
  const {
    options: endpointOptions,
    isLoading,
    error: optionsError,
  } = useEndpointOptions(session?.session_token ?? '');
  const error = optionsError
    ? 'Failed to load endpoints. Please try again.'
    : null;

  const handleChange = (event: SelectChangeEvent<string>) => {
    const value = event.target.value;
    onEndpointChange(value === '' ? null : value);
  };

  const formatEnvironment = (env: string) => {
    return env.charAt(0).toUpperCase() + env.slice(1);
  };

  const getEnvironmentColor = (env: string) => {
    switch (env.toLowerCase()) {
      case 'production':
        return 'error.main';
      case 'staging':
        return 'warning.main';
      case 'development':
        return 'info.main';
      default:
        return 'text.secondary';
    }
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 2 }}>
        <CircularProgress size={20} />
        <Typography variant="body2" color="text.secondary">
          Loading endpoints...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (endpointOptions.length === 0) {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        No endpoints available. Please create an endpoint in a project first.
      </Alert>
    );
  }

  return (
    <FormControl fullWidth sx={{ mb: 3 }}>
      <InputLabel id="endpoint-selector-label">
        Select Endpoint for Test Preview
      </InputLabel>
      <Select
        labelId="endpoint-selector-label"
        id="endpoint-selector"
        value={selectedEndpointId || ''}
        label="Select Endpoint for Test Preview"
        onChange={handleChange}
      >
        <MenuItem value="">
          <Typography variant="body2" color="text.secondary">
            None (Skip preview)
          </Typography>
        </MenuItem>
        {endpointOptions.map(option => (
          <MenuItem key={option.endpointId} value={option.endpointId}>
            <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <Typography variant="body2" sx={{ flexGrow: 1 }}>
                {option.projectName} › {option.endpointName}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  ml: 2,
                  px: 1,
                  py: 0.25,
                  borderRadius: theme => theme.shape.borderRadius / 4,
                  bgcolor: 'action.hover',
                  color: getEnvironmentColor(option.environment),
                  fontWeight: 'medium',
                }}
              >
                {formatEnvironment(option.environment)}
              </Typography>
            </Box>
          </MenuItem>
        ))}
      </Select>
      {selectedEndpointId && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
          Test samples will show live responses from this endpoint in the next
          step.
        </Typography>
      )}
    </FormControl>
  );
}
