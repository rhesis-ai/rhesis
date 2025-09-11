'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Chip,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Divider,
  Link,
  CircularProgress,
} from '@mui/material';
import {
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  Assignment as TaskIcon,
} from '@mui/icons-material';
import { formatDistanceToNow, format } from 'date-fns';
import { useSession } from 'next-auth/react';
import { Task, TaskStatus, TaskPriority, EntityType } from '@/types/tasks';
import { mockTasks, mockUsers } from '@/utils/mock-data/tasks';
import { UserAvatar } from '@/components/common/UserAvatar';
import CommentsWrapper from '@/components/comments/CommentsWrapper';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function TaskDetailPage({ params }: PageProps) {
  const { data: session } = useSession();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editedTask, setEditedTask] = useState<Task | null>(null);
  const [taskId, setTaskId] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);

  // Get the task ID from params
  React.useEffect(() => {
    params.then(({ id }) => {
      setTaskId(id);
      setIsLoading(false);
    });
  }, [params]);

  // Find the task (in a real app, this would come from an API)
  const task = mockTasks.find(t => t.id === taskId);

  // Show loading state while taskId is being set
  if (isLoading) {
    return (
      <Box sx={{ p: 3, maxWidth: 800, mx: 'auto', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  // Show error if task not found
  if (!task) {
    return (
      <Box sx={{ p: 3, maxWidth: 800, mx: 'auto', textAlign: 'center' }}>
        <Typography variant="h5" color="error" gutterBottom>
          Task Not Found
        </Typography>
        <Typography variant="body1" color="text.secondary">
          The task with ID &quot;{taskId}&quot; could not be found.
        </Typography>
      </Box>
    );
  }

  const handleEdit = () => {
    setEditedTask({ ...task });
    setIsEditing(true);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // In a real app, this would make an API call
      console.log('Saving task:', editedTask);
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      setIsEditing(false);
      setEditedTask(null);
    } catch (error) {
      console.error('Failed to save task:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setEditedTask(null);
    setIsEditing(false);
  };

  const handleFieldChange = (field: keyof Task, value: any) => {
    if (editedTask) {
      setEditedTask({ ...editedTask, [field]: value });
    }
  };

  const getStatusColor = (status: TaskStatus) => {
    switch (status) {
      case 'Open':
        return 'default';
      case 'In Progress':
        return 'primary';
      case 'Completed':
        return 'success';
      case 'Cancelled':
        return 'error';
      default:
        return 'default';
    }
  };

  const getPriorityColor = (priority: TaskPriority) => {
    switch (priority) {
      case 'Low':
        return 'default';
      case 'Medium':
        return 'warning';
      case 'High':
        return 'error';
      default:
        return 'default';
    }
  };

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

  const currentTask = editedTask || task;

  return (
    <Box sx={{ p: 3, maxWidth: 800, mx: 'auto' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <TaskIcon color="primary" />
          <Box>
            <Typography variant="h4" fontWeight={600}>
              Task Details
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Created {formatDistanceToNow(new Date(task.created_at), { addSuffix: true })}
            </Typography>
          </Box>
        </Box>

        {!isEditing ? (
          <Button
            variant="outlined"
            startIcon={<EditIcon />}
            onClick={handleEdit}
          >
            Edit Task
          </Button>
        ) : (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="contained"
              startIcon={isSaving ? <CircularProgress size={16} /> : <SaveIcon />}
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? 'Saving...' : 'Save'}
            </Button>
            <Button
              variant="outlined"
              startIcon={<CancelIcon />}
              onClick={handleCancel}
              disabled={isSaving}
            >
              Cancel
            </Button>
          </Box>
        )}
      </Box>

      {/* Task Content */}
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Title */}
          <Box>
            <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
              Title
            </Typography>
            {isEditing ? (
              <TextField
                value={currentTask.title}
                onChange={(e) => handleFieldChange('title', e.target.value)}
                fullWidth
                variant="outlined"
                size="small"
              />
            ) : (
              <Typography variant="h6" fontWeight={500}>
                {currentTask.title}
              </Typography>
            )}
          </Box>

          {/* Description */}
          <Box>
            <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
              Description
            </Typography>
            {isEditing ? (
              <TextField
                value={currentTask.description}
                onChange={(e) => handleFieldChange('description', e.target.value)}
                fullWidth
                multiline
                rows={4}
                variant="outlined"
                size="small"
              />
            ) : (
              <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                {currentTask.description}
              </Typography>
            )}
          </Box>

          {/* Status and Priority */}
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                Status
              </Typography>
              {isEditing ? (
                <FormControl fullWidth size="small">
                  <Select
                    value={currentTask.status}
                    onChange={(e) => handleFieldChange('status', e.target.value)}
                  >
                    <MenuItem value="Open">Open</MenuItem>
                    <MenuItem value="In Progress">In Progress</MenuItem>
                    <MenuItem value="Completed">Completed</MenuItem>
                    <MenuItem value="Cancelled">Cancelled</MenuItem>
                  </Select>
                </FormControl>
              ) : (
                <Chip
                  label={currentTask.status}
                  color={getStatusColor(currentTask.status)}
                  variant="outlined"
                />
              )}
            </Box>

            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                Priority
              </Typography>
              {isEditing ? (
                <FormControl fullWidth size="small">
                  <Select
                    value={currentTask.priority}
                    onChange={(e) => handleFieldChange('priority', e.target.value)}
                  >
                    <MenuItem value="Low">Low</MenuItem>
                    <MenuItem value="Medium">Medium</MenuItem>
                    <MenuItem value="High">High</MenuItem>
                  </Select>
                </FormControl>
              ) : (
                <Chip
                  label={currentTask.priority}
                  color={getPriorityColor(currentTask.priority)}
                  variant="outlined"
                />
              )}
            </Box>
          </Box>

          {/* Assignee */}
          <Box>
            <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
              Assignee
            </Typography>
            {isEditing ? (
              <FormControl fullWidth size="small">
                <Select
                  value={currentTask.assignee_id || ''}
                  onChange={(e) => handleFieldChange('assignee_id', e.target.value)}
                >
                  <MenuItem value="">
                    <em>Unassigned</em>
                  </MenuItem>
                  {mockUsers.map((user) => (
                    <MenuItem key={user.id} value={user.id}>
                      {user.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            ) : (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <UserAvatar 
                  userName={currentTask.assignee_name || currentTask.creator_name}
                  size={32}
                />
                <Typography variant="body1">
                  {currentTask.assignee_name || 'Unassigned'}
                </Typography>
              </Box>
            )}
          </Box>

          <Divider />

          {/* Metadata */}
          <Box>
            <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2 }}>
              Task Information
            </Typography>
            
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  Created by:
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <UserAvatar 
                    userName={currentTask.creator_name}
                    size={20}
                  />
                  <Typography variant="body2">
                    {currentTask.creator_name}
                  </Typography>
                </Box>
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  Created at:
                </Typography>
                <Typography variant="body2">
                  {format(new Date(currentTask.created_at), 'PPP p')}
                </Typography>
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  Last updated:
                </Typography>
                <Typography variant="body2">
                  {format(new Date(currentTask.updated_at), 'PPP p')}
                </Typography>
              </Box>

              {currentTask.completed_at && (
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Completed at:
                  </Typography>
                  <Typography variant="body2">
                    {format(new Date(currentTask.completed_at), 'PPP p')}
                  </Typography>
                </Box>
              )}

              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">
                  Related to:
                </Typography>
                <Link href={`/${getEntityPath(currentTask.entity_type)}/${currentTask.entity_id}`}>
                  <Typography variant="body2" color="primary">
                    {getEntityDisplayName(currentTask.entity_type)}
                  </Typography>
                </Link>
              </Box>

              {currentTask.comment_id && (
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Created from comment:
                  </Typography>
                  <Link href={`/${getEntityPath(currentTask.entity_type)}/${currentTask.entity_id}#comment-${currentTask.comment_id}`}>
                    <Typography variant="body2" color="primary">
                      View Comment
                    </Typography>
                  </Link>
                </Box>
              )}
            </Box>
          </Box>
        </Box>
      </Paper>

      {/* Comments Section */}
      <CommentsWrapper
        entityType="Task"
        entityId={taskId}
        sessionToken={session?.session_token || ''}
        currentUserId={session?.user?.id || ''}
        currentUserName={session?.user?.name || ''}
        currentUserPicture={session?.user?.image || undefined}
      />
    </Box>
  );
}
