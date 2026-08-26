'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import { useSearchParams } from 'next/navigation';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useBulkActionsBridge } from '@/hooks/useBulkActionsBridge';
import { useListAuthGate } from '@/hooks/useListAuthGate';
import TasksGrid from './TasksGrid';
import TaskDrawer, { type TaskDrawerInitialEntity } from './TaskDrawer';
import { tasksList } from './list';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { EntityType } from '@/types/tasks';
import type { Task } from '@/utils/api-client/interfaces/task';

interface TasksPageClientProps {
  /** Server-fetched first page — when present, skips the initial client fetch. */
  initialData?: Task[];
  initialTotalCount?: number;
}

export default function TasksPageClient({
  initialData,
  initialTotalCount = 0,
}: TasksPageClientProps) {
  const gate = useListAuthGate(tasksList);
  const canCreateTask = useCan(Capability.Task.CREATE);
  const searchParams = useSearchParams();
  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [initialEntity, setInitialEntity] = React.useState<
    TaskDrawerInitialEntity | undefined
  >();
  const [refreshTrigger, setRefreshTrigger] = React.useState(0);
  const { bulkActionsVisible, onBulkDelete, handleBulkActionsChange } =
    useBulkActionsBridge();

  useDocumentTitle('Tasks');

  React.useEffect(() => {
    const shouldOpen = searchParams.get('create') === 'true';
    if (!shouldOpen) return;

    const entityType = searchParams.get('entityType') as EntityType | null;
    const entityId = searchParams.get('entityId');
    const commentId = searchParams.get('commentId');

    const task_metadata: Record<string, unknown> = {};
    if (commentId) task_metadata.comment_id = commentId;
    const testResultId = searchParams.get('test_result_id');
    const testRunId = searchParams.get('test_run_id');
    if (testResultId) task_metadata.test_result_id = testResultId;
    if (testRunId) task_metadata.test_run_id = testRunId;

    if (entityType && entityId) {
      setInitialEntity({
        entityType,
        entityId,
        task_metadata:
          Object.keys(task_metadata).length > 0 ? task_metadata : undefined,
      });
    } else {
      setInitialEntity(undefined);
    }

    setCreateDrawerOpen(true);

    const newUrl = new URL(window.location.href);
    newUrl.searchParams.delete('create');
    window.history.replaceState({}, '', newUrl.toString());
  }, [searchParams]);

  const handleCreateSuccess = React.useCallback(() => {
    setCreateDrawerOpen(false);
    setInitialEntity(undefined);
    setRefreshTrigger(prev => prev + 1);
  }, []);

  const handleCloseDrawer = React.useCallback(() => {
    setCreateDrawerOpen(false);
    setInitialEntity(undefined);
  }, []);

  if (!gate.ready) return gate.node;

  return (
    <>
      <PageLayout
        title="Tasks"
        description="Track and manage work items linked to tests, endpoints, and comments across your organization."
        breadcrumbs={[]}
        actions={
          <FabGroup>
            {bulkActionsVisible && (
              <Can capability={Capability.Task.DELETE}>
                <Fab
                  icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
                  tooltip="Delete Tasks"
                  aria-label="Delete Tasks"
                  onClick={onBulkDelete}
                  sx={{
                    bgcolor: 'error.main',
                    '&:hover': { bgcolor: 'error.dark' },
                  }}
                />
              </Can>
            )}
            <Can capability={Capability.Task.CREATE}>
              <Fab
                icon={<FabAddIcon />}
                tooltip="New Task"
                aria-label="New Task"
                onClick={() => {
                  setInitialEntity(undefined);
                  setCreateDrawerOpen(true);
                }}
              />
            </Can>
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          <TasksGrid
            canCreate={canCreateTask}
            onCreateClick={() => {
              setInitialEntity(undefined);
              setCreateDrawerOpen(true);
            }}
            onBulkActionsChange={handleBulkActionsChange}
            refreshTrigger={refreshTrigger}
            initialData={initialData}
            initialTotalCount={initialTotalCount}
          />
        </Box>
      </PageLayout>

      <TaskDrawer
        open={createDrawerOpen}
        onClose={handleCloseDrawer}
        initialEntity={initialEntity}
        onSuccess={handleCreateSuccess}
      />
    </>
  );
}
