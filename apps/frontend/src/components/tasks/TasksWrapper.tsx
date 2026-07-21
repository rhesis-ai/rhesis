'use client';

import React, { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { EntityType } from '@/types/tasks';
import type { TaskCreate } from '@/utils/api-client/interfaces/task';
import { useTasks } from '@/hooks/useTasks';
import { taskKeys } from '@/constants/query-keys';
import { TasksSection } from './TasksSection';
import { TaskCreationDrawer } from './TaskCreationDrawer';

interface TasksWrapperProps {
  entityType: EntityType;
  entityId: string;
}

export function TasksWrapper({ entityType, entityId }: TasksWrapperProps) {
  const queryClient = useQueryClient();
  const [createDrawerOpen, setCreateDrawerOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const { createTask, deleteTask } = useTasks();

  const handleCreateTask = useCallback(
    async (taskData: Record<string, unknown>) => {
      try {
        setIsCreating(true);
        await createTask(taskData as unknown as TaskCreate);
        setCreateDrawerOpen(false);
        queryClient.invalidateQueries({ queryKey: taskKeys.all() });
      } catch {
        // Errors surfaced by useTasks
      } finally {
        setIsCreating(false);
      }
    },
    [createTask, queryClient]
  );

  const handleEditTask = useCallback((taskId: string) => {
    window.open(`/tasks/${taskId}`, '_blank');
  }, []);

  const handleDeleteTask = useCallback(
    async (taskId: string) => {
      try {
        await deleteTask(taskId);
        queryClient.invalidateQueries({ queryKey: taskKeys.all() });
      } catch {
        // Errors surfaced by useTasks
      }
    },
    [deleteTask, queryClient]
  );

  return (
    <>
      <TasksSection
        entityType={entityType}
        entityId={entityId}
        onCreateTask={handleCreateTask}
        onEditTask={handleEditTask}
        onDeleteTask={handleDeleteTask}
        onOpenCreateDrawer={() => setCreateDrawerOpen(true)}
      />

      <TaskCreationDrawer
        open={createDrawerOpen}
        onClose={() => {
          if (!isCreating) setCreateDrawerOpen(false);
        }}
        onSubmit={handleCreateTask}
        entityType={entityType}
        entityId={entityId}
        isLoading={isCreating}
      />
    </>
  );
}
