import { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  Task,
  TaskCreate,
  TaskUpdate,
  TasksQueryParams,
} from '@/utils/api-client/interfaces/task';
import { useNotifications } from '@/components/common/NotificationContext';

interface UseTasksOptions {
  entityType?: string;
  entityId?: string;
  autoFetch?: boolean;
}

export function useTasks(options: UseTasksOptions = {}) {
  const { entityType, entityId, autoFetch = true } = options;
  const { data: session, status } = useSession();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { show } = useNotifications();

  const fetchTasks = useCallback(
    async (params: TasksQueryParams = {}) => {
      if (status === 'loading') {
        return; // Wait for session to load
      }

      if (!session?.session_token) {
        setError('No session token available');
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const clientFactory = new ApiClientFactory(session.session_token);
        const tasksClient = clientFactory.getTasksClient();

        let fetchedTasks: Task[];
        if (entityType && entityId) {
          const response = await tasksClient.getTasksByEntity(
            entityType,
            entityId,
            params
          );
          fetchedTasks = response.data;
        } else {
          const response = await tasksClient.getTasks(params);
          fetchedTasks = response.data;
        }

        setTasks(fetchedTasks);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to fetch tasks';
        setError(errorMessage);
        show(errorMessage, { severity: 'error' });
      } finally {
        setIsLoading(false);
      }
    },
    [entityType, entityId, session?.session_token, status]
  );

  const createTask = useCallback(
    async (taskData: TaskCreate): Promise<Task | null> => {
      if (!session?.session_token) {
        setError('No session token available');
        return null;
      }

      try {
        const clientFactory = new ApiClientFactory(session.session_token);
        const tasksClient = clientFactory.getTasksClient();

        const newTask = await tasksClient.createTask(taskData);

        // Add the new task to the current list
        setTasks(prev => [newTask, ...prev]);

        show('Task created successfully', { severity: 'success' });
        return newTask;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to create task';
        setError(errorMessage);
        show(errorMessage, { severity: 'error' });
        return null;
      }
    },
    [session?.session_token]
  );

  const updateTask = useCallback(
    async (taskId: string, taskData: TaskUpdate): Promise<Task | null> => {
      if (!session?.session_token) {
        setError('No session token available');
        return null;
      }

      try {
        const clientFactory = new ApiClientFactory(session.session_token);
        const tasksClient = clientFactory.getTasksClient();

        const updatedTask = await tasksClient.updateTask(taskId, taskData);

        // Update the task in the current list
        setTasks(prev =>
          prev.map(task => (task.id === taskId ? updatedTask : task))
        );

        show('Task updated successfully', { severity: 'success' });
        return updatedTask;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to update task';
        setError(errorMessage);
        show(errorMessage, { severity: 'error' });
        return null;
      }
    },
    [session?.session_token]
  );

  const deleteTask = useCallback(
    async (taskId: string): Promise<boolean> => {
      if (!session?.session_token) {
        setError('No session token available');
        return false;
      }

      try {
        const clientFactory = new ApiClientFactory(session.session_token);
        const tasksClient = clientFactory.getTasksClient();

        await tasksClient.deleteTask(taskId);

        // Remove the task from the current list
        setTasks(prev => prev.filter(task => task.id !== taskId));

        show('Task deleted successfully', { severity: 'success' });
        return true;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to delete task';
        setError(errorMessage);
        show(errorMessage, { severity: 'error' });
        return false;
      }
    },
    [session?.session_token]
  );

  const getTask = useCallback(
    async (taskId: string): Promise<Task | null> => {
      if (!session?.session_token) {
        setError('No session token available');
        return null;
      }

      try {
        const clientFactory = new ApiClientFactory(session.session_token);
        const tasksClient = clientFactory.getTasksClient();

        return await tasksClient.getTask(taskId);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to fetch task';
        setError(errorMessage);
        show(errorMessage, { severity: 'error' });
        return null;
      }
    },
    [session?.session_token]
  );

  const fetchTasksByCommentId = useCallback(
    async (
      commentId: string,
      params: TasksQueryParams = {}
    ): Promise<Task[]> => {
      if (status === 'loading') {
        return []; // Wait for session to load
      }

      if (!session?.session_token) {
        setError('No session token available');
        return [];
      }

      try {
        const clientFactory = new ApiClientFactory(session.session_token);
        const tasksClient = clientFactory.getTasksClient();

        const fetchedTasks = await tasksClient.getTasksByCommentId(
          commentId,
          params
        );
        return fetchedTasks;
      } catch (err) {
        return [];
      }
    },
    [session?.session_token, status]
  );

  // Auto-fetch tasks when component mounts or dependencies change
  useEffect(() => {
    if (autoFetch) {
      fetchTasks();
    }
  }, [autoFetch, fetchTasks]);

  return {
    tasks,
    isLoading,
    error,
    fetchTasks,
    createTask,
    updateTask,
    deleteTask,
    getTask,
    fetchTasksByCommentId,
  };
}
