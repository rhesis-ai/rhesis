'use client';

import React, { useCallback } from 'react';
import { EntityType } from '@/types/tasks';
import { useTasks } from '@/hooks/useTasks';
import { TasksSection } from './TasksSection';
import { TaskCreationDrawer } from './TaskCreationDrawer';

interface TasksWrapperProps {
  entityType: EntityType;
  entityId: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export function TasksWrapper({
  entityType,
  entityId,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TasksWrapperProps) {
  const { tasks, isLoading, createTask, deleteTask } = useTasks({
    entityType,
    entityId,
    autoFetch: true,
  });

  const handleCreateTask = useCallback(
    async (taskData: any) => {
      try {
        await createTask(taskData);
      } catch (error) {
        console.error('Failed to create task:', error);
      }
    },
    [createTask]
  );

  const handleEditTask = useCallback((taskId: string) => {
    // Navigate to the task detail page
    window.open(`/tasks/${taskId}`, '_blank');
  }, []);

  const handleDeleteTask = useCallback(
    async (taskId: string) => {
      try {
        await deleteTask(taskId);
      } catch (error) {
        console.error('Failed to delete task:', error);
      }
    },
    [deleteTask]
  );

  return (
    <>
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

      {/* Task Creation Modal */}
      <TaskCreationDrawer
        open={false} // This will be controlled by the TasksSection component
        onClose={() => {
          (window as any).pendingCommentId = undefined;
        }}
        onSubmit={handleCreateTask}
        entityType={entityType}
        entityId={entityId}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        isLoading={false}
        commentId={(window as any).pendingCommentId}
      />
    </>
  );
}
