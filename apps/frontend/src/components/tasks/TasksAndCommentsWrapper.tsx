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
  elevation?: number;
  onCountsChange?: () => void;
  additionalMetadata?: Record<string, any>;
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
  const router = useRouter();

  const { createTask, deleteTask } = useTasks({
    entityType,
    entityId,
    autoFetch: false, // TasksSection will handle fetching
  });

  const handleCreateTask = useCallback(
    async (taskData: any) => {
      try {
        // Merge additional metadata into task_metadata if available
        const enrichedTaskData = { ...taskData };
        if (additionalMetadata && Object.keys(additionalMetadata).length > 0) {
          enrichedTaskData.task_metadata = {
            ...taskData.task_metadata,
            ...additionalMetadata,
          };
        }
        await createTask(enrichedTaskData);
        // Notify parent that counts have changed
        await onCountsChange?.();
      } catch (_error) {}
    },
    [createTask, onCountsChange, additionalMetadata]
  );

  const handleEditTask = useCallback((taskId: string) => {
    // Navigate to the task detail page
    window.open(`/tasks/${taskId}`, '_blank');
  }, []);

  const handleDeleteTask = useCallback(
    async (taskId: string) => {
      try {
        await deleteTask(taskId);
        // Notify parent that counts have changed
        await onCountsChange?.();
      } catch (_error) {}
    },
    [deleteTask, onCountsChange]
  );

  const handleCreateTaskFromComment = useCallback(
    (commentId: string) => {
      // Navigate to create task page with entity and comment info
      const params = new URLSearchParams({
        entityType,
        entityId,
        commentId,
      });
      // Add additional metadata as query params
      if (additionalMetadata) {
        Object.entries(additionalMetadata).forEach(([key, value]) => {
          params.append(key, String(value));
        });
      }
      const finalUrl = `/tasks/create?${params.toString()}`;
      router.push(finalUrl);
    },
    [router, entityType, entityId, additionalMetadata]
  );

  const handleCreateTaskFromEntity = useCallback(() => {
    // Navigate to create task page with entity info
    const params = new URLSearchParams({
      entityType,
      entityId,
    });
    // Add additional metadata as query params
    if (additionalMetadata) {
      Object.entries(additionalMetadata).forEach(([key, value]) => {
        params.append(key, String(value));
      });
    }
    const finalUrl = `/tasks/create?${params.toString()}`;
    router.push(finalUrl);
  }, [router, entityType, entityId, additionalMetadata]);

  return (
    <Paper elevation={elevation} sx={{ p: 3 }} suppressHydrationWarning>
      {/* Tasks Section */}
      <TasksSection
        entityType={entityType}
        entityId={entityId}
        sessionToken={sessionToken}
        onCreateTask={handleCreateTask}
        onEditTask={handleEditTask}
        onDeleteTask={handleDeleteTask}
        onNavigateToCreate={handleCreateTaskFromEntity}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
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
        onCountsChange={onCountsChange}
      />
    </Paper>
  );
}
