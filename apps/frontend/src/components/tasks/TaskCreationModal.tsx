'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
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
import { TaskPriority, EntityType } from '@/types/tasks';
import { getPriorities } from '@/utils/task-lookup';
import { getEntityDisplayName } from '@/utils/entity-helpers';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { User } from '@/utils/api-client/interfaces/user';
import { useSession } from 'next-auth/react';

interface TaskCreationModalProps {
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

export function TaskCreationModal({
  open,
  onClose,
  onSubmit,
  entityType,
  entityId,
  currentUserId,
  currentUserName,
  isLoading = false,
  commentId,
}: TaskCreationModalProps) {
  const { data: session } = useSession();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<TaskPriority>('Medium');
  const [assigneeId, setAssigneeId] = useState('');
  const [priorities, setPriorities] = useState<any[]>([]);
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
          })()
        ]);

        setPriorities(fetchedPriorities);
        setUsers(fetchedUsers);
      } catch (error) {
        console.error('Error loading task creation data:', error);
      } finally {
        setIsLoadingData(false);
      }
    };
    
    loadData();
  }, [open, session?.session_token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    await onSubmit({
      title: title.trim(),
      description: description.trim(),
      priority,
      assignee_id: assigneeId || undefined,
      entity_type: entityType,
      entity_id: entityId,
      task_metadata: commentId ? { comment_id: commentId } : undefined,
    });

    // Reset form
    setTitle('');
    setDescription('');
    setPriority('Medium');
    setAssigneeId('');
  };

  const handleClose = () => {
    if (!isLoading) {
      setTitle('');
      setDescription('');
      setPriority('Medium');
      setAssigneeId('');
      onClose();
    }
  };

  return (
    <Dialog 
      open={open} 
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle>
        Create New Task
        {commentId && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            From comment on {getEntityDisplayName(entityType)}
          </Typography>
        )}
      </DialogTitle>
      
      <form onSubmit={handleSubmit}>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Title */}
            <TextField
              label="Task Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              fullWidth
              required
              variant="outlined"
              placeholder="Enter a brief description of the task"
            />

            {/* Description */}
            <TextField
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              fullWidth
              multiline
              rows={4}
              variant="outlined"
              placeholder="Provide detailed information about what needs to be done"
            />

            {/* Priority and Assignee Row */}
            <Box sx={{ display: 'flex', gap: 2 }}>
              {/* Priority */}
              <FormControl fullWidth>
                <InputLabel>Priority</InputLabel>
                <Select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as TaskPriority)}
                  label="Priority"
                  disabled={isLoadingData}
                >
                  {priorities.map((priorityOption) => (
                    <MenuItem key={priorityOption.type_value} value={priorityOption.type_value}>
                      {priorityOption.type_value}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Assignee */}
              <FormControl fullWidth>
                <InputLabel>Assignee</InputLabel>
                <Select
                  value={assigneeId}
                  onChange={(e) => setAssigneeId(e.target.value)}
                  label="Assignee"
                  disabled={isLoadingData}
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
            </Box>

            {/* Entity Info */}
            <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
              <Typography variant="body2" color="text.secondary">
                <strong>Related to:</strong> {getEntityDisplayName(entityType)}
              </Typography>
              {commentId && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  <strong>From comment:</strong> This task was created from a comment
                </Typography>
              )}
            </Box>
          </Box>
        </DialogContent>

        <DialogActions>
          <Button 
            onClick={handleClose} 
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button 
            type="submit" 
            variant="contained"
            disabled={isLoading || !title.trim() || isLoadingData}
            startIcon={isLoading ? <CircularProgress size={16} /> : undefined}
          >
            {isLoading ? 'Creating...' : 'Create Task'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
