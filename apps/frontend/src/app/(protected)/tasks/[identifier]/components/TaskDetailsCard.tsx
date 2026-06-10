'use client';

import React from 'react';
import {
  Avatar,
  Box,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import EditableSection from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';
import { Priority, Status, Task, TaskUpdate } from '@/types/tasks';
import type { User } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';

interface AssigneeDisplay {
  name?: string;
  picture?: string;
}

interface TaskDetailsDraft {
  title: string;
  description: string;
  status_id: string;
  priority_id: string;
  assignee_id: string;
}

interface TaskDetailsCardProps {
  task: Task;
  statuses: Status[];
  priorities: Priority[];
  users: User[];
  onSave: (update: TaskUpdate) => Promise<Task | null | undefined>;
  onTaskUpdated: (task: Task) => void;
}

function UserFieldContent({
  user,
  fallback,
}: {
  user?: AssigneeDisplay | null;
  fallback: string;
}) {
  if (!user?.name) {
    return (
      <Typography
        sx={{
          fontSize: 16,
          lineHeight: '24px',
          color: theme => theme.palette.greyscale.body,
        }}
      >
        {fallback}
      </Typography>
    );
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Avatar
        src={user.picture}
        alt={user.name}
        sx={{
          width: AVATAR_SIZES.SMALL,
          height: AVATAR_SIZES.SMALL,
          bgcolor: 'primary.main',
        }}
      >
        {user.name.charAt(0)}
      </Avatar>
      <Typography
        sx={{
          fontSize: 16,
          lineHeight: '24px',
          color: theme => theme.palette.greyscale.body,
        }}
      >
        {user.name}
      </Typography>
    </Box>
  );
}

function toDraft(task: Task): TaskDetailsDraft {
  return {
    title: task.title || '',
    description: task.description || '',
    status_id: task.status_id || '',
    priority_id: task.priority_id || '',
    assignee_id: task.assignee_id || '',
  };
}

function statusLabel(statuses: Status[], statusId: string): string {
  return statuses.find(status => status.id === statusId)?.name ?? '—';
}

function priorityLabel(priorities: Priority[], priorityId: string): string {
  return (
    priorities.find(priority => priority.id === priorityId)?.type_value ?? '—'
  );
}

export default function TaskDetailsCard({
  task,
  statuses,
  priorities,
  users,
  onSave,
  onTaskUpdated,
}: TaskDetailsCardProps) {
  const { show } = useNotifications();
  const initialDraft = React.useMemo(() => toDraft(task), [task]);

  const handleSave = async (draft: TaskDetailsDraft) => {
    if (!draft.title.trim()) {
      show('Task title cannot be empty', { severity: 'error' });
      return false;
    }

    const updatedTask = await onSave({
      title: draft.title.trim(),
      description: draft.description,
      status_id: draft.status_id,
      priority_id: draft.priority_id || null,
      assignee_id: draft.assignee_id || null,
    });

    if (updatedTask) {
      onTaskUpdated(updatedTask);
      show('Task updated successfully', { severity: 'success' });
    }

    return Boolean(updatedTask);
  };

  const assigneeForDraft = (
    assigneeId: string
  ): AssigneeDisplay | undefined => {
    if (!assigneeId) {
      return undefined;
    }

    const fromList = users.find(user => user.id === assigneeId);
    if (fromList) {
      return fromList;
    }

    return task.assignee;
  };

  return (
    <EditableSection
      title="Task details"
      initialValue={initialDraft}
      onSave={handleSave}
    >
      {({ draft, setDraft, isEditing }) => (
        <Grid
          container
          columnSpacing={isEditing ? 2 : '30px'}
          rowSpacing={isEditing ? 2 : '50px'}
        >
          <Grid size={12}>
            {isEditing ? (
              <TextField
                fullWidth
                label="Title"
                value={draft.title}
                onChange={event =>
                  setDraft(current => ({
                    ...current,
                    title: event.target.value,
                  }))
                }
                variant="outlined"
                helperText="Task title"
                error={!draft.title.trim()}
              />
            ) : (
              <ViewField
                label="Title"
                value={draft.title}
                helperText="Task title"
              />
            )}
          </Grid>

          <Grid size={12}>
            {isEditing ? (
              <TextField
                fullWidth
                multiline
                minRows={3}
                label="Description"
                value={draft.description}
                onChange={event =>
                  setDraft(current => ({
                    ...current,
                    description: event.target.value,
                  }))
                }
                variant="outlined"
                helperText="Additional context for this task"
              />
            ) : (
              <ViewField
                label="Description"
                value={draft.description}
                helperText="Additional context for this task"
                multiline
              />
            )}
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            {isEditing ? (
              <FormControl fullWidth>
                <InputLabel>Status</InputLabel>
                <Select
                  value={draft.status_id}
                  label="Status"
                  onChange={event =>
                    setDraft(current => ({
                      ...current,
                      status_id: event.target.value,
                    }))
                  }
                >
                  {statuses.map(status => (
                    <MenuItem key={status.id} value={status.id}>
                      {status.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            ) : (
              <ViewField
                label="Status"
                value={statusLabel(statuses, draft.status_id)}
                helperText="Current workflow status"
              />
            )}
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            {isEditing ? (
              <FormControl fullWidth>
                <InputLabel>Priority</InputLabel>
                <Select
                  value={draft.priority_id}
                  label="Priority"
                  onChange={event =>
                    setDraft(current => ({
                      ...current,
                      priority_id: event.target.value,
                    }))
                  }
                >
                  {priorities.map(priority => (
                    <MenuItem key={priority.id} value={priority.id}>
                      {priority.type_value}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            ) : (
              <ViewField
                label="Priority"
                value={priorityLabel(priorities, draft.priority_id)}
                helperText="Task urgency level"
              />
            )}
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            {isEditing ? (
              <FormControl fullWidth>
                <InputLabel shrink>Assignee</InputLabel>
                <Select
                  value={draft.assignee_id}
                  label="Assignee"
                  displayEmpty
                  onChange={event =>
                    setDraft(current => ({
                      ...current,
                      assignee_id: event.target.value,
                    }))
                  }
                  sx={{
                    '& .MuiSelect-select': {
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      py: 2,
                    },
                  }}
                  renderValue={value => {
                    const selectedUser = assigneeForDraft(String(value));
                    return (
                      <UserFieldContent
                        user={selectedUser}
                        fallback="Unassigned"
                      />
                    );
                  }}
                >
                  <MenuItem value="">
                    <UserFieldContent user={null} fallback="Unassigned" />
                  </MenuItem>
                  {users
                    .filter(user => user.id && user.name)
                    .map(user => (
                      <MenuItem key={user.id} value={user.id}>
                        <UserFieldContent user={user} fallback="Unassigned" />
                      </MenuItem>
                    ))}
                </Select>
              </FormControl>
            ) : (
              <ViewField
                label="Assignee"
                helperText="User responsible for this task"
              >
                <UserFieldContent
                  user={assigneeForDraft(draft.assignee_id)}
                  fallback="Unassigned"
                />
              </ViewField>
            )}
          </Grid>
        </Grid>
      )}
    </EditableSection>
  );
}
