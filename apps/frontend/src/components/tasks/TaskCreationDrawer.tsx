'use client';

import React, { useState, useEffect } from 'react';
import {
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
} from '@mui/material';
import { EntityType } from '@/types/tasks';
import { getPriorities, getStatuses } from '@/utils/task-lookup';
import { getEntityDisplayName } from '@/utils/entity-helpers';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { Priority, Status } from '@/utils/api-client/interfaces/task';
import { useSession } from 'next-auth/react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { drawerOutlinedFieldSx } from '@/components/common/drawerFormFieldSx';

interface TaskCreationDrawerProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (taskData: Record<string, unknown>) => Promise<void>;
  entityType: EntityType;
  entityId: string;
  isLoading?: boolean;
  commentId?: string;
}

export function TaskCreationDrawer({
  open,
  onClose,
  onSubmit,
  entityType,
  entityId,
  isLoading = false,
  commentId,
}: TaskCreationDrawerProps) {
  const { data: session } = useSession();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [statusId, setStatusId] = useState<string>('');
  const [priorityId, setPriorityId] = useState<string>('');
  const [assigneeId, setAssigneeId] = useState('');
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [priorities, setPriorities] = useState<Priority[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [isLoadingData, setIsLoadingData] = useState(false);

  // Load data when modal opens
  useEffect(() => {
    const loadData = async () => {
      const sessionToken = session?.session_token;
      if (!open || !sessionToken) return;

      setIsLoadingData(true);
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

        // Default to "Open" status
        const openStatus = fetchedStatuses.find(s => s.name === 'Open');
        if (openStatus) {
          setStatusId(openStatus.id);
        }
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
      status_id: statusId,
      priority_id: priorityId || null,
      assignee_id: assigneeId || null,
      entity_type: entityType,
      entity_id: entityId,
      task_metadata: commentId ? { comment_id: commentId } : undefined,
    });

    // Reset form
    setTitle('');
    setDescription('');
    setStatusId('');
    setPriorityId('');
    setAssigneeId('');
  };

  const handleClose = () => {
    if (!isLoading) {
      setTitle('');
      setDescription('');
      setStatusId('');
      setPriorityId('');
      setAssigneeId('');
      onClose();
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title="Create task"
      loading={isLoading}
      onSave={handleSubmit}
      saveButtonText="Save"
      closeButtonText="Close"
      saveDisabled={!title.trim()}
      width={578}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Comment context note */}
        {commentId && (
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Typography variant="body2" color="text.secondary">
              <strong>From comment on:</strong>{' '}
              {getEntityDisplayName(entityType)}
            </Typography>
          </Box>
        )}

        {/* Task Title */}
        <TextField
          label="Task Title*"
          value={title}
          onChange={e => setTitle(e.target.value)}
          fullWidth
          variant="outlined"
          disabled={isLoading}
          sx={drawerOutlinedFieldSx}
        />

        {/* Status */}
        <FormControl fullWidth sx={drawerOutlinedFieldSx}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusId}
            onChange={e => setStatusId(e.target.value)}
            label="Status"
            disabled={isLoadingData || isLoading}
          >
            {statuses.map(statusOption => (
              <MenuItem key={statusOption.id} value={statusOption.id}>
                {statusOption.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Priority */}
        <FormControl fullWidth sx={drawerOutlinedFieldSx}>
          <InputLabel>Priority</InputLabel>
          <Select
            value={priorityId}
            onChange={e => setPriorityId(e.target.value)}
            label="Priority"
            disabled={isLoadingData || isLoading}
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {priorities.map(priorityOption => (
              <MenuItem key={priorityOption.id} value={priorityOption.id}>
                {priorityOption.type_value || priorityOption.id}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Assignee */}
        <FormControl fullWidth sx={drawerOutlinedFieldSx}>
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

        {/* Description */}
        <TextField
          label="Description"
          value={description}
          onChange={e => setDescription(e.target.value)}
          fullWidth
          multiline
          rows={4}
          variant="outlined"
          disabled={isLoading}
          sx={drawerOutlinedFieldSx}
        />
      </Box>
    </BaseDrawer>
  );
}

export default TaskCreationDrawer;
