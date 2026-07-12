'use client';

import React, { useEffect, useState } from 'react';
import { Alert, Box, CircularProgress, Typography } from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import EndpointSelectField from '@/components/common/EndpointSelectField';
import type { EndpointOption } from '@/utils/endpoint-options';

interface PlaygroundEndpointDrawerProps {
  open: boolean;
  onClose: () => void;
  endpointOptions: EndpointOption[];
  selectedEndpointId: string | null;
  isLoading: boolean;
  error: string | null;
  onSelect: (endpointId: string | null) => void;
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
  const [pendingEndpointId, setPendingEndpointId] = useState<string | null>(
    selectedEndpointId
  );

  useEffect(() => {
    if (open) {
      setPendingEndpointId(selectedEndpointId);
    }
  }, [open, selectedEndpointId]);

  const handleSave = () => {
    onSelect(pendingEndpointId);
    onClose();
  };

  const canSelect =
    !isLoading && !error && endpointOptions.length > 0 && !!pendingEndpointId;

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Select Endpoint"
      onSave={handleSave}
      saveButtonText="Select"
      saveDisabled={!canSelect}
      loading={isLoading}
      closeButtonText="Cancel"
    >
      {isLoading ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
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
        <>
          <Typography variant="body2" color="text.secondary">
            Choose an endpoint to chat with interactively and generate test
            cases from your conversations.
          </Typography>
          <EndpointSelectField
            label="Select Endpoint"
            placeholder="Choose an endpoint"
            value={pendingEndpointId}
            onChange={setPendingEndpointId}
            options={endpointOptions}
            selectId="playground-endpoint-select"
          />
        </>
      )}
    </BaseDrawer>
  );
}
