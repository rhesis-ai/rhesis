'use client';

import React, { useState } from 'react';
import { Box, Typography, Button, Alert, Paper } from '@mui/material';
import { Source } from '@/utils/api-client/interfaces/source';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import UploadIcon from '@mui/icons-material/Upload';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useNotifications } from '@/components/common/NotificationContext';
import SourcesGrid from './SourcesGrid';

/** Type for alert/snackbar severity */
type AlertSeverity = 'success' | 'error' | 'info' | 'warning';

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
    <Paper elevation={2} sx={{ p: 4, textAlign: 'center', mt: 3 }}>
      {icon || (
        <Box sx={{ mb: 2 }}>
          <MenuBookIcon sx={{ fontSize: 64, color: 'primary.main', opacity: 0.7 }} />
        </Box>
      )}

      <Typography variant="h5" sx={{ mb: 2, fontWeight: 500 }}>
        {title}
      </Typography>

      <Typography variant="body1" sx={{ color: 'text.secondary', maxWidth: 400, mx: 'auto' }}>
        {description}
      </Typography>
    </Paper>
  );
}

/** Props for the KnowledgeClientWrapper component */
interface KnowledgeClientWrapperProps {
  initialSources: Source[];
  sessionToken: string;
}

/**
 * Client component for the Knowledge page
 * Handles displaying knowledge sources and managing interactive features
 */
export default function KnowledgeClientWrapper({
  initialSources = [],
  sessionToken,
}: KnowledgeClientWrapperProps) {
  const [sources, setSources] = useState<Source[]>(initialSources || []);
  const [refreshKey, setRefreshKey] = useState(0);
  const notifications = useNotifications();

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  // Show error state if no session token
  if (!sessionToken) {
    return (
      <PageContainer
        title="Knowledge"
        breadcrumbs={[{ title: 'Knowledge', path: '/knowledge' }]}
      >
        <Alert severity="error" sx={{ mb: 3 }}>
          Session expired. Please refresh the page or log in again.
        </Alert>
        <EmptyStateMessage
          title="Authentication Required"
          description="Please log in to view and manage your knowledge sources."
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Knowledge"
      breadcrumbs={[{ title: 'Knowledge', path: '/knowledge' }]}
    >
      {/* Header with actions */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 3,
        }}
      >
        <Typography variant="h6" sx={{ color: 'text.secondary' }}>
          Manage your knowledge sources and documents
        </Typography>

        <Button
          variant="contained"
          color="primary"
          startIcon={<UploadIcon />}
          // TODO: Add upload functionality
          onClick={() => {
            notifications.show('Upload functionality coming soon!', { severity: 'info' });
          }}
        >
          Upload Source
        </Button>
      </Box>

      {/* Sources grid */}
      <Paper sx={{ width: '100%', mb: 2, mt: 2 }}>
        <Box sx={{ p: 2 }}>
          <SourcesGrid
            sessionToken={sessionToken}
            onRefresh={handleRefresh}
            key={`sources-grid-${refreshKey}`}
          />
        </Box>
      </Paper>
    </PageContainer>
  );
}
