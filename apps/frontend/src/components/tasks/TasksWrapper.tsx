'use client';

import React, { useCallback, useState } from 'react';
import { EntityType } from '@/types/tasks';
import type { TaskCreate } from '@/utils/api-client/interfaces/task';
import { useTasks } from '@/hooks/useTasks';
import { TasksSection } from './TasksSection';
import { TaskCreationDrawer } from './TaskCreationDrawer';

interface TasksWrapperProps {
  entityType: EntityType;
  entityId: string;
  sessionToken: string;
}

export function TasksWrapper({
  entityType,
  entityId,
  sessionToken,
}: TasksWrapperProps) {
  const [createDrawerOpen, setCreateDrawerOpen] = useState(false);
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
        await createTask(taskData as unknown as TaskCreate);
        setCreateDrawerOpen(false);
        setTasksRefreshKey(key => key + 1);
      } catch {
        // Errors surfaced by useTasks
      } finally {
        setIsCreating(false);
      }
    },
    [createTask]
  );

  const handleEditTask = useCallback((taskId: string) => {
    window.open(`/tasks/${taskId}`, '_blank');
  }, []);

  const handleDeleteTask = useCallback(
    async (taskId: string) => {
      try {
        await deleteTask(taskId);
        setTasksRefreshKey(key => key + 1);
      } catch {
        // Errors surfaced by useTasks
      }
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
        onOpenCreateDrawer={() => setCreateDrawerOpen(true)}
        refreshKey={tasksRefreshKey}
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
