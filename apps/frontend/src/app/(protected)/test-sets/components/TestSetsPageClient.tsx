'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import Box from '@mui/material/Box';
import FileUploadIcon from '@mui/icons-material/FileUploadOutlined';
import SecurityIcon from '@mui/icons-material/SecurityOutlined';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import TestSetsGrid, { type TestSetsBulkActionsState } from './TestSetsGrid';
import TestSetDrawer from './TestSetDrawer';
import FileImportDrawer from './FileImportDrawer';
import SecurityTestDrawer from './SecurityTestDrawer';
import { testSetsList } from './list';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { useNotifications } from '@/components/common/NotificationContext';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useListAuthGate } from '@/hooks/useListAuthGate';
import type { TestSet } from '@/utils/api-client/interfaces/test-set';

interface TestSetsPageClientProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: TestSet[];
  initialTotalCount?: number;
}

export default function TestSetsPageClient({
  initialData,
  initialTotalCount = 0,
}: TestSetsPageClientProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const gate = useListAuthGate(testSetsList);
  const canCreate = useCan(Capability.TestSet.CREATE);
  const canGarak = useCan(Capability.Garak.CREATE);
  const canOwasp = useCan(Capability.Owasp.CREATE);

  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [fileImportDrawerOpen, setFileImportDrawerOpen] = React.useState(false);
  const [securityDrawerOpen, setSecurityDrawerOpen] = React.useState(false);
  const [bulkActions, setBulkActions] = React.useState<
    Pick<TestSetsBulkActionsState, 'visible'>
  >({ visible: false });
  const bulkHandlersRef = React.useRef<
    Pick<TestSetsBulkActionsState, 'onRun' | 'onDelete'>
  >({
    onRun: () => {},
    onDelete: () => {},
  });
  const [refreshTrigger, setRefreshTrigger] = React.useState(0);
  const bumpRefreshTrigger = React.useCallback(
    () => setRefreshTrigger(prev => prev + 1),
    []
  );

  const handleBulkActionsChange = React.useCallback(
    (actions: TestSetsBulkActionsState) => {
      setBulkActions({ visible: actions.visible });
      bulkHandlersRef.current = {
        onRun: actions.onRun,
        onDelete: actions.onDelete,
      };
    },
    []
  );

  useDocumentTitle('Test Sets');

  const handleCreateSuccess = React.useCallback(() => {
    setCreateDrawerOpen(false);
    bumpRefreshTrigger();
  }, [bumpRefreshTrigger]);

  const handleFileImportSuccess = React.useCallback(
    (_testSetId: string) => {
      bumpRefreshTrigger();
      notifications.show('Test set imported successfully from file', {
        severity: 'success',
      });
    },
    [bumpRefreshTrigger, notifications]
  );

  const handleGarakImportStarted = React.useCallback(() => {
    // Import/generation run as background tasks — this fires once they're
    // queued, not once they're done. Refresh now so the list picks up
    // completed test sets whenever the user next revisits it.
    bumpRefreshTrigger();
    notifications.show(
      'Garak import started — the test set(s) will appear in your list shortly',
      { severity: 'success', autoHideDuration: 6000 }
    );
  }, [bumpRefreshTrigger, notifications]);

  const handleOwaspGenerateSuccess = React.useCallback(() => {
    // Generation runs as a background task — this fires once it's queued,
    // not once it's done. Refresh now so the list picks up the completed
    // test set whenever the user next revisits it, mirroring Garak import.
    bumpRefreshTrigger();
    notifications.show('OWASP test set generation started', {
      severity: 'success',
    });
  }, [bumpRefreshTrigger, notifications]);

  if (!gate.ready) return gate.node;

  return (
    <>
      <PageLayout
        title="Test Sets"
        description="Curated collections of tests you can version, share, and execute against your AI endpoints."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            {bulkActions.visible && (
              <>
                <Fab
                  icon={<PlayArrowIcon />}
                  tooltip="Run Test Sets"
                  aria-label="Run Test Sets"
                  onClick={() => bulkHandlersRef.current.onRun()}
                />
                <Can capability={Capability.TestSet.DELETE}>
                  <Fab
                    icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
                    tooltip="Delete Test Sets"
                    aria-label="Delete Test Sets"
                    onClick={() => bulkHandlersRef.current.onDelete()}
                    sx={{
                      bgcolor: 'error.main',
                      '&:hover': { bgcolor: 'error.dark' },
                    }}
                  />
                </Can>
              </>
            )}
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
            onBulkActionsChange={handleBulkActionsChange}
            refreshTrigger={refreshTrigger}
            initialData={initialData}
            initialTotalCount={initialTotalCount}
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
