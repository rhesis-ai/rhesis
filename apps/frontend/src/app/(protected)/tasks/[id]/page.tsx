'use client';

import { useState, useEffect, use } from 'react';
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
  Chip,
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

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function TaskDetailPage({ params }: PageProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const { getTask, updateTask } = useTasks({ autoFetch: false });
  const { show } = useNotifications();

  const theme = useTheme();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statuses, setStatuses] = useState<any[]>([]);
  const [priorities, setPriorities] = useState<any[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [editedTask, setEditedTask] = useState<Task | null>(null);
  const [isEditingDescription, setIsEditingDescription] = useState(false);
  const [editDescription, setEditDescription] = useState('');
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState('');

  const resolvedParams = use(params);
  const taskId = resolvedParams.id;

  // Initialize edit description and title when task loads
  useEffect(() => {
    if (editedTask) {
      setEditDescription(editedTask.description || '');
      setEditTitle(editedTask.title || '');
    }
  }, [editedTask]);

  useEffect(() => {
    const loadInitialData = async () => {
      // Skip if already loaded
      if (
        statuses.length > 0 &&
        priorities.length > 0 &&
        users.length > 0 &&
        editedTask
      ) {
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        // Load task data first to get existing status/priority IDs
        const taskData = taskId ? await getTask(taskId) : null;

        // Load statuses, priorities, and users in parallel, including existing task's status/priority
        const [fetchedStatuses, fetchedPriorities, fetchedUsers] =
          await Promise.all([
            getStatusesForTask(session?.session_token, taskData?.status_id),
            getPrioritiesForTask(session?.session_token, taskData?.priority_id),
            (async () => {
              if (!session?.session_token) return [];
              const clientFactory = new ApiClientFactory(session.session_token);
              const usersClient = clientFactory.getUsersClient();
              const response = await usersClient.getUsers();
              return response.data;
            })(),
          ]);

        setStatuses(fetchedStatuses);
        setPriorities(fetchedPriorities);
        setUsers(fetchedUsers);
        setEditedTask(taskData);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load task data';
        setError(errorMessage);
        show(errorMessage, { severity: 'error' });
      } finally {
        setIsLoading(false);
      }
    };

    if (taskId) {
      loadInitialData();
    }
  }, [
    taskId,
    getTask,
    show,
    session?.session_token,
    editedTask,
    priorities.length,
    statuses.length,
    users.length,
  ]);

  // Show loading state while taskId is being set
  if (isLoading) {
    return (
      <PageContainer
        title="Loading..."
        breadcrumbs={[
          { title: 'Tasks', path: '/tasks' },
          { title: 'Loading...', path: `/tasks/${taskId}` },
        ]}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '50vh',
          }}
        >
          <CircularProgress />
        </Box>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer
        title="Error"
        breadcrumbs={[
          { title: 'Tasks', path: '/tasks' },
          { title: 'Error', path: `/tasks/${taskId}` },
        ]}
      >
        <Box sx={{ flexGrow: 1, pt: 3 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
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
          <Alert severity="warning" sx={{ mb: 2 }}>
            Task not found
          </Alert>
        </Box>
      </PageContainer>
    );
  }

  const task = editedTask;

  const handleSaveDescription = async () => {
    if (!taskId) return;

    setIsSaving(true);

    try {
      const updateData: TaskUpdate = {
        title: task.title,
        description: editDescription,
        status_id: task.status_id,
        priority_id: task.priority_id,
        assignee_id: task.assignee_id || undefined,
      };

      await updateTask(taskId, updateData);
      show('Description updated successfully', { severity: 'success' });
      setIsEditingDescription(false);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to update description';
      show(errorMessage, { severity: 'error' });
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
        assignee_id: taskData.assignee_id || undefined,
      };

      await updateTask(taskId, updateData);
      show('Task updated successfully', { severity: 'success' });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to update task';
      show(errorMessage, { severity: 'error' });
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
    } catch (error) {
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
                  // Map entity types to correct URL paths (plural)
                  const entityUrlMap = getEntityUrlMap();
                  const entityPath =
                    entityUrlMap[task.entity_type] ||
                    task.entity_type.toLowerCase();
                  const baseUrl = `/${entityPath}/${task.entity_id}`;
                  const commentHash = task.task_metadata?.comment_id
                    ? `#comment-${task.task_metadata.comment_id}`
                    : '';
                  router.push(`${baseUrl}${commentHash}`);
                } catch (error) {
                  console.error('Navigation error:', error);
                }
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
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 4 }}>
              {/* Task Details Section */}

              {/* Status and Priority Row */}
              <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid item xs={6}>
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
                <Grid item xs={6}>
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
                <Grid item xs={6}>
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
                      renderValue={value => {
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
                <Grid item xs={6}>
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

              {/* Task Details Section */}
              <Box sx={{ mb: 4 }}>
                <Typography
                  variant="h6"
                  component="h2"
                  sx={{ fontWeight: 'bold', mb: 1 }}
                >
                  Task Details
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 3 }}
                >
                  Key information about this task.
                </Typography>
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
