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
  IconButton
} from '@mui/material';
import { Save, ArrowForward, Edit, Cancel } from '@mui/icons-material';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useTasks } from '@/hooks/useTasks';
import { Task, TaskUpdate } from '@/types/tasks';
import { getStatusesForTask, getPrioritiesForTask, getStatusByName, getPriorityByName } from '@/utils/task-lookup';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import CommentsWrapper from '@/components/comments/CommentsWrapper';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function TaskDetailPage({ params }: PageProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const { getTask, updateTask } = useTasks({ autoFetch: false });
  const { show } = useNotifications();
  
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [statuses, setStatuses] = useState<any[]>([]);
  const [priorities, setPriorities] = useState<any[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [editedTask, setEditedTask] = useState<Task | null>(null);
  const [isEditingDescription, setIsEditingDescription] = useState(false);

  const resolvedParams = use(params);
  const taskId = resolvedParams.id;

  useEffect(() => {
    const loadInitialData = async () => {
      // Skip if already loaded and session token hasn't changed
      if (statuses.length > 0 && priorities.length > 0 && users.length > 0 && editedTask) {
        return;
      }
      
      try {
        setIsLoading(true);
        setError(null);

        // Load task data first to get existing status/priority IDs
        const taskData = taskId ? await getTask(taskId) : null;
        
        // Load statuses, priorities, and users in parallel, including existing task's status/priority
        const [fetchedStatuses, fetchedPriorities, fetchedUsers] = await Promise.all([
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
        const errorMessage = err instanceof Error ? err.message : 'Failed to load task data';
        setError(errorMessage);
        show(errorMessage, { severity: 'error' });
      } finally {
        setIsLoading(false);
      }
    };

    if (taskId) {
      loadInitialData();
    }
  }, [taskId, getTask, show, session?.session_token, statuses.length, priorities.length, users.length, editedTask]);

  // Show loading state while taskId is being set
  if (isLoading) {
    return (
      <PageContainer title="Loading..." breadcrumbs={[{ title: 'Tasks', path: '/tasks' }, { title: 'Loading...', path: `/tasks/${taskId}` }]}>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
          <CircularProgress />
        </Box>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer title="Error" breadcrumbs={[{ title: 'Tasks', path: '/tasks' }, { title: 'Error', path: `/tasks/${taskId}` }]}>
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
      <PageContainer title="Task Not Found" breadcrumbs={[{ title: 'Tasks', path: '/tasks' }, { title: 'Not Found', path: `/tasks/${taskId}` }]}>
        <Box sx={{ flexGrow: 1, pt: 3 }}>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Task not found
          </Alert>
        </Box>
      </PageContainer>
    );
  }

  const task = editedTask;

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
        assignee_id: taskData.assignee_id || undefined
      };

      await updateTask(taskId, updateData);
      show('Task updated successfully', { severity: 'success' });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update task';
      show(errorMessage, { severity: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleChange = (field: keyof Task) => (
    event: React.ChangeEvent<HTMLInputElement> | any
  ) => {
    if (!editedTask) return;
    
    const value = event.target.value;
    const updatedTask = { ...editedTask, [field]: value };
    setEditedTask(updatedTask);
    
    // Auto-save for non-description fields
    if (field !== 'description') {
      handleSave(updatedTask);
    }
  };

  return (
    <PageContainer title={task.title} breadcrumbs={[{ title: 'Tasks', path: '/tasks' }, { title: task.title, path: `/tasks/${taskId}` }]}>
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 4 }}>
              {/* Header with title and action button */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold', color: 'text.primary' }}>
                  {task.title}
                </Typography>
                {(task.task_metadata?.comment_id || (task.entity_type && task.entity_id)) && (
                  <Button
                    variant="outlined"
                    endIcon={<ArrowForward />}
                    sx={{ 
                      color: 'text.secondary',
                      borderColor: 'grey.300',
                      '&:hover': {
                        borderColor: 'grey.400',
                        backgroundColor: 'grey.50'
                      }
                    }}
                    onClick={() => {
                      // Navigate to the associated comment or entity
                      if (task.task_metadata?.comment_id && task.entity_type && task.entity_id) {
                        // If there's a comment, go to the comment
                        router.push(`/${task.entity_type.toLowerCase()}/${task.entity_id}#comment-${task.task_metadata.comment_id}`);
                      } else if (task.entity_type && task.entity_id) {
                        // If there's no comment but there's an entity, go to the entity
                        router.push(`/${task.entity_type.toLowerCase()}/${task.entity_id}`);
                      }
                    }}
                  >
                    {task.task_metadata?.comment_id ? 'Go to associated comment' : `Go to ${task.entity_type}`}
                  </Button>
                )}
              </Box>

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
                      {statuses.map((status) => (
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
                      {priorities.map((priority) => (
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
                  <Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      Creator
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main' }}>
                        {task.user?.name?.charAt(0) || 'U'}
                      </Avatar>
                      <Typography variant="body1">
                        {task.user?.name || 'Unknown'}
                      </Typography>
                    </Box>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      Assignee
                    </Typography>
                    <FormControl fullWidth disabled={isSaving}>
                      <Select
                        value={task.assignee_id || ''}
                        onChange={handleChange('assignee_id')}
                        displayEmpty
                        sx={{
                          '& .MuiSelect-select': {
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1
                          }
                        }}
                        renderValue={(value) => {
                          const selectedUser = users.find(user => user.id === value);
                          return (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Avatar sx={{ width: 24, height: 24, bgcolor: 'secondary.main' }}>
                                {selectedUser?.name?.charAt(0) || 'U'}
                              </Avatar>
                              <Typography variant="body1">
                                {selectedUser?.name || 'Unassigned'}
                              </Typography>
                            </Box>
                          );
                        }}
                      >
                        <MenuItem value="">
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Avatar sx={{ width: 24, height: 24, bgcolor: 'grey.300' }}>
                              U
                            </Avatar>
                            <Typography variant="body1">Unassigned</Typography>
                          </Box>
                        </MenuItem>
                        {users.map((user) => (
                          <MenuItem key={user.id} value={user.id}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Avatar sx={{ width: 24, height: 24, bgcolor: 'secondary.main' }}>
                                {user.name?.charAt(0) || 'U'}
                              </Avatar>
                              <Typography variant="body1">{user.name}</Typography>
                            </Box>
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Box>
                </Grid>
              </Grid>

              {/* Task Details Section */}
              <Box sx={{ mb: 4 }}>
                <Typography variant="h6" component="h2" sx={{ fontWeight: 'bold', mb: 1 }}>
                  Task Details
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Key information about this task.
                </Typography>
              </Box>

              {/* Description */}
              <Box sx={{ mb: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    Description
                  </Typography>
                  {!isEditingDescription ? (
                    <IconButton
                      onClick={() => setIsEditingDescription(true)}
                      size="small"
                      sx={{ 
                        color: 'text.secondary',
                        '&:hover': {
                          color: 'primary.main',
                        }
                      }}
                    >
                      <Edit fontSize="small" />
                    </IconButton>
                  ) : (
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <IconButton
                        onClick={() => setIsEditingDescription(false)}
                        size="small"
                        sx={{ 
                          color: 'text.secondary',
                          '&:hover': {
                            color: 'primary.main',
                          }
                        }}
                      >
                        <Cancel fontSize="small" />
                      </IconButton>
                      <IconButton
                        onClick={() => {
                          setIsEditingDescription(false);
                          handleSave();
                        }}
                        size="small"
                        sx={{ 
                          color: 'primary.main',
                          '&:hover': {
                            color: 'primary.dark',
                          }
                        }}
                      >
                        <Save fontSize="small" />
                      </IconButton>
                    </Box>
                  )}
                </Box>
                {isEditingDescription ? (
                  <TextField
                    fullWidth
                    value={task.description || ''}
                    onChange={handleChange('description')}
                    multiline
                    rows={6}
                    disabled={isSaving}
                    variant="outlined"
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        backgroundColor: 'background.paper',
                      }
                    }}
                  />
                ) : (
                  <Box
                    sx={{
                      p: 2,
                      border: '1px solid',
                      borderColor: 'grey.300',
                      borderRadius: 1,
                      backgroundColor: 'background.paper',
                      minHeight: 120,
                      cursor: 'pointer'
                    }}
                    onClick={() => setIsEditingDescription(true)}
                  >
                    <Typography variant="body1" color="text.primary">
                      {task.description || 'No description provided. Click to add one.'}
                    </Typography>
                  </Box>
                )}
              </Box>

            </Paper>
          </Grid>
          
          {/* Comments Section */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <CommentsWrapper
                entityType="Task"
                entityId={taskId}
                sessionToken={session?.session_token || ''}
                currentUserId={session?.user?.id || ''}
                currentUserName={session?.user?.name || 'Unknown User'}
                currentUserPicture={session?.user?.picture}
                onCreateTask={undefined} // No task creation from task comments
              />
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </PageContainer>
  );
}