'use client';

import { useState, useEffect, useCallback, useRef, use } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Typography,
  Button,
  Alert,
  CircularProgress,
} from '@mui/material';
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
import CreateJiraIssueButton from '../components/CreateJiraIssueButton';
import TaskDetailTabs from './components/TaskDetailTabs';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import DetailEntityMissingState from '@/components/common/DetailEntityMissingState';
import DetailNotFoundState from '@/components/common/DetailNotFoundState';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

function TaskDetailLoadingState({
  taskId,
  loadingTimeout,
  onBack,
  onRetry,
}: {
  taskId: string;
  loadingTimeout: boolean;
  onBack: () => void;
  onRetry: () => void;
}) {
  return (
    <PageLayout
      title={loadingTimeout ? 'Taking longer than expected...' : 'Loading...'}
      breadcrumbs={[
        { label: 'Tasks', href: '/tasks' },
        {
          label: loadingTimeout ? 'Slow Connection' : 'Loading...',
          href: `/tasks/${taskId}`,
        },
      ]}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '50vh',
          gap: 3,
        }}
      >
        <CircularProgress />

        {loadingTimeout && (
          <Box sx={{ textAlign: 'center', maxWidth: 400 }}>
            <Alert severity="warning" sx={{ mb: 2 }}>
              <Typography variant="h6" sx={{ mb: 1 }}>
                This is taking longer than usual
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                The server might be experiencing high load or there could be a
                network issue. We&apos;re still trying to load your task.
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Task ID: {taskId}
              </Typography>
            </Alert>

            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              <Button variant="contained" onClick={onBack}>
                Back to Tasks
              </Button>
              <Button variant="outlined" onClick={onRetry}>
                Try Again
              </Button>
            </Box>
          </Box>
        )}
      </Box>
    </PageLayout>
  );
}

function TaskDetailErrorState({
  taskId,
  error,
  isRetrying,
  onBack,
  onRetry,
}: {
  taskId: string;
  error: string;
  isRetrying: boolean;
  onBack: () => void;
  onRetry: () => void;
}) {
  return (
    <PageLayout
      title="Error"
      breadcrumbs={[
        { label: 'Tasks', href: '/tasks' },
        { label: 'Error', href: `/tasks/${taskId}` },
      ]}
    >
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        <Alert
          severity="error"
          sx={{ mb: 3 }}
          action={
            <Button
              color="inherit"
              size="small"
              onClick={onRetry}
              disabled={isRetrying}
            >
              {isRetrying ? (
                <>
                  <CircularProgress color="inherit" size={16} sx={{ mr: 1 }} />
                  Retrying...
                </>
              ) : (
                'Retry'
              )}
            </Button>
          }
        >
          <Typography variant="h6" sx={{ mb: 1 }}>
            Sorry, we couldn&apos;t load this task
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            We encountered an issue while trying to load the task details. This
            might be due to a temporary network issue or server problem.
          </Typography>
          <Box
            sx={{
              fontSize: theme => theme.typography.helperText.fontSize,
              fontFamily: 'monospace',
              color: 'text.secondary',
              mt: 1,
            }}
          >
            Error: {error}
          </Box>
        </Alert>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button variant="contained" onClick={onBack}>
            Back to Tasks
          </Button>
          <Button variant="outlined" onClick={onRetry} disabled={isRetrying}>
            {isRetrying ? (
              <>
                <CircularProgress color="inherit" size={16} sx={{ mr: 1 }} />
                Retrying...
              </>
            ) : (
              'Try Again'
            )}
          </Button>
        </Box>
      </Box>
    </PageLayout>
  );
}

