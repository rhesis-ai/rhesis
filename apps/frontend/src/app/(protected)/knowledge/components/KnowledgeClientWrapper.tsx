'use client';

import React, { useState, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { Box, Alert } from '@mui/material';
import UploadIcon from '@mui/icons-material/Upload';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
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
import { useBulkActionsBridge } from '@/hooks/useBulkActionsBridge';
import SourcesGrid from './SourcesGrid';
import UploadSourceDrawer from './UploadSourceDrawer';
import ToolImportDrawer from './ToolImportDrawer';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import type { Source } from '@/utils/api-client/interfaces/source';

interface KnowledgeClientWrapperProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: Source[];
  initialTotalCount?: number;
}

export default function KnowledgeClientWrapper({
  initialData,
  initialTotalCount,
}: KnowledgeClientWrapperProps) {
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Source.READ
  );
  const canCreateSource = useCan(Capability.Source.CREATE);
  const { status } = useSession();
  const [uploadDrawerOpen, setUploadDrawerOpen] = useState(false);
  const [toolImportDrawerOpen, setToolImportDrawerOpen] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const { bulkActionsVisible, onBulkDelete, handleBulkActionsChange } =
    useBulkActionsBridge();

  useDocumentTitle('Knowledge');

  const handleUploadSuccess = useCallback(() => {
    setUploadDrawerOpen(false);
    setRefreshTrigger(prev => prev + 1);
  }, []);

  const handleMcpImportSuccess = useCallback(() => {
    setToolImportDrawerOpen(false);
    setRefreshTrigger(prev => prev + 1);
  }, []);

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
            {bulkActionsVisible && (
              <Can capability={Capability.Source.DELETE}>
                <Fab
                  icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
                  tooltip="Delete Sources"
                  aria-label="Delete Sources"
                  onClick={onBulkDelete}
                  sx={{
                    bgcolor: 'error.main',
                    '&:hover': { bgcolor: 'error.dark' },
                  }}
                />
              </Can>
            )}
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
          <SourcesGrid
            canCreate={canCreateSource}
            onCreateClick={() => setUploadDrawerOpen(true)}
            onBulkActionsChange={handleBulkActionsChange}
            initialData={initialData}
            initialTotalCount={initialTotalCount}
            refreshTrigger={refreshTrigger}
          />
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
