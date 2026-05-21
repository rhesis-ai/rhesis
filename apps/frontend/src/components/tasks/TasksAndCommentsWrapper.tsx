'use client';

import React, { useCallback, useState } from 'react';
import { Paper } from '@mui/material';
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
  elevation?: number;
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
  elevation = 1,
  onCountsChange,
  additionalMetadata,
}: TasksAndCommentsWrapperProps) {
  const [createDrawerOpen, setCreateDrawerOpen] = useState(false);
  const [pendingCommentId, setPendingCommentId] = useState<
    string | undefined
  >();
  const [isCreating, setIsCreating] = useState(false);

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
      <Paper
        elevation={elevation}
        sx={{ p: 3, mb: 3 }}
        suppressHydrationWarning
      >
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
        />
      </Paper>

      <Paper elevation={elevation} sx={{ p: 3 }} suppressHydrationWarning>
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
      </Paper>

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
