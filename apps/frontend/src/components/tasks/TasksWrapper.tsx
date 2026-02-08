'use client';

import React, { useCallback } from 'react';
import { EntityType } from '@/types/tasks';
import { useTasks } from '@/hooks/useTasks';
import { TasksSection } from './TasksSection';
import { TaskCreationDrawer } from './TaskCreationDrawer';

interface TasksWrapperProps {
  entityType: EntityType;
  entityId: string;
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export function TasksWrapper({
  entityType,
  entityId,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TasksWrapperProps) {
  const { createTask, deleteTask } = useTasks({
    entityType,
    entityId,
    autoFetch: false, // TasksSection will handle fetching
  });

  const handleCreateTask = useCallback(
    async (taskData: any) => {
      try {
        await createTask(taskData);
      } catch (_error) {}
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
      } catch (_error) {}
    },
    [deleteTask]
  );

  return (
    <>
      <TasksSection
        entityType={entityType}
        entityId={entityId}
        sessionToken={sessionToken}
        onCreateTask={handleCreateTask}
        onEditTask={handleEditTask}
        onDeleteTask={handleDeleteTask}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
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
