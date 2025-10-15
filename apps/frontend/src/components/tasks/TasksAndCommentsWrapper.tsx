'use client';

import React, { useCallback, useEffect } from 'react';
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
  
  // Log on mount/update to see if additionalMetadata is being passed
  useEffect(() => {
    console.log('[TasksAndCommentsWrapper] Component mounted/updated with:', {
      entityType,
      entityId,
      additionalMetadata,
    });
  }, [entityType, entityId, additionalMetadata]);
  
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
          console.log('[TasksAndCommentsWrapper] Enriching task with additional metadata:', additionalMetadata);
          enrichedTaskData.task_metadata = {
            ...taskData.task_metadata,
            ...additionalMetadata,
          };
        }
        console.log('[TasksAndCommentsWrapper] Creating task with data:', enrichedTaskData);
        await createTask(enrichedTaskData);
        // Notify parent that counts have changed
        onCountsChange?.();
      } catch (error) {
        console.error('Failed to create task:', error);
      }
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
        onCountsChange?.();
      } catch (error) {
        console.error('Failed to delete task:', error);
      }
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
        console.log('[TasksAndCommentsWrapper] Adding additional metadata to comment task URL:', additionalMetadata);
        Object.entries(additionalMetadata).forEach(([key, value]) => {
          params.append(key, String(value));
        });
      }
      const finalUrl = `/tasks/create?${params.toString()}`;
      console.log('[TasksAndCommentsWrapper] Navigating to create task from comment:', {
        entityType,
        entityId,
        commentId,
        additionalMetadata,
        finalUrl,
      });
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
      console.log('[TasksAndCommentsWrapper] Adding additional metadata to URL:', additionalMetadata);
      Object.entries(additionalMetadata).forEach(([key, value]) => {
        params.append(key, String(value));
      });
    }
    const finalUrl = `/tasks/create?${params.toString()}`;
    console.log('[TasksAndCommentsWrapper] Navigating to create task:', {
      entityType,
      entityId,
      additionalMetadata,
      finalUrl,
    });
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
