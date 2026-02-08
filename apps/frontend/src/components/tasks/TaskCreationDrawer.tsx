'use client';

import React, { useState, useEffect } from 'react';
import {
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
  CircularProgress,
} from '@mui/material';
import { EntityType } from '@/types/tasks';
import { getPriorities } from '@/utils/task-lookup';
import { getEntityDisplayName } from '@/utils/entity-helpers';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { Priority } from '@/utils/api-client/interfaces/task';
import { useSession } from 'next-auth/react';
import BaseDrawer from '@/components/common/BaseDrawer';

interface TaskCreationDrawerProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (taskData: any) => Promise<void>;
  entityType: EntityType;
  entityId: string;
  currentUserId: string;
  currentUserName: string;
  isLoading?: boolean;
  commentId?: string;
}

export function TaskCreationDrawer({
  open,
  onClose,
  onSubmit,
  entityType,
  entityId,
  currentUserId,
  currentUserName,
  isLoading = false,
  commentId,
}: TaskCreationDrawerProps) {
  const { data: session } = useSession();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priorityId, setPriorityId] = useState<string>('');
  const [assigneeId, setAssigneeId] = useState('');
  const [priorities, setPriorities] = useState<Priority[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [isLoadingData, setIsLoadingData] = useState(false);

  // Load data when modal opens
  useEffect(() => {
    const loadData = async () => {
      if (!open || !session?.session_token) return;

      setIsLoadingData(true);
      try {
        const [fetchedPriorities, fetchedUsers] = await Promise.all([
          getPriorities(session.session_token),
          (async () => {
            const clientFactory = new ApiClientFactory(session.session_token!);
            const usersClient = clientFactory.getUsersClient();
            const response = await usersClient.getUsers();
            return response.data;
          })(),
        ]);

        setPriorities(fetchedPriorities);
        setUsers(fetchedUsers);
      } catch (_error) {
      } finally {
        setIsLoadingData(false);
      }
    };

    loadData();
  }, [open, session?.session_token]);

  const handleSubmit = async () => {
    if (!title.trim()) return;

    await onSubmit({
      title: title.trim(),
      description: description.trim(),
      priority_id: priorityId || null,
      assignee_id: assigneeId || null,
      entity_type: entityType,
      entity_id: entityId,
      task_metadata: commentId ? { comment_id: commentId } : undefined,
    });

    // Reset form
    setTitle('');
    setDescription('');
    setPriorityId('');
    setAssigneeId('');
  };

  const handleClose = () => {
    if (!isLoading) {
      setTitle('');
      setDescription('');
      setPriorityId('');
      setAssigneeId('');
      onClose();
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title="Create New Task"
      loading={isLoading}
      onSave={handleSubmit}
      saveButtonText={isLoading ? 'Creating...' : 'Create Task'}
      width={600}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Comment context info */}
        {commentId && (
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Typography variant="body2" color="text.secondary">
              <strong>From comment on:</strong>{' '}
              {getEntityDisplayName(entityType)}
            </Typography>
          </Box>
        )}

        {/* Title */}
        <TextField
          label="Task Title"
          value={title}
          onChange={e => setTitle(e.target.value)}
          fullWidth
          required
          variant="outlined"
          placeholder="Enter a brief description of the task"
          disabled={isLoading}
        />

        {/* Description */}
        <TextField
          label="Description"
          value={description}
          onChange={e => setDescription(e.target.value)}
          fullWidth
          multiline
          rows={4}
          variant="outlined"
          placeholder="Provide detailed information about what needs to be done"
          disabled={isLoading}
        />

        {/* Priority and Assignee Row */}
        <Box sx={{ display: 'flex', gap: 2 }}>
          {/* Priority */}
          <FormControl fullWidth>
            <InputLabel>Priority</InputLabel>
            <Select
              value={priorityId}
              onChange={e => setPriorityId(e.target.value)}
              label="Priority"
              disabled={isLoadingData || isLoading}
            >
              {priorities.map(priorityOption => (
                <MenuItem key={priorityOption.id} value={priorityOption.id}>
                  {priorityOption.type_value || priorityOption.id}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Assignee */}
          <FormControl fullWidth>
            <InputLabel>Assignee</InputLabel>
            <Select
              value={assigneeId}
              onChange={e => setAssigneeId(e.target.value)}
              label="Assignee"
              disabled={isLoadingData || isLoading}
            >
              <MenuItem value="">
                <em>Unassigned</em>
              </MenuItem>
              {users.map(user => (
                <MenuItem key={user.id} value={user.id}>
                  {user.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {/* Entity Info */}
        <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
          <Typography variant="body2" color="text.secondary">
            <strong>Related to:</strong> {getEntityDisplayName(entityType)}
          </Typography>
          {commentId && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              <strong>From comment:</strong> This task was created from a
              comment
            </Typography>
          )}
        </Box>
      </Box>
    </BaseDrawer>
  );
}

export default TaskCreationDrawer;
