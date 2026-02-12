'use client';

import { useState, useEffect, useCallback, useRef, use } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Alert,
  CircularProgress,
  Avatar,
  useTheme,
  IconButton,
  Divider,
  Tooltip,
} from '@mui/material';
import { ArrowOutwardIcon, EditIcon } from '@/components/icons';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useTasks } from '@/hooks/useTasks';
import { Task, TaskUpdate } from '@/types/tasks';
import { getStatusesForTask, getPrioritiesForTask } from '@/utils/task-lookup';
import { getEntityUrlMap } from '@/utils/entity-helpers';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import CommentsWrapper from '@/components/comments/CommentsWrapper';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import CreateJiraIssueButton from '../components/CreateJiraIssueButton';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default function TaskDetailPage({ params }: PageProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const { getTask, updateTask } = useTasks({ autoFetch: false });
  const { show } = useNotifications();

  const theme = useTheme();
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasInitialLoad, setHasInitialLoad] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [loadingTimeout, setLoadingTimeout] = useState(false);

  // Use refs to track state without causing dependency cycles
  const isLoadingRef = useRef(false);
  const hasInitialLoadRef = useRef(false);

  // Update refs when state changes
  useEffect(() => {
    isLoadingRef.current = isLoading;
  }, [isLoading]);

  useEffect(() => {
    hasInitialLoadRef.current = hasInitialLoad;
  }, [hasInitialLoad]);

  const [statuses, setStatuses] = useState<any[]>([]);
  const [priorities, setPriorities] = useState<any[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [editedTask, setEditedTask] = useState<Task | null>(null);
  const [isEditingDescription, setIsEditingDescription] = useState(false);
  const [editDescription, setEditDescription] = useState('');
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState('');

  const resolvedParams = use(params);
  const taskId = resolvedParams.identifier;

  // Initialize edit description and title when task loads
  useEffect(() => {
    if (editedTask) {
      setEditDescription(editedTask.description || '');
      setEditTitle(editedTask.title || '');
    }
  }, [editedTask]);

  // Create a stable reference for the load function
  const loadInitialData = useCallback(
    async (isRetry = false) => {
      // Prevent multiple concurrent requests using refs to avoid dependency cycles
      if (!isRetry && (isLoadingRef.current || hasInitialLoadRef.current))
        return;

      try {
        if (isRetry) {
          setIsRetrying(true);
        } else {
          setIsLoading(true);
        }
        setError(null);

        if (!taskId) {
          throw new Error('No task ID provided');
        }

        if (!session?.session_token) {
          throw new Error('No session token available');
        }

        // Load task data first to get existing status/priority IDs
        const taskData = await getTask(taskId);

        if (!taskData) {
          throw new Error('Task not found');
        }

        // Load statuses, priorities, and users in parallel, including existing task's status/priority
        const [fetchedStatuses, fetchedPriorities, fetchedUsers] =
          await Promise.all([
            getStatusesForTask(session.session_token, taskData.status_id),
            getPrioritiesForTask(session.session_token, taskData.priority_id),
            (async () => {
              if (!session?.session_token) return [];
              const clientFactory = new ApiClientFactory(session.session_token);
              const usersClient = clientFactory.getUsersClient();
              const response = await usersClient.getUsers();
              return response.data || [];
            })(),
          ]);

        setStatuses(fetchedStatuses || []);
        setPriorities(fetchedPriorities || []);
        setUsers(fetchedUsers);
        setEditedTask(taskData);
        setHasInitialLoad(true);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load task data';
        setError(errorMessage);

        // Only show notification on initial load or retry
        if (!hasInitialLoad || isRetry) {
          show(errorMessage, { severity: 'error' });
        }

        // Set hasInitialLoad to true even on error to prevent infinite retries
        setHasInitialLoad(true);
      } finally {
        setIsLoading(false);
        setIsRetrying(false);
      }
    },
    [taskId, getTask, session?.session_token, show, hasInitialLoad]
  );

  // Initial load effect - only depends on essential values
  useEffect(() => {
    if (taskId && session?.session_token) {
      loadInitialData();
    }
  }, [taskId, session?.session_token, loadInitialData]);

  // Timeout effect - show timeout message if loading takes too long
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    if (isLoading || (!hasInitialLoad && taskId && session?.session_token)) {
      // Set timeout for 10 seconds
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
  }, [isLoading, hasInitialLoad, taskId, session?.session_token]);

  // Show loading state while loading or if we haven't loaded yet
  if (isLoading || (!hasInitialLoad && taskId && session?.session_token)) {
    return (
      <PageContainer
        title={loadingTimeout ? 'Taking longer than expected...' : 'Loading...'}
        breadcrumbs={[
          { title: 'Tasks', path: '/tasks' },
          {
            title: loadingTimeout ? 'Slow Connection' : 'Loading...',
            path: `/tasks/${taskId}`,
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
                <Button
                  variant="contained"
                  onClick={() => router.push('/tasks')}
                >
                  Back to Tasks
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => {
                    setLoadingTimeout(false);
                    setHasInitialLoad(false);
                    loadInitialData(true);
                  }}
                >
                  Try Again
                </Button>
              </Box>
            </Box>
          )}
        </Box>
      </PageContainer>
    );
  }

  if (error && !editedTask) {
    return (
      <PageContainer
        title="Error"
        breadcrumbs={[
          { title: 'Tasks', path: '/tasks' },
          { title: 'Error', path: `/tasks/${taskId}` },
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
                onClick={() => loadInitialData(true)}
                disabled={isRetrying}
              >
                {isRetrying ? (
                  <>
                    <CircularProgress
                      color="inherit"
                      size={16}
                      sx={{ mr: 1 }}
                    />
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
              We encountered an issue while trying to load the task details.
              This might be due to a temporary network issue or server problem.
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
            <Button variant="contained" onClick={() => router.push('/tasks')}>
              Back to Tasks
            </Button>
            <Button
              variant="outlined"
              onClick={() => loadInitialData(true)}
              disabled={isRetrying}
            >
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
      </PageContainer>
    );
  }

  if (!editedTask) {
    return (
      <PageContainer
        title="Task Not Found"
        breadcrumbs={[
          { title: 'Tasks', path: '/tasks' },
          { title: 'Not Found', path: `/tasks/${taskId}` },
        ]}
      >
        <Box sx={{ flexGrow: 1, pt: 3 }}>
          <Alert severity="warning" sx={{ mb: 3 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Sorry, we couldn&apos;t load this task
            </Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              The task you&apos;re looking for might have been deleted, moved,
              or you may not have permission to view it.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Task ID: {taskId}
            </Typography>
          </Alert>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button variant="contained" onClick={() => router.push('/tasks')}>
              Back to Tasks
            </Button>
            <Button
              variant="outlined"
              onClick={() => loadInitialData(true)}
              disabled={isRetrying}
            >
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
      </PageContainer>
    );
  }

  const task = editedTask;

  const handleSaveDescription = async () => {
    if (!taskId || !editedTask) return;

    setIsSaving(true);
    const originalDescription = editedTask.description;

    try {
      const updateData: TaskUpdate = {
        title: editedTask.title,
        description: editDescription,
        status_id: editedTask.status_id,
        priority_id: editedTask.priority_id,
        assignee_id: editedTask.assignee_id || null,
      };

      const updatedTask = await updateTask(taskId, updateData);

      // Update local state with the response from server
      if (updatedTask) {
        setEditedTask(updatedTask);
      }

      show('Description updated successfully', { severity: 'success' });
      setIsEditingDescription(false);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to update description';
      show(errorMessage, { severity: 'error' });

      // Revert description on error
      setEditDescription(originalDescription || '');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSave = async (taskToSave?: Task) => {
    if (!taskId) return;

    const taskData = taskToSave || task;
    setIsSaving(true);

    try {
      const updateData: TaskUpdate = {
        title: taskData.title,
        description: taskData.description,
        status_id: taskData.status_id,
        priority_id: taskData.priority_id,
        assignee_id: taskData.assignee_id || null,
      };

      const updatedTask = await updateTask(taskId, updateData);

      // Update local state with the response from server
      if (updatedTask) {
        setEditedTask(updatedTask);
      }

      show('Task updated successfully', { severity: 'success' });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to update task';
      show(errorMessage, { severity: 'error' });

      // Revert local changes on error if we have original data
      if (editedTask && taskToSave) {
        setEditedTask(editedTask);
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleChange =
    (field: keyof Task) =>
    (event: React.ChangeEvent<HTMLInputElement> | any) => {
      if (!editedTask) return;

      const value = event.target.value;
      const updatedTask = { ...editedTask, [field]: value };
      setEditedTask(updatedTask);

      // Auto-save for non-description fields
      if (field !== 'description') {
        handleSave(updatedTask);
      }
    };

  const handleSaveTitle = async () => {
    if (!editTitle.trim()) {
      show('Task title cannot be empty', { severity: 'error' });
      return;
    }

    if (!editedTask) return;

    setIsSaving(true);
    const updatedTask = { ...editedTask, title: editTitle.trim() };
    setEditedTask(updatedTask);
    setIsEditingTitle(false);

    try {
      await handleSave(updatedTask);
    } catch (_error) {
      // Revert on error
      setEditTitle(editedTask.title || '');
      setIsEditingTitle(true);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <PageContainer
      breadcrumbs={[
        { title: 'Tasks', path: '/tasks' },
        { title: editedTask?.title || task.title, path: `/tasks/${taskId}` },
      ]}
    >
      {/* Title and Navigation Button in same row */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 500 }}>
          {editedTask?.title || task.title}
        </Typography>
        {task.entity_type && task.entity_id && (
          <Button
            variant="outlined"
            size="small"
            onClick={() => {
              // Always navigate to the entity, optionally with comment hash
              if (task.entity_type && task.entity_id) {
                try {
                  // Special handling for TestResult entities - navigate to test run page
                  if (
                    task.entity_type === 'TestResult' &&
                    task.task_metadata?.test_run_id
                  ) {
                    const queryParams = new URLSearchParams();
                    queryParams.append('selectedresult', task.entity_id);
                    const queryString = queryParams.toString();
                    const commentHash = task.task_metadata?.comment_id
                      ? `#comment-${task.task_metadata.comment_id}`
                      : '';
                    const finalUrl = `/test-runs/${task.task_metadata.test_run_id}?${queryString}${commentHash}`;
                    router.push(finalUrl);
                    return;
                  }

                  // Map entity types to correct URL paths (plural)
                  const entityUrlMap = getEntityUrlMap();
                  const entityPath =
                    entityUrlMap[task.entity_type] ||
                    task.entity_type.toLowerCase();
                  const baseUrl = `/${entityPath}/${task.entity_id}`;

                  // Add query parameters if available (e.g., selectedresult for test runs)
                  const queryParams = new URLSearchParams();
                  if (task.task_metadata?.test_result_id) {
                    queryParams.append(
                      'selectedresult',
                      String(task.task_metadata.test_result_id)
                    );
                  }
                  const queryString = queryParams.toString()
                    ? `?${queryParams.toString()}`
                    : '';

                  // Add hash for comments if available
                  const commentHash = task.task_metadata?.comment_id
                    ? `#comment-${task.task_metadata.comment_id}`
                    : '';

                  const finalUrl = `${baseUrl}${queryString}${commentHash}`;
                  router.push(finalUrl);
                } catch (_error) {}
              }
            }}
            sx={{
              borderRadius: theme.shape.borderRadius,
              backgroundColor: 'background.paper',
              color: 'text.secondary',
              border: '1px solid',
              borderColor: 'divider',
              px: 2,
              py: 1,
              '&:hover': {
                backgroundColor: 'action.hover',
                color: 'text.primary',
                borderColor: 'primary.main',
              },
            }}
            endIcon={
              <Box
                sx={{
                  width: 20,
                  height: 20,
                  borderRadius: theme.shape.circular,
                  backgroundColor: 'text.secondary',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <ArrowOutwardIcon
                  sx={{ fontSize: '12px', color: 'background.paper' }}
                />
              </Box>
            }
          >
            {task.task_metadata?.comment_id
              ? 'Go to associated comment'
              : `Go to ${task.entity_type}`}
          </Button>
        )}
      </Box>
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        {/* Show warning if there's an error but we have cached data */}
        {error && editedTask && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2" sx={{ mb: 1 }}>
              <strong>Connection Issue:</strong> We&apos;re having trouble
              connecting to the server, but we&apos;re showing you the last
              saved version of this task.
            </Typography>
            <Box
              sx={{
                fontSize: theme => theme.typography.helperText.fontSize,
                fontFamily: 'monospace',
                color: 'text.secondary',
                mb: 1,
              }}
            >
              {error}
            </Box>
            <Button
              color="inherit"
              size="small"
              onClick={() => loadInitialData(true)}
              disabled={isRetrying}
              variant="outlined"
              sx={{ mt: 1 }}
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
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid size={12}>
            <Paper sx={{ p: 4 }}>
              {/* Task Details Section Header */}
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  mb: 4,
                }}
              >
                <Box>
                  <Typography
                    variant="h6"
                    component="h2"
                    sx={{ fontWeight: 'bold', mb: 1 }}
                  >
                    Task Details
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Key information about this task.
                  </Typography>
                </Box>
                <CreateJiraIssueButton
                  task={editedTask || task}
                  onIssueCreated={() => loadInitialData(true)}
                />
              </Box>

              {/* Title */}
              <Box sx={{ mb: 4 }}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 1,
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    Title
                  </Typography>
                  {!isEditingTitle ? (
                    <Tooltip title="Edit title">
                      <IconButton
                        onClick={() => setIsEditingTitle(true)}
                        size="small"
                        sx={{
                          color: 'text.secondary',
                          '&:hover': {
                            color: 'primary.main',
                          },
                        }}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  ) : null}
                </Box>
                {isEditingTitle ? (
                  <Box sx={{ mb: 2 }}>
                    <TextField
                      value={editTitle}
                      onChange={e => setEditTitle(e.target.value)}
                      fullWidth
                      variant="outlined"
                      size="small"
                      placeholder="Enter task title..."
                      error={!editTitle.trim()}
                      helperText={
                        !editTitle.trim() ? 'Title cannot be empty' : ''
                      }
                      sx={{ mb: 1 }}
                    />
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'flex-end',
                        gap: 1,
                      }}
                    >
                      <Button
                        size="small"
                        onClick={() => {
                          setIsEditingTitle(false);
                          setEditTitle(task.title || '');
                        }}
                        disabled={isSaving}
                        sx={{ textTransform: 'none', borderRadius: '16px' }}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="small"
                        variant="contained"
                        onClick={handleSaveTitle}
                        disabled={isSaving || !editTitle.trim()}
                        sx={{ textTransform: 'none', borderRadius: '16px' }}
                      >
                        {isSaving ? 'Saving...' : 'Save'}
                      </Button>
                    </Box>
                  </Box>
                ) : (
                  <Typography
                    variant="body1"
                    sx={{
                      minHeight: '24px',
                      color:
                        editedTask?.title || task.title
                          ? 'text.primary'
                          : 'text.secondary',
                      fontStyle:
                        editedTask?.title || task.title ? 'normal' : 'italic',
                    }}
                  >
                    {editedTask?.title || task.title || 'No title set'}
                  </Typography>
                )}
              </Box>

              {/* Description */}
              <Box sx={{ mb: 4 }}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 1,
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    Description
                  </Typography>
                  {!isEditingDescription ? (
                    <Tooltip title="Edit description">
                      <IconButton
                        onClick={() => setIsEditingDescription(true)}
                        size="small"
                        sx={{
                          color: 'text.secondary',
                          '&:hover': {
                            color: 'primary.main',
                          },
                        }}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  ) : null}
                </Box>
                {isEditingDescription ? (
                  <Box sx={{ mb: 2 }}>
                    <TextField
                      value={editDescription}
                      onChange={e => setEditDescription(e.target.value)}
                      multiline
                      rows={3}
                      fullWidth
                      variant="outlined"
                      size="small"
                      sx={{ mb: 1 }}
                    />
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'flex-end',
                        gap: 1,
                      }}
                    >
                      <Button
                        size="small"
                        onClick={() => {
                          setIsEditingDescription(false);
                          setEditDescription(task.description || '');
                        }}
                        sx={{ textTransform: 'none', borderRadius: '16px' }}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="small"
                        variant="contained"
                        onClick={handleSaveDescription}
                        disabled={isSaving || !editDescription.trim()}
                        sx={{ textTransform: 'none', borderRadius: '16px' }}
                      >
                        {isSaving ? 'Saving...' : 'Save'}
                      </Button>
                    </Box>
                  </Box>
                ) : (
                  <Typography
                    variant="body2"
                    sx={{
                      mb: 2,
                      lineHeight: 1.6,
                      whiteSpace: 'pre-wrap',
                      color: 'text.primary',
                    }}
                  >
                    {task.description || 'No description provided'}
                  </Typography>
                )}
              </Box>

              {/* Status and Priority Row */}
              <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid size={6}>
                  <FormControl fullWidth disabled={isSaving}>
                    <InputLabel>Status</InputLabel>
                    <Select
                      value={task.status_id || ''}
                      onChange={handleChange('status_id')}
                      label="Status"
                    >
                      {statuses.map(status => (
                        <MenuItem key={status.id} value={status.id}>
                          {status.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid size={6}>
                  <FormControl fullWidth disabled={isSaving}>
                    <InputLabel>Priority</InputLabel>
                    <Select
                      value={task.priority_id || ''}
                      onChange={handleChange('priority_id')}
                      label="Priority"
                    >
                      {priorities.map(priority => (
                        <MenuItem key={priority.id} value={priority.id}>
                          {priority.type_value}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>

              {/* Creator and Assignee Row */}
              <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid size={6}>
                  <FormControl fullWidth disabled>
                    <InputLabel>Creator</InputLabel>
                    <Select
                      value={task.user?.id || ''}
                      label="Creator"
                      displayEmpty
                      sx={{
                        '& .MuiSelect-select': {
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                        },
                      }}
                      renderValue={_value => {
                        return (
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                            }}
                          >
                            <Avatar
                              src={task.user?.picture}
                              alt={task.user?.name || 'Unknown'}
                              sx={{
                                width: AVATAR_SIZES.SMALL,
                                height: AVATAR_SIZES.SMALL,
                                bgcolor: 'primary.main',
                              }}
                            >
                              {task.user?.name?.charAt(0) || 'U'}
                            </Avatar>
                            <Typography variant="body1">
                              {task.user?.name || 'Unknown'}
                            </Typography>
                          </Box>
                        );
                      }}
                    >
                      <MenuItem value={task.user?.id || ''}>
                        <Box
                          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                        >
                          <Avatar
                            src={task.user?.picture}
                            alt={task.user?.name || 'Unknown'}
                            sx={{
                              width: AVATAR_SIZES.SMALL,
                              height: AVATAR_SIZES.SMALL,
                              bgcolor: 'primary.main',
                            }}
                          >
                            {task.user?.name?.charAt(0) || 'U'}
                          </Avatar>
                          <Typography variant="body1">
                            {task.user?.name || 'Unknown'}
                          </Typography>
                        </Box>
                      </MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid size={6}>
                  <FormControl fullWidth disabled={isSaving}>
                    <InputLabel shrink>Assignee</InputLabel>
                    <Select
                      value={task.assignee_id || ''}
                      onChange={handleChange('assignee_id')}
                      label="Assignee"
                      displayEmpty
                      sx={{
                        '& .MuiSelect-select': {
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          paddingTop: theme.spacing(2),
                          paddingBottom: theme.spacing(2),
                        },
                      }}
                      renderValue={value => {
                        const selectedUser = users.find(
                          user => user.id === value
                        );
                        if (!selectedUser) {
                          // Handle "Unassigned" case
                          return (
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                              }}
                            >
                              <Avatar
                                sx={{
                                  width: AVATAR_SIZES.SMALL,
                                  height: AVATAR_SIZES.SMALL,
                                  bgcolor: 'grey.300',
                                }}
                              >
                                U
                              </Avatar>
                              <Typography variant="body1">
                                Unassigned
                              </Typography>
                            </Box>
                          );
                        }
                        return (
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                            }}
                          >
                            <Avatar
                              src={selectedUser.picture}
                              alt={selectedUser.name || 'User'}
                              sx={{
                                width: AVATAR_SIZES.SMALL,
                                height: AVATAR_SIZES.SMALL,
                                bgcolor: 'primary.main',
                              }}
                            >
                              {selectedUser.name?.charAt(0) || 'U'}
                            </Avatar>
                            <Typography variant="body1">
                              {selectedUser.name}
                            </Typography>
                          </Box>
                        );
                      }}
                    >
                      <MenuItem value="">
                        <Box
                          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                        >
                          <Avatar
                            sx={{
                              width: AVATAR_SIZES.SMALL,
                              height: AVATAR_SIZES.SMALL,
                              bgcolor: 'grey.300',
                            }}
                          >
                            U
                          </Avatar>
                          <Typography variant="body1">Unassigned</Typography>
                        </Box>
                      </MenuItem>
                      {users
                        .filter(user => user.id && user.name)
                        .map(user => (
                          <MenuItem key={user.id} value={user.id}>
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                              }}
                            >
                              <Avatar
                                src={user.picture}
                                alt={user.name || 'User'}
                                sx={{
                                  width: AVATAR_SIZES.SMALL,
                                  height: AVATAR_SIZES.SMALL,
                                  bgcolor: 'primary.main',
                                }}
                              >
                                {user.name?.charAt(0) || 'U'}
                              </Avatar>
                              <Typography variant="body1">
                                {user.name}
                              </Typography>
                            </Box>
                          </MenuItem>
                        ))}
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>

              {/* Divider between task details and comments */}
              <Divider sx={{ my: 4 }} />

              {/* Comments Section */}
              <Box>
                <CommentsWrapper
                  entityType="Task"
                  entityId={taskId}
                  sessionToken={session?.session_token || ''}
                  currentUserId={session?.user?.id || ''}
                  currentUserName={session?.user?.name || 'Unknown User'}
                  currentUserPicture={session?.user?.picture || undefined}
                  onCreateTask={undefined} // No task creation from task comments
                />
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </PageContainer>
  );
}
