/* eslint-disable @typescript-eslint/no-explicit-any */
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useTasks } from '../useTasks';
import { ApiClientFactory } from '../../utils/api-client/client-factory';

// Mock dependencies
jest.mock('../../utils/api-client/client-factory');
jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: {
      session_token: 'mock-session-token',
      user: { id: 'user-1', name: 'John Doe', email: 'john@example.com' },
    },
    status: 'authenticated',
  }),
}));
const mockShow = jest.fn();
jest.mock('../../components/common/NotificationContext', () => ({
  useNotifications: () => ({
    show: mockShow,
  }),
}));

const mockApiClientFactory = ApiClientFactory as jest.MockedClass<
  typeof ApiClientFactory
>;

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return React.createElement(
    QueryClientProvider,
    { client: queryClient },
    children
  );
}

describe('useTasks', () => {
  const mockTasksClient = {
    createTask: jest.fn(),
    updateTask: jest.fn(),
    deleteTask: jest.fn(),
    getTask: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockApiClientFactory.mockImplementation(
      () =>
        ({
          getTasksClient: () => mockTasksClient,
        }) as any
    );
  });

  it('has all required methods', () => {
    const { result } = renderHook(() => useTasks(), { wrapper });

    expect(typeof result.current.createTask).toBe('function');
    expect(typeof result.current.updateTask).toBe('function');
    expect(typeof result.current.deleteTask).toBe('function');
    expect(typeof result.current.getTask).toBe('function');
  });

  it('creates a task and shows a success notification', async () => {
    const mockTask = { id: '1', title: 'Test Task' };
    mockTasksClient.createTask.mockResolvedValue(mockTask);

    const { result } = renderHook(() => useTasks(), { wrapper });

    let created;
    await act(async () => {
      created = await result.current.createTask({ title: 'Test Task' } as any);
    });

    expect(mockTasksClient.createTask).toHaveBeenCalledWith({
      title: 'Test Task',
    });
    expect(created).toEqual(mockTask);
    expect(mockShow).toHaveBeenCalledWith(
      'Task created successfully',
      expect.objectContaining({ severity: 'success' })
    );
  });

  it('returns null and shows an error notification when create fails', async () => {
    mockTasksClient.createTask.mockRejectedValue(new Error('boom'));

    const { result } = renderHook(() => useTasks(), { wrapper });

    let created;
    await act(async () => {
      created = await result.current.createTask({ title: 'x' } as any);
    });

    expect(created).toBeNull();
    expect(mockShow).toHaveBeenCalledWith(
      'boom',
      expect.objectContaining({ severity: 'error' })
    );
  });

  it('updates a task', async () => {
    const mockTask = { id: '1', title: 'Updated' };
    mockTasksClient.updateTask.mockResolvedValue(mockTask);

    const { result } = renderHook(() => useTasks(), { wrapper });

    let updated;
    await act(async () => {
      updated = await result.current.updateTask('1', {
        title: 'Updated',
      } as any);
    });

    expect(mockTasksClient.updateTask).toHaveBeenCalledWith('1', {
      title: 'Updated',
    });
    expect(updated).toEqual(mockTask);
  });

  it('deletes a task and returns true on success', async () => {
    mockTasksClient.deleteTask.mockResolvedValue(undefined);

    const { result } = renderHook(() => useTasks(), { wrapper });

    let deleted;
    await act(async () => {
      deleted = await result.current.deleteTask('1');
    });

    expect(mockTasksClient.deleteTask).toHaveBeenCalledWith('1');
    expect(deleted).toBe(true);
  });

  it('returns false when delete fails', async () => {
    mockTasksClient.deleteTask.mockRejectedValue(new Error('boom'));

    const { result } = renderHook(() => useTasks(), { wrapper });

    let deleted;
    await act(async () => {
      deleted = await result.current.deleteTask('1');
    });

    expect(deleted).toBe(false);
  });

  it('fetches a single task', async () => {
    const mockTask = { id: '1', title: 'Test Task' };
    mockTasksClient.getTask.mockResolvedValue(mockTask);

    const { result } = renderHook(() => useTasks(), { wrapper });

    let fetched;
    await act(async () => {
      fetched = await result.current.getTask('1');
    });

    expect(mockTasksClient.getTask).toHaveBeenCalledWith('1');
    expect(fetched).toEqual(mockTask);
  });
});
