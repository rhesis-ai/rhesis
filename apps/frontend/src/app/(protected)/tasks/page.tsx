'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useSession } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { taskKeys } from '@/constants/query-keys';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import TasksGrid from './components/TasksGrid';
import TaskDrawer, {
  type TaskDrawerInitialEntity,
} from './components/TaskDrawer';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { EntityType } from '@/types/tasks';
import { isAuthenticated, isSessionLoading } from '@/hooks/useIsAuthenticated';

export default function TasksPage() {
  const { status } = useSession();
  const queryClient = useQueryClient();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Task.READ
  );
  const canCreateTask = useCan(Capability.Task.CREATE);
  const searchParams = useSearchParams();
  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [initialEntity, setInitialEntity] = React.useState<
    TaskDrawerInitialEntity | undefined
  >();

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
    queryClient.invalidateQueries({ queryKey: taskKeys.all() });
  }, [queryClient]);

  const handleCloseDrawer = React.useCallback(() => {
    setCreateDrawerOpen(false);
    setInitialEntity(undefined);
  }, []);

  if (isSessionLoading(status)) {
    return (
      <PageLayout title="Tasks" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="tasks" />;

  if (!isAuthenticated(status)) {
    return (
      <PageLayout title="Tasks" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <>
      <PageLayout
        title="Tasks"
        description="Track and manage work items linked to tests, endpoints, and comments across your organization."
        breadcrumbs={[]}
        actions={
          <FabGroup>
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
