'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useBulkActionsBridge } from '@/hooks/useBulkActionsBridge';
import { useListAuthGate } from '@/hooks/useListAuthGate';
import TestRunsGrid from './TestRunsGrid';
import RunDrawer from '@/components/common/RunDrawer';
import { testRunsList } from './list';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

interface TestRunsPageClientProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: TestRunDetail[];
  initialTotalCount?: number;
}

export default function TestRunsPageClient({
  initialData,
  initialTotalCount = 0,
}: TestRunsPageClientProps) {
  const gate = useListAuthGate(testRunsList);
  const canCreateTestRun = useCan(Capability.TestRun.CREATE);
  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [refreshTrigger, setRefreshTrigger] = React.useState(0);
  const { bulkActionsVisible, onBulkDelete, handleBulkActionsChange } =
    useBulkActionsBridge();

  useDocumentTitle('Test Runs');

  const handleCreateSuccess = React.useCallback(() => {
    setCreateDrawerOpen(false);
    setRefreshTrigger(prev => prev + 1);
  }, []);

  if (!gate.ready) return gate.node;

  return (
    <>
      <PageLayout
        title="Test Runs"
        description="Executions of your test sets against AI endpoints. Track status, results, and history of each run."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            {bulkActionsVisible && (
              <Can capability={Capability.TestRun.DELETE}>
                <Fab
                  icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
                  tooltip="Delete Test Runs"
                  aria-label="Delete Test Runs"
                  onClick={onBulkDelete}
                  sx={{
                    bgcolor: 'error.main',
                    '&:hover': { bgcolor: 'error.dark' },
                  }}
                />
              </Can>
            )}
            <Can capability={Capability.TestRun.CREATE}>
              <Fab
                icon={<FabAddIcon />}
                tooltip="New Test Run"
                onClick={() => setCreateDrawerOpen(true)}
              />
            </Can>
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          <TestRunsGrid
            canCreate={canCreateTestRun}
            onCreateClick={() => setCreateDrawerOpen(true)}
            onBulkActionsChange={handleBulkActionsChange}
            refreshTrigger={refreshTrigger}
            initialData={initialData}
            initialTotalCount={initialTotalCount}
          />
        </Box>
      </PageLayout>

      <RunDrawer
        mode="newTestRun"
        open={createDrawerOpen}
        onClose={() => setCreateDrawerOpen(false)}
        onSuccess={handleCreateSuccess}
      />
    </>
  );
}
