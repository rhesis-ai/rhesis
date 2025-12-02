'use client';

import React, { useState } from 'react';
import { Box, Typography, Alert, Paper } from '@mui/material';
import { Source } from '@/utils/api-client/interfaces/source';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useNotifications } from '@/components/common/NotificationContext';
import SourcesGrid from './SourcesGrid';
import styles from '@/styles/Knowledge.module.css';

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
    <Paper elevation={2} className={styles.emptyState}>
      {icon || (
        <Box className={styles.iconContainer}>
          <MenuBookIcon className={styles.primaryIcon} />
        </Box>
      )}

      <Typography variant="h5" className={styles.emptyStateTitle}>
        {title}
      </Typography>

      <Typography variant="body1" className={styles.emptyStateDescription}>
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
        <Alert severity="error" className={styles.marginBottom3}>
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
      <Box sx={{ mb: 3 }}>
        <Typography color="text.secondary">
          Upload knowledge sources to use as context for test generation and
          evaluation workflows.
        </Typography>
      </Box>
      {/* Sources grid */}
      <Paper className={styles.gridContainer}>
        <Box className={styles.gridContent}>
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
