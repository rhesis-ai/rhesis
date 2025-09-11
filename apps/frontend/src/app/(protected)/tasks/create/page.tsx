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
} from '@mui/material';
import { ArrowBack as ArrowBackIcon, Save as SaveIcon } from '@mui/icons-material';
import { TaskStatus, TaskPriority, EntityType } from '@/types/tasks';
import { useNotifications } from '@/components/common/NotificationContext';

export default function CreateTaskPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { show } = useNotifications();
  
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    status: 'Open' as TaskStatus,
    priority: 'Medium' as TaskPriority,
    assignee_id: '',
  });
  
  const [isSubmitting, setIsSubmitting] = useState(false);

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
      // In a real app, this would make an API call
      console.log('Creating task:', {
        ...formData,
        entityType: searchParams.get('entityType'),
        entityId: searchParams.get('entityId'),
        commentId: searchParams.get('commentId'),
      });
      
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      show('Task created successfully!', { severity: 'neutral' });
      
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
    } catch (error) {
      console.error('Failed to create task:', error);
      show('Failed to create task. Please try again.', { severity: 'error' });
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
                >
                  <MenuItem value="Open">Open</MenuItem>
                  <MenuItem value="In Progress">In Progress</MenuItem>
                  <MenuItem value="Completed">Completed</MenuItem>
                  <MenuItem value="Cancelled">Cancelled</MenuItem>
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
                >
                  <MenuItem value="Low">Low</MenuItem>
                  <MenuItem value="Medium">Medium</MenuItem>
                  <MenuItem value="High">High</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {/* Assignee */}
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Assignee ID"
                value={formData.assignee_id}
                onChange={(e) => handleInputChange('assignee_id', e.target.value)}
                placeholder="Enter user ID to assign this task (optional)"
              />
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
