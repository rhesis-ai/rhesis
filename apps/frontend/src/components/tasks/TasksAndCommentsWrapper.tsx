'use client';

import React, { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Paper, Divider } from '@mui/material';
import { EntityType } from '@/types/tasks';
import { useTasks } from '@/hooks/useTasks';
import { TasksSection } from './TasksSection';
import CommentsWrapper from '@/components/comments/CommentsWrapper';

interface TasksAndCommentsWrapperProps {
  entityType: EntityType;
  entityId: string;
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export function TasksAndCommentsWrapper({
  entityType,
  entityId,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TasksAndCommentsWrapperProps) {
  const router = useRouter();
  const { tasks, isLoading, createTask, deleteTask } = useTasks({ 
    entityType, 
    entityId, 
    autoFetch: true 
  });

  const handleCreateTask = useCallback(async (taskData: any) => {
    try {
      await createTask(taskData);
    } catch (error) {
      console.error('Failed to create task:', error);
    }
  }, [createTask]);

  const handleEditTask = useCallback((taskId: string) => {
    // Navigate to the task detail page
    window.open(`/tasks/${taskId}`, '_blank');
  }, []);

  const handleDeleteTask = useCallback(async (taskId: string) => {
    try {
      await deleteTask(taskId);
    } catch (error) {
      console.error('Failed to delete task:', error);
    }
  }, [deleteTask]);

  const handleCreateTaskFromComment = useCallback((commentId: string) => {
    // Navigate to create task page with entity and comment info
    const params = new URLSearchParams({
      entityType,
      entityId,
      commentId,
    });
    router.push(`/tasks/create?${params.toString()}`);
  }, [router, entityType, entityId]);

  const handleCreateTaskFromEntity = useCallback(() => {
    // Navigate to create task page with entity info
    const params = new URLSearchParams({
      entityType,
      entityId,
    });
    router.push(`/tasks/create?${params.toString()}`);
  }, [router, entityType, entityId]);

  return (
    <Paper sx={{ p: 3 }}>
      {/* Tasks Section */}
      <TasksSection
        entityType={entityType}
        entityId={entityId}
        tasks={tasks}
        onCreateTask={handleCreateTask}
        onEditTask={handleEditTask}
        onDeleteTask={handleDeleteTask}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        isLoading={isLoading}
      />

      {/* Divider between Tasks and Comments */}
      <Divider sx={{ my: 3 }} />

      {/* Comments Section with Task Creation Integration */}
      <CommentsWrapper
        entityType={entityType}
        entityId={entityId}
        sessionToken={sessionToken}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        currentUserPicture={currentUserPicture}
        onCreateTask={handleCreateTaskFromComment}
        onCreateTaskFromEntity={handleCreateTaskFromEntity}
      />
    </Paper>
  );
}
