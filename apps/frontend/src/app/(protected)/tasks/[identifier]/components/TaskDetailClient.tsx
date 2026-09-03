'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { Typography, Button, Alert, CircularProgress } from '@mui/material';
import { format } from 'date-fns';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import { useTasks } from '@/hooks/useTasks';
import { Task, TaskUpdate } from '@/types/tasks';
import { getStatusesForTask, getPrioritiesForTask } from '@/utils/task-lookup';
import type { Status, Priority } from '@/utils/api-client/interfaces/task';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { isNotFoundApiError } from '@/utils/api-client/is-not-found-error';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import CreateJiraIssueButton from '../../components/CreateJiraIssueButton';
import TaskDetailTabs from './TaskDetailTabs';
import type { Comment } from '@/types/comments';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import DetailEntityMissingState from '@/components/common/DetailEntityMissingState';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface TaskDetailClientProps {
  identifier: string;
  initialTask: Task;
  initialComments?: Comment[];
}

export default function TaskDetailClient({
  identifier: taskId,
  initialTask,
  initialComments,
}: TaskDetailClientProps) {
  const router = useRouter();
  const { data: session, status } = useSession();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Task.READ
  );
  const { updateTask } = useTasks();
  const { show } = useNotifications();

  const [task, setTask] = useState<Task>(initialTask);
  const [error, setError] = useState<string | null>(null);
  const [missingError, setMissingError] = useState<unknown>(null);
  const [isRetrying, setIsRetrying] = useState(false);

  const [statuses, setStatuses] = useState<Status[]>([]);
  const [priorities, setPriorities] = useState<Priority[]>([]);
  const [users, setUsers] = useState<User[]>([]);

  // The task itself is server-rendered; only the dropdown lookups load here.
  useEffect(() => {
    if (!isAuthenticated(status)) return;
    let cancelled = false;
    Promise.all([
      getStatusesForTask(task.status_id),
      getPrioritiesForTask(task.priority_id),
    ]).then(([fetchedStatuses, fetchedPriorities]) => {
      if (cancelled) return;
      setStatuses(fetchedStatuses || []);
      setPriorities(fetchedPriorities || []);
    });
    return () => {
      cancelled = true;
    };
  }, [status, task.status_id, task.priority_id]);

  useEffect(() => {
    if (!isAuthenticated(status)) return;
    let cancelled = false;
    new ApiClientFactory()
      .getUsersClient()
      .getUsers()
      .then(response => {
        if (!cancelled) setUsers(response.data || []);
      })
      .catch(() => {
        // Assignee picker just stays empty; the task itself is unaffected.
      });
    return () => {
      cancelled = true;
    };
  }, [status]);

  // Keep the last loaded task visible while reloading so transient failures
  // still show cached data instead of flashing back to a loading state.
  const reloadTask = useCallback(async () => {
    setIsRetrying(true);
    setError(null);
    setMissingError(null);
    try {
      const taskData = await new ApiClientFactory()
        .getTasksClient()
        .getTask(taskId);
      setTask(taskData);
    } catch (err) {
      if (isNotFoundApiError(err)) {
        setMissingError(err);
        return;
      }
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load task data';
      setError(errorMessage);
      show(errorMessage, { severity: 'error' });
    } finally {
      setIsRetrying(false);
    }
  }, [taskId, show]);

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="tasks" />;

  if (missingError) {
    return (
      <DetailEntityMissingState
        error={missingError}
        entityLabel="Task"
        entityId={taskId}
        entityTableName="task"
        listUrl="/tasks"
        breadcrumbs={[
          { label: 'Tasks', href: '/tasks' },
          { label: 'Not Found', href: `/tasks/${taskId}` },
        ]}
        onBack={() => router.push('/tasks')}
        onRetry={reloadTask}
        isRetrying={isRetrying}
      />
    );
  }

  const metadataStrip = (
    <DetailMetadataStrip
      items={[
        { label: 'created by:', value: task.user?.name || '—' },
        {
          label: 'created on:',
          value: task.created_at
            ? format(new Date(task.created_at), 'dd/MM/yyyy')
            : '—',
        },
      ]}
    />
  );

  const handleUpdateTask = async (id: string, update: TaskUpdate) =>
    updateTask(id, update);

  return (
    <PageLayout
      title={task.title}
      breadcrumbs={[
        { label: 'Tasks', href: '/tasks' },
        { label: task.title, href: `/tasks/${taskId}` },
      ]}
      metadata={metadataStrip}
      actions={
        <CreateJiraIssueButton task={task} onIssueCreated={reloadTask} />
      }
    >
      {error && (
        <Alert
          severity="warning"
          sx={{ mb: 3 }}
          action={
            <Button
              color="inherit"
              size="small"
              onClick={reloadTask}
              disabled={isRetrying}
              variant="outlined"
            >
              {isRetrying ? (
                <>
                  <CircularProgress color="inherit" size={14} sx={{ mr: 1 }} />
                  Reconnecting...
                </>
              ) : (
                'Try to Reconnect'
              )}
            </Button>
          }
        >
          <Typography variant="body2">
            <strong>Connection Issue:</strong> We&apos;re having trouble
            connecting to the server, but we&apos;re showing you the last saved
            version of this task.
          </Typography>
        </Alert>
      )}

      <TaskDetailTabs
        task={task}
        statuses={statuses}
        priorities={priorities}
        users={users}
        currentUserId={session?.user?.id || ''}
        currentUserName={session?.user?.name || 'Unknown User'}
        currentUserPicture={session?.user?.picture || undefined}
        initialComments={initialComments}
        onTaskUpdated={setTask}
        updateTask={handleUpdateTask}
      />
    </PageLayout>
  );
}
