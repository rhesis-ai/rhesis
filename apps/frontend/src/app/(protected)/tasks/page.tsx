'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import AssignmentOutlinedIcon from '@mui/icons-material/AssignmentOutlined';
import { useSession } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import TasksGrid from './components/TasksGrid';
import TaskDrawer, {
  type TaskDrawerInitialEntity,
} from './components/TaskDrawer';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { EntityType } from '@/types/tasks';

export default function TasksPage() {
  const { data: session, status } = useSession();
  const canCreateTask = useCan(Capability.Task.CREATE);
  const searchParams = useSearchParams();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [taskCount, setTaskCount] = React.useState<number | null>(null);
  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [initialEntity, setInitialEntity] = React.useState<
    TaskDrawerInitialEntity | undefined
  >();

  useDocumentTitle('Tasks');

  const sessionToken = session?.session_token ?? '';

  React.useEffect(() => {
    const fetchCount = async () => {
      if (!sessionToken) return;
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const tasksClient = apiFactory.getTasksClient();
        const response = await tasksClient.getTasks({
          skip: 0,
          limit: 1,
          sort_by: 'created_at',
          sort_order: 'desc',
        });
        setTaskCount(response.totalCount ?? 0);
      } catch {
        setTaskCount(0);
      }
    };
    fetchCount();
  }, [sessionToken, refreshKey]);

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

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleCreateSuccess = React.useCallback(() => {
    setCreateDrawerOpen(false);
    setInitialEntity(undefined);
    handleRefresh();
  }, [handleRefresh]);

  const handleCloseDrawer = React.useCallback(() => {
    setCreateDrawerOpen(false);
    setInitialEntity(undefined);
  }, []);

  if (status === 'loading') {
    return (
      <PageLayout title="Tasks" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (!sessionToken) {
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
          {taskCount === 0 ? (
            <EntityEmptyState
              icon={AssignmentOutlinedIcon}
              title="No tasks yet"
              description="Create tasks to track follow-ups, issues, and action items from tests and evaluations."
              actionLabel={canCreateTask ? 'Create task' : undefined}
              onAction={
                canCreateTask
                  ? () => {
                      setInitialEntity(undefined);
                      setCreateDrawerOpen(true);
                    }
                  : undefined
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
              }}
            >
              <TasksGrid
                sessionToken={sessionToken}
                refreshKey={refreshKey}
                onRefresh={handleRefresh}
              />
            </Paper>
          )}
        </Box>
      </PageLayout>

      <TaskDrawer
        open={createDrawerOpen}
        onClose={handleCloseDrawer}
        sessionToken={sessionToken}
        initialEntity={initialEntity}
        onSuccess={handleCreateSuccess}
      />
    </>
  );
}
