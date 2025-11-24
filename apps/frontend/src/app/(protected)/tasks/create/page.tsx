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
  CircularProgress,
  Avatar,
  useTheme,
} from '@mui/material';
import { ArrowBackIcon } from '@/components/icons';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useTasks } from '@/hooks/useTasks';
import { TaskCreate, EntityType } from '@/types/tasks';
import {
  getStatuses,
  getPriorities,
  getStatusByName,
  getPriorityByName,
} from '@/utils/task-lookup';
import { getEntityDisplayName } from '@/utils/entity-helpers';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';

export default function CreateTaskPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  const { createTask } = useTasks({ autoFetch: false });
  const { show } = useNotifications();
  const theme = useTheme();

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
    task_metadata: undefined,
  });

  useEffect(() => {
    const loadInitialData = async () => {
      // Skip if already loaded
      if (statuses.length > 0 && priorities.length > 0 && users.length > 0) {
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        // Load statuses, priorities, and users in parallel
        const [fetchedStatuses, fetchedPriorities, fetchedUsers] =
          await Promise.all([
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
          const defaultStatus =
            fetchedStatuses.find(status => status.name === 'Open') ||
            fetchedStatuses[0];
          setFormData(prev => ({
            ...prev,
            status_id: defaultStatus.id,
          }));
        }

        // Set default priority if none is selected
        if (!formData.priority_id && fetchedPriorities.length > 0) {
          const defaultPriority =
            fetchedPriorities.find(
              priority => priority.type_value?.toLowerCase() === 'medium'
            ) || fetchedPriorities[0];
          setFormData(prev => ({
            ...prev,
            priority_id: defaultPriority.id,
          }));
        }
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load initial data';
        setError(errorMessage);
        show(errorMessage, { severity: 'error' });
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialData();
  }, [
    show,
    session?.session_token,
    formData.priority_id,
    formData.status_id,
    priorities.length,
    statuses.length,
    users.length,
  ]);

  // Pre-fill form with query parameters
  useEffect(() => {
    const entityType = searchParams.get('entityType') as EntityType;
    const entityId = searchParams.get('entityId');
    const commentId = searchParams.get('commentId');
    const testResultId = searchParams.get('test_result_id');

    if (entityType && entityId) {
      // Build metadata object from available params
      const metadata: Record<string, any> = {};
      if (commentId) metadata.comment_id = commentId;
      if (testResultId) metadata.test_result_id = testResultId;

      setFormData(prev => ({
        ...prev,
        entity_type: entityType,
        entity_id: entityId,
        task_metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
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

      if (!formData.priority_id) {
        show('Please select a priority', { severity: 'error' });
        return;
      }

      const taskData: TaskCreate = {
        title: formData.title,
        description: formData.description,
        status_id: formData.status_id,
        priority_id: formData.priority_id,
        assignee_id: formData.assignee_id || undefined,
        entity_type: formData.entity_type,
        entity_id: formData.entity_id,
        task_metadata: formData.task_metadata,
      };

      await createTask(taskData);
      router.push('/tasks');
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to create task';
      show(errorMessage, { severity: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleChange =
    (field: keyof TaskCreate) =>
    (event: React.ChangeEvent<HTMLInputElement> | any) => {
      setFormData(prev => ({
        ...prev,
        [field]: event.target.value,
      }));
    };

  if (isLoading) {
    return (
      <PageContainer
        title="Create Task"
        breadcrumbs={[
          { title: 'Tasks', path: '/tasks' },
          { title: 'Create Task', path: '/tasks/create' },
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

  return (
    <PageContainer
      title="Create Task"
      breadcrumbs={[
        { title: 'Tasks', path: '/tasks' },
        { title: 'Create Task', path: '/tasks/create' },
      ]}
    >
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        <Grid container spacing={3}>
          <Grid size={12}>
            <Paper sx={{ p: 3 }}>
              {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {error}
                </Alert>
              )}

              <form onSubmit={handleSubmit}>
                <Grid container spacing={3}>
                  <Grid size={12}>
                    <TextField
                      fullWidth
                      label="Task Title"
                      value={formData.title}
                      onChange={handleChange('title')}
                      required
                      disabled={isSaving}
                      placeholder={
                        formData.task_metadata?.comment_id
                          ? 'Enter task title related to the comment...'
                          : formData.entity_type
                            ? `Enter task title for ${getEntityDisplayName(formData.entity_type as EntityType)}...`
                            : 'Enter task title...'
                      }
                    />
                  </Grid>

                  <Grid
                    size={{
                      xs: 12,
                      sm: 6,
                    }}
                  >
                    <FormControl fullWidth disabled={isSaving}>
                      <InputLabel>Status</InputLabel>
                      <Select
                        value={formData.status_id}
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

                  <Grid
                    size={{
                      xs: 12,
                      sm: 6,
                    }}
                  >
                    <FormControl fullWidth disabled={isSaving}>
                      <InputLabel>Priority</InputLabel>
                      <Select
                        value={formData.priority_id}
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

                  <Grid size={12}>
                    <FormControl fullWidth disabled={isSaving}>
                      <InputLabel shrink>Assignee</InputLabel>
                      <Select
                        value={formData.assignee_id || ''}
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

                  <Grid size={12}>
                    <TextField
                      fullWidth
                      label="Description"
                      value={formData.description}
                      onChange={handleChange('description')}
                      multiline
                      rows={4}
                      disabled={isSaving}
                      placeholder={
                        formData.task_metadata?.comment_id
                          ? 'Describe the task related to this comment...'
                          : formData.entity_type
                            ? `Describe the task for ${getEntityDisplayName(formData.entity_type as EntityType)}...`
                            : 'Describe the task...'
                      }
                    />
                  </Grid>

                  <Grid size={12}>
                    <Box
                      sx={{
                        display: 'flex',
                        gap: 2,
                        justifyContent: 'flex-end',
                      }}
                    >
                      <Button
                        variant="outlined"
                        onClick={() => router.push('/tasks')}
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
          </Grid>
        </Grid>
      </Box>
    </PageContainer>
  );
}
