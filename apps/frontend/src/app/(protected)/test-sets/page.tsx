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
import SecurityTestDrawer from './components/SecurityTestDrawer';
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
  const canGarak = useCan(Capability.Garak.CREATE);
  const canOwasp = useCan(Capability.Owasp.CREATE);

  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [fileImportDrawerOpen, setFileImportDrawerOpen] = React.useState(false);
  const [securityDrawerOpen, setSecurityDrawerOpen] = React.useState(false);

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

  const handleGarakImportStarted = React.useCallback(() => {
    // Import/generation run as background tasks — this fires once they're
    // queued, not once they're done. Invalidate now so the list picks up
    // completed test sets whenever the user next revisits it.
    queryClient.invalidateQueries({ queryKey: testSetKeys.all() });
    notifications.show(
      'Garak import started — the test set(s) will appear in your list shortly',
      { severity: 'success', autoHideDuration: 6000 }
    );
  }, [queryClient, notifications]);

  const handleOwaspGenerateSuccess = React.useCallback(() => {
    // Generation runs as a background task — this fires once it's queued,
    // not once it's done. Invalidate now so the list picks up the completed
    // test set whenever the user next revisits it, mirroring Garak import.
    queryClient.invalidateQueries({ queryKey: testSetKeys.all() });
    notifications.show('OWASP test set generation started', {
      severity: 'success',
    });
  }, [queryClient, notifications]);

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
            {(canGarak || canOwasp) && (
              <Fab
                icon={<SecurityIcon />}
                tooltip={
                  canGarak && canOwasp
                    ? 'Import from Garak or OWASP'
                    : canOwasp
                      ? 'Generate from OWASP'
                      : 'Import from Garak'
                }
                aria-label={
                  canGarak && canOwasp
                    ? 'Import from Garak or OWASP'
                    : canOwasp
                      ? 'Generate from OWASP'
                      : 'Import from Garak'
                }
                onClick={() => setSecurityDrawerOpen(true)}
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

      <SecurityTestDrawer
        open={securityDrawerOpen}
        onClose={() => setSecurityDrawerOpen(false)}
        onImportStarted={handleGarakImportStarted}
        onOwaspSuccess={handleOwaspGenerateSuccess}
        canUseGarak={canGarak}
        canUseOwasp={canOwasp}
      />
    </>
  );
}
