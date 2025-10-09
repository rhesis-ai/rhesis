'use client';

import React, { useState } from 'react';
import { Box, Typography, Grid, Button, Alert, Paper } from '@mui/material';
import { Source } from '@/utils/api-client/interfaces/source';
import AddIcon from '@mui/icons-material/Add';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import UploadIcon from '@mui/icons-material/Upload';
import Link from 'next/link';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useNotifications } from '@/components/common/NotificationContext';

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
  const notifications = useNotifications();

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
            notifications.showNotification('Upload functionality coming soon!', 'info');
          }}
        >
          Upload Source
        </Button>
      </Box>

      {/* Sources content area */}
      <Box sx={{ mb: 4 }}>
        {Array.isArray(sources) && sources.length > 0 ? (
          <Grid container spacing={3}>
            {sources.map(source => (
              <Grid item key={source.id} xs={12} md={6} lg={4}>
                <Paper
                  elevation={1}
                  sx={{
                    p: 3,
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    '&:hover': {
                      elevation: 2,
                      cursor: 'pointer'
                    }
                  }}
                >
                  <Typography variant="h6" sx={{ mb: 1, fontWeight: 500 }}>
                    {source.title}
                  </Typography>

                  {source.description && (
                    <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
                      {source.description}
                    </Typography>
                  )}

                  <Box sx={{ mt: 'auto' }}>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      Uploaded: {new Date(source.created_at).toLocaleDateString()}
                    </Typography>

                    {source.tags && source.tags.length > 0 && (
                      <Box sx={{ mt: 1 }}>
                        {source.tags.slice(0, 3).map(tag => (
                          <Typography
                            key={tag}
                            variant="caption"
                            sx={{
                              mr: 1,
                              px: 1,
                              py: 0.5,
                              bgcolor: 'primary.light',
                              color: 'primary.contrastText',
                              borderRadius: 1,
                              fontSize: '0.7rem'
                            }}
                          >
                            {tag}
                          </Typography>
                        ))}
                        {source.tags.length > 3 && (
                          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                            +{source.tags.length - 3} more
                          </Typography>
                        )}
                      </Box>
                    )}
                  </Box>
                </Paper>
              </Grid>
            ))}
          </Grid>
        ) : (
          <EmptyStateMessage
            title="No knowledge sources found"
            description="Upload your first document, PDF, or text file to start building your knowledge base. Sources help improve your AI model's understanding and responses."
            icon={
              <Box sx={{ mb: 2 }}>
                <UploadIcon sx={{ fontSize: 64, color: 'primary.main', opacity: 0.7 }} />
              </Box>
            }
          />
        )}
      </Box>
    </PageContainer>
  );
}
