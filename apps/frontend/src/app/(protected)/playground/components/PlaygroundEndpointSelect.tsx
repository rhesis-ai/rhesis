'use client';

import React from 'react';
import { Alert, Box, CircularProgress, Typography } from '@mui/material';
import EndpointSelectField from '@/components/common/EndpointSelectField';
import type { EndpointOption } from '@/utils/endpoint-options';

interface PlaygroundEndpointSelectProps {
  endpointOptions: EndpointOption[];
  selectedEndpointId: string | null;
  isLoading: boolean;
  error: string | null;
  onSelect: (endpointId: string | null) => void;
}

export default function PlaygroundEndpointSelect({
  endpointOptions,
  selectedEndpointId,
  isLoading,
  error,
  onSelect,
}: PlaygroundEndpointSelectProps) {
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
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
    <Box sx={{ mb: 2 }}>
      <EndpointSelectField
        label="Select Endpoint"
        placeholder="Choose an endpoint"
        value={selectedEndpointId}
        onChange={onSelect}
        options={endpointOptions}
        selectId="playground-endpoint-select"
      />
    </Box>
  );
}
