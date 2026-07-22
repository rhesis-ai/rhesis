'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useQueryClient } from '@tanstack/react-query';
import { testSetKeys } from '@/constants/query-keys';
import FileUploadIcon from '@mui/icons-material/FileUploadOutlined';
import SecurityIcon from '@mui/icons-material/SecurityOutlined';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import TestSetsGrid from './components/TestSetsGrid';
import TestSetDrawer from './components/TestSetDrawer';
import FileImportDrawer from './components/FileImportDrawer';
import GarakImportDrawer from './components/GarakImportDrawer';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { useNotifications } from '@/components/common/NotificationContext';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';

export default function TestSetsPage() {
  const { status } = useSession();
  const router = useRouter();
  const queryClient = useQueryClient();
  const notifications = useNotifications();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.TestSet.READ
  );
  const canCreate = useCan(Capability.TestSet.CREATE);
  const canGenerate = useCan(Capability.TestSet.GENERATE);
  const canGarak = useCan(Capability.Garak.CREATE);

  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [fileImportDrawerOpen, setFileImportDrawerOpen] = React.useState(false);
  const [garakImportDrawerOpen, setGarakImportDrawerOpen] =
    React.useState(false);

  useDocumentTitle('Test Sets');

  const handleCreateSuccess = React.useCallback(() => {
    setCreateDrawerOpen(false);
    queryClient.invalidateQueries({ queryKey: testSetKeys.all() });
  }, [queryClient]);

  const handleFileImportSuccess = React.useCallback(
    (_testSetId: string) => {
      queryClient.invalidateQueries({ queryKey: testSetKeys.all() });
      notifications.show('Test set imported successfully from file', {
        severity: 'success',
      });
    },
    [queryClient, notifications]
  );

  const handleGarakImportSuccess = React.useCallback(
    (testSetIds: string[]) => {
      queryClient.invalidateQueries({ queryKey: testSetKeys.all() });
      const count = testSetIds.length;
      notifications.show(
        `${count} Garak ${count === 1 ? 'probe' : 'probes'} imported successfully`,
        { severity: 'success', autoHideDuration: 6000 }
      );
      if (testSetIds.length === 1) {
        router.push(`/test-sets/${testSetIds[0]}`);
      }
    },
    [queryClient, notifications, router]
  );

  const handleOwaspGenerateSuccess = React.useCallback(() => {
    // Generation runs as a background task — the test set doesn't exist yet,
    // so the drawer stays open showing its own completion state. The user
    // closes it manually once they've read the "will appear in your list" note.
    notifications.show('OWASP test set generation started', {
      severity: 'success',
    });
  }, [notifications]);

  if (isSessionLoading(status)) {
    return (
      <PageLayout title="Test Sets" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="test sets" />;

  if (!isAuthenticated(status)) {
    return (
      <PageLayout title="Test Sets" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <>
      <PageLayout
        title="Test Sets"
        description="Curated collections of tests you can version, share, and execute against your AI endpoints."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            <Can capability={Capability.File.IMPORT}>
              <Fab
                icon={<FileUploadIcon />}
                tooltip="Import from File"
                onClick={() => setFileImportDrawerOpen(true)}
              />
            </Can>
            {(canGarak || canGenerate) && (
              <Fab
                icon={<SecurityIcon />}
                tooltip={
                  canGarak && canGenerate
                    ? 'Import from Garak or OWASP'
                    : canGenerate
                      ? 'Generate from OWASP'
                      : 'Import from Garak'
                }
                aria-label={
                  canGarak && canGenerate
                    ? 'Import from Garak or OWASP'
                    : canGenerate
                      ? 'Generate from OWASP'
                      : 'Import from Garak'
                }
                onClick={() => setGarakImportDrawerOpen(true)}
              />
            )}
            <Can capability={Capability.TestSet.GENERATE}>
              <Fab
                icon={<AutoFixHighIcon />}
                tooltip="AI generated Test Set"
                aria-label="AI generated Test Set"
                onClick={() => router.push('/test-sets/new-generated')}
              />
            </Can>
            <Can capability={Capability.TestSet.CREATE}>
              <Fab
                icon={<FabAddIcon />}
                tooltip="New Test Set"
                aria-label="New Test Set"
                onClick={() => setCreateDrawerOpen(true)}
              />
            </Can>
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          <TestSetsGrid
            canCreate={canCreate}
            onCreateClick={() => setCreateDrawerOpen(true)}
          />
        </Box>
      </PageLayout>

      <TestSetDrawer
        open={createDrawerOpen}
        onClose={() => setCreateDrawerOpen(false)}
        onSuccess={handleCreateSuccess}
      />

      <FileImportDrawer
        open={fileImportDrawerOpen}
        onClose={() => setFileImportDrawerOpen(false)}
        onSuccess={handleFileImportSuccess}
      />

      <GarakImportDrawer
        open={garakImportDrawerOpen}
        onClose={() => setGarakImportDrawerOpen(false)}
        onSuccess={handleGarakImportSuccess}
        onOwaspSuccess={handleOwaspGenerateSuccess}
        canUseGarak={canGarak}
        canUseOwasp={canGenerate}
      />
    </>
  );
}