export default function TaskDetailPage({ params }: PageProps) {
  const router = useRouter();
  const { data: session, status } = useSession();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Task.READ
  );
  const { updateTask } = useTasks();
  const { show } = useNotifications();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [missingError, setMissingError] = useState<unknown>(null);
  const [hasInitialLoad, setHasInitialLoad] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [loadingTimeout, setLoadingTimeout] = useState(false);

  const isLoadingRef = useRef(false);
  const hasInitialLoadRef = useRef(false);

  const [statuses, setStatuses] = useState<Status[]>([]);
  const [priorities, setPriorities] = useState<Priority[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [task, setTask] = useState<Task | null>(null);

  const resolvedParams = use(params);
  const taskId = resolvedParams.identifier;

  useEffect(() => {
    isLoadingRef.current = isLoading;
  }, [isLoading]);

  useEffect(() => {
    hasInitialLoadRef.current = hasInitialLoad;
  }, [hasInitialLoad]);

  const loadInitialData = useCallback(
    async (isRetry = false) => {
      if (!isRetry && (isLoadingRef.current || hasInitialLoadRef.current)) {
        return;
      }

      try {
        if (isRetry) {
          setIsRetrying(true);
        } else {
          setIsLoading(true);
        }
        setError(null);
        setMissingError(null);

        if (!taskId) {
          throw new Error('No task ID provided');
        }

        if (!isAuthenticated(status)) {
          throw new Error('No session token available');
        }

        const sessionToken = session?.session_token;
        const clientFactory = new ApiClientFactory(sessionToken);
        const tasksClient = clientFactory.getTasksClient();
        const taskData = await tasksClient.getTask(taskId);

        const [fetchedStatuses, fetchedPriorities, fetchedUsers] =
          await Promise.all([
            getStatusesForTask(sessionToken, taskData.status_id),
            getPrioritiesForTask(sessionToken, taskData.priority_id),
            (async () => {
              const clientFactory = new ApiClientFactory(sessionToken);
              const usersClient = clientFactory.getUsersClient();
              const response = await usersClient.getUsers();
              return response.data || [];
            })(),
          ]);

        setStatuses(fetchedStatuses || []);
        setPriorities(fetchedPriorities || []);
        setUsers(fetchedUsers);
        setTask(taskData);
        setHasInitialLoad(true);
      } catch (err) {
        if (isNotFoundApiError(err)) {
          setMissingError(err);
          setHasInitialLoad(true);
          return;
        }

        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load task data';
        setError(errorMessage);

        if (!hasInitialLoad || isRetry) {
          show(errorMessage, { severity: 'error' });
        }

        setHasInitialLoad(true);
      } finally {
        setIsLoading(false);
        setIsRetrying(false);
      }
    },
    [taskId, session?.session_token, show, hasInitialLoad, status]
  );

  useEffect(() => {
    if (taskId && isAuthenticated(status)) {
      loadInitialData();
    }
  }, [taskId, session?.session_token, loadInitialData, status]);

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    if (isLoading || (!hasInitialLoad && taskId && isAuthenticated(status))) {
      timeoutId = setTimeout(() => {
        setLoadingTimeout(true);
      }, 10000);
    } else {
      setLoadingTimeout(false);
    }

    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [isLoading, hasInitialLoad, taskId, session?.session_token, status]);

  // Keep the last loaded task visible while retrying so transient failures
  // still show cached data instead of flashing back to the loading state.
  const handleRetry = () => {
    setLoadingTimeout(false);
    setHasInitialLoad(false);
    setMissingError(null);
    loadInitialData(true);
  };

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="tasks" />;

  if (isLoading || (!hasInitialLoad && taskId && isAuthenticated(status))) {
    return (
      <TaskDetailLoadingState
        taskId={taskId}
        loadingTimeout={loadingTimeout}
        onBack={() => router.push('/tasks')}
        onRetry={handleRetry}
      />
    );
  }

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
        onRetry={handleRetry}
        isRetrying={isRetrying}
      />
    );
  }

  if (!task && hasInitialLoad && !error) {
    return (
      <DetailNotFoundState
        entityLabel="Task"
        entityId={taskId}
        entityTableName="task"
        listUrl="/tasks"
        breadcrumbs={[
          { label: 'Tasks', href: '/tasks' },
          { label: 'Not Found', href: `/tasks/${taskId}` },
        ]}
        onBack={() => router.push('/tasks')}
        onRetry={handleRetry}
        isRetrying={isRetrying}
      />
    );
  }

  if (error && !task) {
    return (
      <TaskDetailErrorState
        taskId={taskId}
        error={error}
        isRetrying={isRetrying}
        onBack={() => router.push('/tasks')}
        onRetry={handleRetry}
      />
    );
  }

  if (!task) {
    return null;
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

  const handleTaskUpdated = (updatedTask: Task) => {
    setTask(updatedTask);
  };

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
        <CreateJiraIssueButton
          task={task}
          onIssueCreated={() => loadInitialData(true)}
        />
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
              onClick={handleRetry}
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
        sessionToken={session?.session_token || ''}
        currentUserId={session?.user?.id || ''}
        currentUserName={session?.user?.name || 'Unknown User'}
        currentUserPicture={session?.user?.picture || undefined}
        onTaskUpdated={handleTaskUpdated}
        updateTask={handleUpdateTask}
      />
    </PageLayout>
  );
}
