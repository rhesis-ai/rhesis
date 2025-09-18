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
  Chip
} from '@mui/material';
import { ArrowBack, Save } from '@mui/icons-material';
import { useTasks } from '@/hooks/useTasks';
import { Task, TaskUpdate } from '@/types/tasks';
import { getStatuses, getPriorities, getStatusByName, getPriorityByName } from '@/utils/task-lookup';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';

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

  const resolvedParams = use(params);
  const taskId = resolvedParams.id;

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Load statuses, priorities, users, and task data in parallel
        const [fetchedStatuses, fetchedPriorities, fetchedUsers, taskData] = await Promise.all([
          getStatuses(session?.session_token),
          getPriorities(session?.session_token),
          (async () => {
            if (!session?.session_token) return [];
            const clientFactory = new ApiClientFactory(session.session_token);
            const usersClient = clientFactory.getUsersClient();
            const response = await usersClient.getUsers();
            return response.data;
          })(),
          taskId ? getTask(taskId) : null,
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
  }, [taskId, getTask, show, session]);

  // Show loading state while taskId is being set
  if (isLoading) {
    return (
      <Box sx={{ p: 3, maxWidth: 800, mx: 'auto', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3, maxWidth: 800, mx: 'auto' }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => router.push('/tasks')}
          variant="outlined"
        >
          Back to Tasks
        </Button>
      </Box>
    );
  }

  if (!editedTask) {
    return (
      <Box sx={{ p: 3, maxWidth: 800, mx: 'auto' }}>
        <Alert severity="warning" sx={{ mb: 2 }}>
          Task not found
        </Alert>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => router.push('/tasks')}
          variant="outlined"
        >
          Back to Tasks
        </Button>
      </Box>
    );
  }

  const task = editedTask;

  const handleSave = async () => {
    if (!taskId) return;

    setIsSaving(true);
    try {
      const updateData: TaskUpdate = {
        title: task.title,
        description: task.description,
        status_id: task.status_id,
        priority_id: task.priority_id,
        assignee_id: task.assignee_id || undefined
      };

      await updateTask(taskId, updateData);
      router.push('/tasks');
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
    setEditedTask(prev => prev ? {
      ...prev,
      [field]: event.target.value
    } : null);
  };

  return (
    <Box sx={{ p: 3, maxWidth: 800, mx: 'auto' }}>
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => router.push('/tasks')}
          variant="outlined"
        >
          Back to Tasks
        </Button>
        <Typography variant="h4" component="h1">
          Task Details
        </Typography>
      </Box>

      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
          {/* Task Info */}
          <Grid item xs={12}>
            <Box sx={{ mb: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip
                  label={task.status?.name || 'Unknown'}
                  color={task.status?.name === 'Completed' ? 'success' : task.status?.name === 'In Progress' ? 'primary' : 'default'}
                />
                <Chip
                  label={task.priority?.type_value || 'Unknown'}
                  color={task.priority?.type_value === 'High' ? 'error' : task.priority?.type_value === 'Medium' ? 'warning' : 'default'}
                />
            </Box>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Task Title"
              value={task.title}
              onChange={handleChange('title')}
              disabled={isSaving}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Description"
              value={task.description}
              onChange={handleChange('description')}
              multiline
              rows={4}
              disabled={isSaving}
            />
          </Grid>

          <Grid item xs={12} sm={6}>
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

          <Grid item xs={12} sm={6}>
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

          <Grid item xs={12}>
            <FormControl fullWidth disabled={isSaving}>
              <InputLabel>Assignee</InputLabel>
              <Select
                value={task.assignee_id || ''}
                onChange={handleChange('assignee_id')}
                label="Assignee"
              >
                <MenuItem value="">
                  <em>Unassigned</em>
                </MenuItem>
                {users.map((user) => (
                  <MenuItem key={user.id} value={user.id}>
                    {user.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Task Metadata */}
          <Grid item xs={12}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
              Task Information
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Typography variant="body2">
                <strong>Created by:</strong> {task.user?.name || 'Unknown'}
              </Typography>
              <Typography variant="body2">
                <strong>Task ID:</strong> {task.nano_id || task.id?.slice(0, 8) || 'N/A'}
              </Typography>
              {task.entity_type && task.entity_id && (
                <Typography variant="body2">
                  <strong>Related to:</strong> {task.entity_type} (ID: {task.entity_id})
                </Typography>
              )}
              {/* Comment Link - removed as comment_id is not in API */}
            </Box>
          </Grid>

          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
              <Button
                variant="outlined"
                onClick={() => router.push('/tasks')}
                disabled={isSaving}
              >
                Cancel
              </Button>
              <Button
                variant="contained"
                startIcon={<Save />}
                onClick={handleSave}
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : 'Save Changes'}
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
}