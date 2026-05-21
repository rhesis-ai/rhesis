'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Box, Alert, Paper } from '@mui/material';
import UploadIcon from '@mui/icons-material/Upload';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { MenuBookIcon } from '@/components/icons';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION, GREYSCALE } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import SourcesGrid from './SourcesGrid';
import UploadSourceDrawer from './UploadSourceDrawer';
import MCPImportDrawer from './MCPImportDrawer';

interface KnowledgeClientWrapperProps {
  sessionToken: string;
}

export default function KnowledgeClientWrapper({
  sessionToken,
}: KnowledgeClientWrapperProps) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [sourceCount, setSourceCount] = useState<number | null>(null);
  const [uploadDrawerOpen, setUploadDrawerOpen] = useState(false);
  const [mcpImportDrawerOpen, setMcpImportDrawerOpen] = useState(false);

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
    setMcpImportDrawerOpen(false);
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

  return (
    <>
      <PageLayout
        title="Knowledge"
        description="Upload knowledge sources to use as context for test generation and evaluation workflows."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            <Fab
              icon={<UploadIcon />}
              tooltip="Upload Source"
              aria-label="Upload Source"
              onClick={() => setUploadDrawerOpen(true)}
            />
            <Fab
              icon={<CloudDownloadIcon />}
              tooltip="Import from MCP"
              aria-label="Import from MCP"
              onClick={() => setMcpImportDrawerOpen(true)}
            />
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          {sourceCount === 0 ? (
            <EntityEmptyState
              icon={MenuBookIcon}
              title="No knowledge sources yet"
              description="Upload files or import from MCP tools to use as context for test generation and evaluation."
              actionLabel="Upload source"
              onAction={() => setUploadDrawerOpen(true)}
            />
          ) : (
            <Paper
              sx={{
                width: '100%',
                borderRadius: BORDER_RADIUS.md,
                boxShadow: ELEVATION.xs,
                border: theme =>
                  `1px solid ${theme.palette.mode === 'light' ? GREYSCALE.light.border : GREYSCALE.dark.border}`,
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

      <MCPImportDrawer
        open={mcpImportDrawerOpen}
        onClose={() => setMcpImportDrawerOpen(false)}
        onSuccess={handleMcpImportSuccess}
        sessionToken={sessionToken}
      />
    </>
  );
}
