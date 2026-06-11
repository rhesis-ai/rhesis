'use client';

import React, { useCallback, useState } from 'react';
import { Box } from '@mui/material';
import { EntityType } from '@/types/tasks';
import type { TaskCreate } from '@/utils/api-client/interfaces/task';
import { useTasks } from '@/hooks/useTasks';
import { TasksSection } from './TasksSection';
import CommentsWrapper from '@/components/comments/CommentsWrapper';
import { TaskCreationDrawer } from './TaskCreationDrawer';

interface TasksAndCommentsWrapperProps {
  entityType: EntityType;
  entityId: string;
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
  onCountsChange?: () => void;
  additionalMetadata?: Record<string, unknown>;
}

export function TasksAndCommentsWrapper({
  entityType,
  entityId,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
  onCountsChange,
  additionalMetadata,
}: TasksAndCommentsWrapperProps) {
  const [createDrawerOpen, setCreateDrawerOpen] = useState(false);
  const [pendingCommentId, setPendingCommentId] = useState<
    string | undefined
  >();
  const [isCreating, setIsCreating] = useState(false);
  const [tasksRefreshKey, setTasksRefreshKey] = useState(0);

  const { createTask, deleteTask } = useTasks({
    entityType,
    entityId,
    autoFetch: false,
  });

  const handleCreateTask = useCallback(
    async (taskData: Record<string, unknown>) => {
      try {
        setIsCreating(true);
        const baseTask = taskData as unknown as TaskCreate;
        const enrichedTaskData: TaskCreate = {
          ...baseTask,
          ...(additionalMetadata && Object.keys(additionalMetadata).length > 0
            ? {
                task_metadata: {
                  ...(baseTask.task_metadata || {}),
                  ...additionalMetadata,
                },
              }
            : {}),
        };
        await createTask(enrichedTaskData);
        setCreateDrawerOpen(false);
        setPendingCommentId(undefined);
        setTasksRefreshKey(key => key + 1);
        await onCountsChange?.();
      } catch {
        // Errors surfaced by useTasks
      } finally {
        setIsCreating(false);
      }
    },
    [createTask, onCountsChange, additionalMetadata]
  );

  const handleEditTask = useCallback((taskId: string) => {
    window.open(`/tasks/${taskId}`, '_blank');
  }, []);

  const handleDeleteTask = useCallback(
    async (taskId: string) => {
      try {
        await deleteTask(taskId);
        setTasksRefreshKey(key => key + 1);
        await onCountsChange?.();
      } catch {
        // Errors surfaced by useTasks
      }
    },
    [deleteTask, onCountsChange]
  );

  const handleOpenCreateDrawer = useCallback((commentId?: string) => {
    setPendingCommentId(commentId);
    setCreateDrawerOpen(true);
  }, []);

  const handleCloseCreateDrawer = useCallback(() => {
    if (!isCreating) {
      setCreateDrawerOpen(false);
      setPendingCommentId(undefined);
    }
  }, [isCreating]);

  return (
    <>
      <TasksSection
        entityType={entityType}
        entityId={entityId}
        sessionToken={sessionToken}
        onCreateTask={handleCreateTask}
        onEditTask={handleEditTask}
        onDeleteTask={handleDeleteTask}
        onOpenCreateDrawer={handleOpenCreateDrawer}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        refreshKey={tasksRefreshKey}
      />

      <Box sx={{ mt: '16px' }}>
        <CommentsWrapper
          entityType={entityType}
          entityId={entityId}
          sessionToken={sessionToken}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
          onCreateTask={commentId => handleOpenCreateDrawer(commentId)}
          onCreateTaskFromEntity={() => handleOpenCreateDrawer()}
          onCountsChange={onCountsChange}
        />
      </Box>

      <TaskCreationDrawer
        open={createDrawerOpen}
        onClose={handleCloseCreateDrawer}
        onSubmit={handleCreateTask}
        entityType={entityType}
        entityId={entityId}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        isLoading={isCreating}
        commentId={pendingCommentId}
      />
    </>
  );
}
