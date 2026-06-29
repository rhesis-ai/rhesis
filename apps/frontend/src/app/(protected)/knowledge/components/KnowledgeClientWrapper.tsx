'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Box, Alert, Paper } from '@mui/material';
import UploadIcon from '@mui/icons-material/Upload';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { MenuBookIcon } from '@/components/icons';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import SourcesGrid from './SourcesGrid';
import UploadSourceDrawer from './UploadSourceDrawer';
import ToolImportDrawer from './ToolImportDrawer';

interface KnowledgeClientWrapperProps {
  sessionToken: string;
}

export default function KnowledgeClientWrapper({
  sessionToken,
}: KnowledgeClientWrapperProps) {
  const canRead = useCan(Capability.Source.READ);
  const canCreateSource = useCan(Capability.Source.CREATE);
  const [refreshKey, setRefreshKey] = useState(0);
  const [sourceCount, setSourceCount] = useState<number | null>(null);
  const [uploadDrawerOpen, setUploadDrawerOpen] = useState(false);
  const [toolImportDrawerOpen, setToolImportDrawerOpen] = useState(false);

  useDocumentTitle('Knowledge');

  const handleRefresh = useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  useEffect(() => {
    const fetchCount = async () => {
      if (!sessionToken) return;
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const sourcesClient = apiFactory.getSourcesClient();
        const response = await sourcesClient.getSources({
          skip: 0,
          limit: 1,
          sort_by: 'created_at',
          sort_order: 'desc',
        });
        const count = Array.isArray(response)
          ? response.length
          : (response?.pagination?.totalCount ?? 0);
        setSourceCount(count);
      } catch {
        setSourceCount(0);
      }
    };
    fetchCount();
  }, [sessionToken, refreshKey]);

  const handleUploadSuccess = useCallback(() => {
    setUploadDrawerOpen(false);
    handleRefresh();
  }, [handleRefresh]);

  const handleMcpImportSuccess = useCallback(() => {
    setToolImportDrawerOpen(false);
    handleRefresh();
  }, [handleRefresh]);

  if (!sessionToken) {
    return (
      <PageLayout
        title="Knowledge"
        description="Upload knowledge sources to use as context for test generation and evaluation workflows."
        breadcrumbs={[]}
      >
        <Alert severity="error" sx={{ mb: 3 }}>
          Session expired. Please refresh the page or log in again.
        </Alert>
        <EntityEmptyState
          icon={MenuBookIcon}
          title="Authentication Required"
          description="Please log in to view and manage your knowledge sources."
        />
      </PageLayout>
    );
  }

  if (!canRead) return <AccessDenied resource="knowledge sources" />;

  return (
    <>
      <PageLayout
        title="Knowledge"
        description="Upload knowledge sources to use as context for test generation and evaluation workflows."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            <Can capability={Capability.Source.CREATE}>
              <Fab
                icon={<UploadIcon />}
                tooltip="Upload Source"
                aria-label="Upload Source"
                onClick={() => setUploadDrawerOpen(true)}
              />
            </Can>
            <Can capability={Capability.Source.CREATE}>
              <Fab
                icon={<CloudDownloadIcon />}
                tooltip="Import from Tool"
                aria-label="Import from Tool"
                onClick={() => setToolImportDrawerOpen(true)}
              />
            </Can>
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          {sourceCount === 0 ? (
            <EntityEmptyState
              icon={MenuBookIcon}
              title="No knowledge sources yet"
              description="Upload files or import from tool connections to use as context for test generation and evaluation."
              actionLabel={canCreateSource ? 'Upload source' : undefined}
              onAction={canCreateSource ? () => setUploadDrawerOpen(true) : undefined}
            />
          ) : (
            <Paper
              sx={{
                width: '100%',
                borderRadius: BORDER_RADIUS.md,
                boxShadow: ELEVATION.xs,
                border: theme => `1px solid ${theme.palette.greyscale.border}`,
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              <SourcesGrid
                sessionToken={sessionToken}
                refreshKey={refreshKey}
                onRefresh={handleRefresh}
              />
            </Paper>
          )}
        </Box>
      </PageLayout>

      <UploadSourceDrawer
        open={uploadDrawerOpen}
        onClose={() => setUploadDrawerOpen(false)}
        onSuccess={handleUploadSuccess}
        sessionToken={sessionToken}
      />

      <ToolImportDrawer
        open={toolImportDrawerOpen}
        onClose={() => setToolImportDrawerOpen(false)}
        onSuccess={handleMcpImportSuccess}
        sessionToken={sessionToken}
      />
    </>
  );
}
