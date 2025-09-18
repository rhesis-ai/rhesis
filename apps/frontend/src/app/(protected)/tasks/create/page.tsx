'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Box,
  Typography,
  Button,
  Paper,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Card,
  CardContent,
  Divider,
  Alert,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon, Save as SaveIcon } from '@mui/icons-material';
import { TaskStatus, TaskPriority, EntityType, TaskCreate } from '@/types/tasks';
import { useNotifications } from '@/components/common/NotificationContext';
import { useTasks } from '@/hooks/useTasks';
import { getStatuses, getPriorities, getStatusByName, getPriorityByName } from '@/utils/task-lookup';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/task';

export default function CreateTaskPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { show } = useNotifications();
  const { createTask } = useTasks({ autoFetch: false });
  
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    status: 'Open' as TaskStatus,
    priority: 'Medium' as TaskPriority,
    assignee_id: '',
  });
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statuses, setStatuses] = useState<any[]>([]);
  const [priorities, setPriorities] = useState<any[]>([]);
  const [users, setUsers] = useState<User[]>([]);

  // Load initial data
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Load statuses, priorities, and users in parallel
        const [fetchedStatuses, fetchedPriorities, fetchedUsers] = await Promise.all([
          getStatuses(session.session_token),
          getPriorities(session.session_token),
          (async () => {
            const clientFactory = new ApiClientFactory(session.session_token);
            const usersClient = clientFactory.getUsersClient();
            const response = await usersClient.getUsers();
            return response.data;
          })(),
        ]);

        setStatuses(fetchedStatuses);
        setPriorities(fetchedPriorities);
        setUsers(fetchedUsers);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load form data';
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
          : `This task is related to ${entityDisplayName} (ID: ${entityId})`
      }));
    }
  }, [searchParams]);

  const getEntityDisplayName = (entityType: EntityType): string => {
    switch (entityType) {
      case 'Test':
        return 'Test';
      case 'TestSet':
        return 'Test Set';
      case 'TestRun':
        return 'Test Run';
      case 'TestResult':
        return 'Test Result';
      case 'Task':
        return 'Task';
      default:
        return entityType;
    }
  };

  const getEntityPath = (entityType: EntityType): string => {
    switch (entityType) {
      case 'Test':
        return 'tests';
      case 'TestSet':
        return 'test-sets';
      case 'TestRun':
        return 'test-runs';
      case 'TestResult':
        return 'test-results';
      case 'Task':
        return 'tasks';
      default:
        return entityType.toLowerCase();
    }
  };

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    
    try {
      // Get status and priority IDs
      const statusObj = await getStatusByName(formData.status);
      const priorityObj = await getPriorityByName(formData.priority);
      
      if (!statusObj) {
        throw new Error(`Status "${formData.status}" not found`);
      }
      
      // Prepare task data
      const taskData: TaskCreate = {
        title: formData.title,
        description: formData.description,
        status_id: statusObj.id,
        priority_id: priorityObj?.id,
        assignee_id: formData.assignee_id || undefined,
        entity_type: searchParams.get('entityType') || undefined,
        entity_id: searchParams.get('entityId') || undefined,
        task_metadata: searchParams.get('commentId') ? { comment_id: searchParams.get('commentId') } : undefined,
      };
      
      const newTask = await createTask(taskData);
      
      if (newTask) {
        show('Task created successfully!', { severity: 'success' });
        
        // Navigate back to the entity page or tasks overview
        const entityType = searchParams.get('entityType');
        const entityId = searchParams.get('entityId');
        
        if (entityType && entityId) {
          // Navigate back to the specific entity page
          const entityPath = getEntityPath(entityType as EntityType);
          router.push(`/${entityPath}/${entityId}`);
        } else {
          // Navigate to tasks overview
          router.push('/tasks');
        }
      }
    } catch (error) {
      console.error('Failed to create task:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to create task. Please try again.';
      show(errorMessage, { severity: 'error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    const entityType = searchParams.get('entityType');
    const entityId = searchParams.get('entityId');
    
    if (entityType && entityId) {
      const entityPath = getEntityPath(entityType as EntityType);
      router.push(`/${entityPath}/${entityId}`);
    } else {
      router.push('/tasks');
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={handleCancel}
          variant="outlined"
        >
          Back
        </Button>
        <Typography variant="h4" fontWeight={600}>
          Create Task
        </Typography>
      </Box>

      {/* Entity Information Card */}
      {(searchParams.get('entityType') || searchParams.get('commentId')) && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Task Context
            </Typography>
            <Grid container spacing={2}>
              {searchParams.get('entityType') && (
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Entity Type
                  </Typography>
                  <Typography variant="body1" fontWeight={500}>
                    {getEntityDisplayName(searchParams.get('entityType') as EntityType)}
                  </Typography>
                </Grid>
              )}
              {searchParams.get('entityId') && (
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Entity ID
                  </Typography>
                  <Typography variant="body1" fontWeight={500}>
                    {searchParams.get('entityId')}
                  </Typography>
                </Grid>
              )}
              {searchParams.get('commentId') && (
                <Grid item xs={12}>
                  <Typography variant="body2" color="text.secondary">
                    Related Comment ID
                  </Typography>
                  <Typography variant="body1" fontWeight={500}>
                    {searchParams.get('commentId')}
                  </Typography>
                </Grid>
              )}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Task Form */}
      <Paper sx={{ p: 3 }}>
        <form onSubmit={handleSubmit}>
          <Grid container spacing={3}>
            {/* Title */}
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Task Title"
                value={formData.title}
                onChange={(e) => handleInputChange('title', e.target.value)}
                required
                placeholder="Enter a descriptive title for the task"
              />
            </Grid>

            {/* Description */}
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Description"
                value={formData.description}
                onChange={(e) => handleInputChange('description', e.target.value)}
                multiline
                rows={4}
                placeholder="Provide detailed description of the task"
              />
            </Grid>

            {/* Status and Priority */}
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select
                  value={formData.status}
                  onChange={(e) => handleInputChange('status', e.target.value)}
                  label="Status"
                  disabled={isLoading}
                >
                  {statuses.map((status) => (
                    <MenuItem key={status.id} value={status.name}>
                      {status.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Priority</InputLabel>
                <Select
                  value={formData.priority}
                  onChange={(e) => handleInputChange('priority', e.target.value)}
                  label="Priority"
                  disabled={isLoading}
                >
                  {priorities.map((priority) => (
                    <MenuItem key={priority.id} value={priority.name}>
                      {priority.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            {/* Assignee */}
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Assignee</InputLabel>
                <Select
                  value={formData.assignee_id}
                  onChange={(e) => handleInputChange('assignee_id', e.target.value)}
                  label="Assignee"
                  disabled={isLoading}
                >
                  <MenuItem value="">
                    <em>Unassigned</em>
                  </MenuItem>
                  {users.map((user) => (
                    <MenuItem key={user.id} value={user.id}>
                      {user.name || user.email}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          {/* Action Buttons */}
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
            <Button
              variant="outlined"
              onClick={handleCancel}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="contained"
              startIcon={<SaveIcon />}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Creating...' : 'Create Task'}
            </Button>
          </Box>
        </form>
      </Paper>
    </Box>
  );
}
