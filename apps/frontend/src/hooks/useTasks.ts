import { useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  Task,
  TaskCreate,
  TaskUpdate,
} from '@/utils/api-client/interfaces/task';
import { useNotifications } from '@/components/common/NotificationContext';

/**
 * Task mutations (create/update/delete/get). No consumer reads a cached
 * task list from this hook — every call site invalidates its own
 * `taskKeys` query externally — so there's no list-fetching state here.
 */
export function useTasks() {
  const { data: session } = useSession();
  const { show } = useNotifications();

  const createMutation = useMutation({
    mutationFn: (taskData: TaskCreate) => {
      if (!session?.session_token) {
        throw new Error('No session token available');
      }
      return new ApiClientFactory(session.session_token)
        .getTasksClient()
        .createTask(taskData);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      taskId,
      taskData,
    }: {
      taskId: string;
      taskData: TaskUpdate;
    }) => {
      if (!session?.session_token) {
        throw new Error('No session token available');
      }
      return new ApiClientFactory(session.session_token)
        .getTasksClient()
        .updateTask(taskId, taskData);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (taskId: string) => {
      if (!session?.session_token) {
        throw new Error('No session token available');
      }
      return new ApiClientFactory(session.session_token)
        .getTasksClient()
        .deleteTask(taskId);
    },
  });

  const getMutation = useMutation({
    mutationFn: (taskId: string) => {
      if (!session?.session_token) {
        throw new Error('No session token available');
      }
      return new ApiClientFactory(session.session_token)
        .getTasksClient()
        .getTask(taskId);
    },
  });

  const createTask = useCallback(
    async (taskData: TaskCreate): Promise<Task | null> => {
      try {
        const newTask = await createMutation.mutateAsync(taskData);
        show('Task created successfully', { severity: 'success' });
        return newTask;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to create task';
        show(errorMessage, { severity: 'error' });
        return null;
      }
    },
    [createMutation, show]
  );

  const updateTask = useCallback(
    async (taskId: string, taskData: TaskUpdate): Promise<Task | null> => {
      try {
        const updatedTask = await updateMutation.mutateAsync({
          taskId,
          taskData,
        });
        show('Task updated successfully', { severity: 'success' });
        return updatedTask;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to update task';
        show(errorMessage, { severity: 'error' });
        return null;
      }
    },
    [updateMutation, show]
  );

  const deleteTask = useCallback(
    async (taskId: string): Promise<boolean> => {
      try {
        await deleteMutation.mutateAsync(taskId);
        show('Task deleted successfully', { severity: 'success' });
        return true;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to delete task';
        show(errorMessage, { severity: 'error' });
        return false;
      }
    },
    [deleteMutation, show]
  );

  const getTask = useCallback(
    async (taskId: string): Promise<Task | null> => {
      try {
        return await getMutation.mutateAsync(taskId);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to fetch task';
        show(errorMessage, { severity: 'error' });
        return null;
      }
    },
    [getMutation, show]
  );

  return {
    createTask,
    updateTask,
    deleteTask,
    getTask,
  };
}
