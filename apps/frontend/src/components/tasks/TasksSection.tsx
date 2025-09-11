'use client';

import React from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
} from '@mui/material';
import { Task, EntityType } from '@/types/tasks';
import { TaskItem } from './TaskItem';

interface TasksSectionProps {
  entityType: EntityType;
  entityId: string;
  tasks: Task[];
  onCreateTask: (taskData: any) => Promise<void>;
  onEditTask?: (taskId: string) => void;
  onDeleteTask?: (taskId: string) => Promise<void>;
  currentUserId: string;
  currentUserName: string;
  isLoading?: boolean;
}

export function TasksSection({
  entityType,
  entityId,
  tasks,
  onCreateTask,
  onEditTask,
  onDeleteTask,
  currentUserId,
  currentUserName,
  isLoading = false,
}: TasksSectionProps) {


  const handleDeleteTask = async (taskId: string) => {
    if (onDeleteTask) {
      try {
        await onDeleteTask(taskId);
      } catch (error) {
        console.error('Failed to delete task:', error);
      }
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
      default:
        return entityType;
    }
  };

  const sortedTasks = [...tasks].sort((a, b) => 
    new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  return (
    <>
      <Paper sx={{ p: 3, mb: 4 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h6" fontWeight={600}>
            Tasks ({tasks.length})
          </Typography>
        </Box>

        {/* Tasks List */}
        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : tasks.length === 0 ? (
          <Box 
            sx={{ 
              textAlign: 'center', 
              py: 6,
              border: '2px dashed',
              borderColor: 'divider',
              borderRadius: 2,
              bgcolor: 'background.default',
            }}
          >
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No tasks yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Create the first task for this {getEntityDisplayName(entityType)}.
            </Typography>
          </Box>
        ) : (
          <Box>
            {sortedTasks.map((task) => (
              <TaskItem
                key={task.id}
                task={task}
                onEdit={onEditTask}
                onDelete={handleDeleteTask}
                currentUserId={currentUserId}
                showEntityLink={false}
              />
            ))}
          </Box>
        )}
      </Paper>

    </>
  );
}
