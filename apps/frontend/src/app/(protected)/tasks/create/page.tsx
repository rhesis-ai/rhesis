'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter, useSearchParams } from 'next/navigation';
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
  CircularProgress
} from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { useTasks } from '@/hooks/useTasks';
import { TaskCreate, EntityType } from '@/types/tasks';
import { getStatuses, getPriorities, getStatusByName, getPriorityByName } from '@/utils/task-lookup';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';

function getEntityDisplayName(entityType: EntityType): string {
  switch (entityType) {
    case 'Test': return 'Test';
    case 'TestSet': return 'Test Set';
    case 'TestRun': return 'Test Run';
    case 'TestResult': return 'Test Result';
    default: return entityType;
  }
}

export default function CreateTaskPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  const { createTask } = useTasks({ autoFetch: false });
  const { show } = useNotifications();
  
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [statuses, setStatuses] = useState<any[]>([]);
  const [priorities, setPriorities] = useState<any[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  
  const [formData, setFormData] = useState<TaskCreate>({
    title: '',
    description: '',
    status_id: '',
    priority_id: '',
    assignee_id: '',
    entity_type: undefined,
    entity_id: undefined,
    task_metadata: undefined
  });

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Load statuses, priorities, and users in parallel
        const [fetchedStatuses, fetchedPriorities, fetchedUsers] = await Promise.all([
          getStatuses(session?.session_token),
          getPriorities(session?.session_token),
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

        // Set default status if none is selected
        if (!formData.status_id && fetchedStatuses.length > 0) {
          const defaultStatus = fetchedStatuses.find(status => status.name === 'Open') || fetchedStatuses[0];
          setFormData(prev => ({
            ...prev,
            status_id: defaultStatus.id
          }));
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load initial data';
        setError(errorMessage);
        show(errorMessage, { severity: 'error' });
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialData();
  }, [show, session]);

  // Pre-fill form with query parameters
  useEffect(() => {
    const entityType = searchParams.get('entityType') as EntityType;
    const entityId = searchParams.get('entityId');
    const commentId = searchParams.get('commentId');
    
    if (entityType && entityId) {
      const entityDisplayName = getEntityDisplayName(entityType);
      const baseTitle = commentId 
        ? `Task related to comment on ${entityDisplayName}`
        : `Task for ${entityDisplayName}`;
      
      setFormData(prev => ({
        ...prev,
        title: baseTitle,
        description: commentId 
          ? `This task is related to a comment on ${entityDisplayName} (ID: ${entityId})`
          : `This task is related to ${entityDisplayName} (ID: ${entityId})`,
        entity_type: entityType,
        entity_id: entityId,
        task_metadata: commentId ? { comment_id: commentId } : undefined
      }));
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.title.trim()) {
      show('Please enter a task title', { severity: 'error' });
      return;
    }

    setIsSaving(true);
    try {
      // Validate required fields
      if (!formData.status_id) {
        show('Please select a status', { severity: 'error' });
        return;
      }

      const taskData: TaskCreate = {
        title: formData.title,
        description: formData.description,
        status_id: formData.status_id,
        priority_id: formData.priority_id || undefined,
        assignee_id: formData.assignee_id || undefined,
        entity_type: formData.entity_type,
        entity_id: formData.entity_id,
        task_metadata: formData.task_metadata
      };

      await createTask(taskData);
      router.push('/tasks');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create task';
      show(errorMessage, { severity: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleChange = (field: keyof TaskCreate) => (
    event: React.ChangeEvent<HTMLInputElement> | any
  ) => {
    setFormData(prev => ({
      ...prev,
      [field]: event.target.value
    }));
  };

  if (isLoading) {
    return (
      <Box sx={{ p: 3, maxWidth: 800, mx: 'auto', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, maxWidth: 800, mx: 'auto' }}>
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Button
          startIcon={<ArrowBack />}
          onClick={() => router.back()}
          variant="outlined"
        >
          Back
        </Button>
        <Typography variant="h4" component="h1">
          Create New Task
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 3 }}>
        <form onSubmit={handleSubmit}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Task Title"
                value={formData.title}
                onChange={handleChange('title')}
                required
                disabled={isSaving}
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Description"
                value={formData.description}
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
                  value={formData.status_id}
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
                  value={formData.priority_id}
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
                  value={formData.assignee_id || ''}
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

            <Grid item xs={12}>
              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
                <Button
                  variant="outlined"
                  onClick={() => router.back()}
                  disabled={isSaving}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="contained"
                  disabled={isSaving}
                >
                  {isSaving ? 'Creating...' : 'Create Task'}
                </Button>
              </Box>
            </Grid>
          </Grid>
        </form>
      </Paper>
    </Box>
  );
}