'use client';

import React from 'react';
import {
  TextField,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
} from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { drawerOutlinedFieldSx } from '@/components/common/drawerFormFieldSx';
import { EntityType } from '@/types/tasks';
import type {
  TaskCreate,
  Status,
  Priority,
} from '@/utils/api-client/interfaces/task';
import { getStatuses, getPriorities } from '@/utils/task-lookup';
import { getEntityDisplayName } from '@/utils/entity-helpers';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { useTasks } from '@/hooks/useTasks';
import { useNotifications } from '@/components/common/NotificationContext';

export interface TaskDrawerInitialEntity {
  entityType?: EntityType;
  entityId?: string;
  task_metadata?: Record<string, unknown>;
}

interface TaskDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  initialEntity?: TaskDrawerInitialEntity;
  onSuccess?: () => void;
}

export default function TaskDrawer({
  open,
  onClose,
  sessionToken,
  initialEntity,
  onSuccess,
}: TaskDrawerProps) {
  const { show } = useNotifications();
  const { createTask } = useTasks();

  const [loading, setLoading] = React.useState(false);
  const [loadError, setLoadError] = React.useState<string>();
  const [title, setTitle] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [statusId, setStatusId] = React.useState('');
  const [priorityId, setPriorityId] = React.useState('');
  const [assigneeId, setAssigneeId] = React.useState('');
  const [statuses, setStatuses] = React.useState<Status[]>([]);
  const [priorities, setPriorities] = React.useState<Priority[]>([]);
  const [users, setUsers] = React.useState<User[]>([]);
  const [titleError, setTitleError] = React.useState('');

  React.useEffect(() => {
    if (!open) return;

    setTitle('');
    setDescription('');
    setAssigneeId('');
    setTitleError('');
    setLoadError(undefined);

    const loadData = async () => {
      try {
        const [fetchedStatuses, fetchedPriorities, fetchedUsers] =
          await Promise.all([
            getStatuses(sessionToken),
            getPriorities(sessionToken),
            (async () => {
              const clientFactory = new ApiClientFactory(sessionToken);
              const usersClient = clientFactory.getUsersClient();
              const response = await usersClient.getUsers();
              return response.data;
            })(),
          ]);

        setStatuses(fetchedStatuses);
        setPriorities(fetchedPriorities);
        setUsers(fetchedUsers);

        const defaultStatus =
          fetchedStatuses.find(s => s.name === 'Open') || fetchedStatuses[0];
        setStatusId(defaultStatus?.id || '');

        const defaultPriority =
          fetchedPriorities.find(
            p => p.type_value?.toLowerCase() === 'medium'
          ) || fetchedPriorities[0];
        setPriorityId(defaultPriority?.id || '');
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to load form data';
        setLoadError(message);
        show(message, { severity: 'error' });
      }
    };

    loadData();
  }, [open, sessionToken, show]);

  const handleSave = async () => {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setTitleError('Task title is required');
      return;
    }
    if (!statusId) {
      show('Please select a status', { severity: 'error' });
      return;
    }

    setTitleError('');
    setLoadError(undefined);

    try {
      setLoading(true);

      const taskData: TaskCreate = {
        title: trimmedTitle,
        description: description.trim() || undefined,
        status_id: statusId,
        priority_id: priorityId || null,
        assignee_id: assigneeId || null,
        entity_type: initialEntity?.entityType,
        entity_id: initialEntity?.entityId,
        task_metadata: initialEntity?.task_metadata,
      };

      await createTask(taskData);
      onSuccess?.();
      onClose();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to create task';
      setLoadError(message);
      show(message, { severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const entityType = initialEntity?.entityType;
  const commentId = initialEntity?.task_metadata?.comment_id as
    string | undefined;

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="New Task"
      loading={loading}
      error={loadError}
      onSave={handleSave}
      saveButtonText={loading ? 'Creating...' : 'Create Task'}
      width={600}
    >
      <Stack spacing={3}>
        {entityType && (
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Typography variant="body2" color="text.secondary">
              <strong>Related to:</strong> {getEntityDisplayName(entityType)}
              {commentId && <> (from comment)</>}
            </Typography>
          </Box>
        )}

        <TextField
          label="Task Title"
          value={title}
          onChange={e => {
            setTitle(e.target.value);
            if (titleError) setTitleError('');
          }}
          fullWidth
          required
          disabled={loading}
          error={!!titleError}
          helperText={titleError}
          placeholder={
            commentId
              ? 'Enter task title related to the comment...'
              : entityType
                ? `Enter task title for ${getEntityDisplayName(entityType)}...`
                : 'Enter task title...'
          }
        />

        <Box sx={{ display: 'flex', gap: 2 }}>
          <FormControl fullWidth disabled={loading} sx={drawerOutlinedFieldSx}>
            <InputLabel>Status</InputLabel>
            <Select
              value={statusId}
              onChange={e => setStatusId(e.target.value)}
              label="Status"
            >
              {statuses.map(status => (
                <MenuItem key={status.id} value={status.id}>
                  {status.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth disabled={loading} sx={drawerOutlinedFieldSx}>
            <InputLabel>Priority</InputLabel>
            <Select
              value={priorityId}
              onChange={e => setPriorityId(e.target.value)}
              label="Priority"
            >
              {priorities.map(priority => (
                <MenuItem key={priority.id} value={priority.id}>
                  {priority.type_value}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        <FormControl fullWidth disabled={loading} sx={drawerOutlinedFieldSx}>
          <InputLabel shrink>Assignee</InputLabel>
          <Select
            value={assigneeId}
            onChange={e => setAssigneeId(e.target.value)}
            label="Assignee"
            displayEmpty
            renderValue={value =>
              value
                ? (users.find(user => user.id === value)?.name ?? 'Unassigned')
                : 'Unassigned'
            }
          >
            <MenuItem value="">
              <em>Unassigned</em>
            </MenuItem>
            {users
              .filter(user => user.id && user.name)
              .map(user => (
                <MenuItem key={user.id} value={user.id}>
                  {user.name}
                </MenuItem>
              ))}
          </Select>
        </FormControl>

        <TextField
          label="Description"
          value={description}
          onChange={e => setDescription(e.target.value)}
          fullWidth
          multiline
          rows={4}
          disabled={loading}
          placeholder={
            commentId
              ? 'Describe the task related to this comment...'
              : entityType
                ? `Describe the task for ${getEntityDisplayName(entityType)}...`
                : 'Describe the task...'
          }
        />
      </Stack>
    </BaseDrawer>
  );
}
