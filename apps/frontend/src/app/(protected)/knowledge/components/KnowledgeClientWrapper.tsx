'use client';

import React, { useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { sourceKeys } from '@/constants/query-keys';
import { Box, Alert, Paper } from '@mui/material';
import UploadIcon from '@mui/icons-material/Upload';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { MenuBookIcon } from '@/components/icons';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import SourcesGrid from './SourcesGrid';
import UploadSourceDrawer from './UploadSourceDrawer';
import ToolImportDrawer from './ToolImportDrawer';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

export default function KnowledgeClientWrapper() {
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Source.READ
  );
  const canCreateSource = useCan(Capability.Source.CREATE);
  const { status } = useSession();
  const queryClient = useQueryClient();
  const [sourceCount, setSourceCount] = useState<number | null>(null);
  const [uploadDrawerOpen, setUploadDrawerOpen] = useState(false);
  const [toolImportDrawerOpen, setToolImportDrawerOpen] = useState(false);

  useDocumentTitle('Knowledge');

  const handleUploadSuccess = useCallback(() => {
    setUploadDrawerOpen(false);
    queryClient.invalidateQueries({ queryKey: sourceKeys.all() });
  }, [queryClient]);

  const handleMcpImportSuccess = useCallback(() => {
    setToolImportDrawerOpen(false);
    queryClient.invalidateQueries({ queryKey: sourceKeys.all() });
  }, [queryClient]);

  if (!isAuthenticated(status)) {
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

  if (permsLoading) return <PageLoadingState />;
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
              card
              icon={MenuBookIcon}
              title="No knowledge sources yet"
              description="Upload files or import from tool connections to use as context for test generation and evaluation."
              actionLabel={canCreateSource ? 'Upload source' : undefined}
              onAction={
                canCreateSource ? () => setUploadDrawerOpen(true) : undefined
              }
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
              <SourcesGrid onTotalCountChange={setSourceCount} />
            </Paper>
          )}
        </Box>
      </PageLayout>

      <UploadSourceDrawer
        open={uploadDrawerOpen}
        onClose={() => setUploadDrawerOpen(false)}
        onSuccess={handleUploadSuccess}
      />

      <ToolImportDrawer
        open={toolImportDrawerOpen}
        onClose={() => setToolImportDrawerOpen(false)}
        onSuccess={handleMcpImportSuccess}
      />
    </>
  );
}
