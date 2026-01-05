'use client';

import React, { useState } from 'react';
import { Box, Typography, Alert, Paper } from '@mui/material';
import TimelineIcon from '@mui/icons-material/Timeline';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useNotifications } from '@/components/common/NotificationContext';
import TracesClient from './TracesClient';

/** Props for the EmptyStateMessage component */
interface EmptyStateMessageProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
}

/**
 * Reusable empty state component with customizable title, description and icon
 */
function EmptyStateMessage({
  title,
  description,
  icon,
}: EmptyStateMessageProps) {
  return (
    <Paper
      elevation={2}
      sx={{
        width: '100%',
        textAlign: 'center',
        p: 8,
        borderRadius: theme => theme.shape.borderRadius * 0.25,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
      }}
    >
      {icon || (
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
          <TimelineIcon
            sx={{
              fontSize: 60,
              color: 'primary.main',
              opacity: 0.7,
            }}
          />
        </Box>
      )}

      <Typography variant="h5" sx={{ color: 'text.primary', fontWeight: 500 }}>
        {title}
      </Typography>

      <Typography
        variant="body1"
        sx={{
          color: 'text.secondary',
          maxWidth: 550,
          mx: 'auto',
        }}
      >
        {description}
      </Typography>
    </Paper>
  );
}

/** Props for the TracesClientWrapper component */
interface TracesClientWrapperProps {
  sessionToken: string;
}

/**
 * Client component for the Traces page
 * Handles displaying traces and managing interactive features
 */
export default function TracesClientWrapper({
  sessionToken,
}: TracesClientWrapperProps) {
  const [refreshKey, setRefreshKey] = useState(0);
  const notifications = useNotifications();

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  // Show error state if no session token
  if (!sessionToken) {
    return (
      <PageContainer
        title="Traces"
        breadcrumbs={[{ title: 'Traces', path: '/traces' }]}
      >
        <Alert severity="error" sx={{ mb: 3 }}>
          Session expired. Please refresh the page or log in again.
        </Alert>
        <EmptyStateMessage
          title="Authentication Required"
          description="Please log in to view and analyze OpenTelemetry traces."
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Traces"
      breadcrumbs={[{ title: 'Traces', path: '/traces' }]}
    >
      <Box sx={{ mb: 3 }}>
        <Typography color="text.secondary">
          View and analyze OpenTelemetry traces from test executions and
          endpoint invocations.
        </Typography>
      </Box>
      {/* Traces content */}
      <Paper sx={{ width: '100%', mb: 2 }}>
        <Box sx={{ p: 2 }}>
          <TracesClient
            sessionToken={sessionToken}
            key={`traces-${refreshKey}`}
          />
        </Box>
      </Paper>
    </PageContainer>
  );
}
