'use client';

import React from 'react';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';
import { useSession } from 'next-auth/react';
import { useEndpointOptions } from '@/hooks/useEndpoints';
import EndpointSelectField from '@/components/common/EndpointSelectField';

interface EndpointSelectorProps {
  selectedEndpointId: string | null;
  onEndpointChange: (endpointId: string | null) => void;
  /** Skip fetching until true — for instances mounted inside a `keepMounted` drawer/dialog that isn't open yet. */
  enabled?: boolean;
}

/**
 * Endpoint selector for test generation live-response preview.
 */
export default function EndpointSelector({
  selectedEndpointId,
  onEndpointChange,
  enabled = true,
}: EndpointSelectorProps) {
  const { data: session } = useSession();
  const {
    options: endpointOptions,
    isLoading,
    error: optionsError,
  } = useEndpointOptions(session?.session_token ?? '', enabled);
  const error = optionsError
    ? 'Failed to load endpoints. Please try again.'
    : null;

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
    <EndpointSelectField
      label="Select Endpoint"
      placeholder="Choose an endpoint"
      value={selectedEndpointId}
      onChange={onEndpointChange}
      options={endpointOptions}
      selectId="test-preview-endpoint-select"
      helperText="Test samples will show live responses from this endpoint in the next step."
    />
  );
}
