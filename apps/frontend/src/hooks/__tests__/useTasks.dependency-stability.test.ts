/* eslint-disable @typescript-eslint/no-explicit-any */
import { renderHook, waitFor } from '@testing-library/react';
import { useTasks } from '../useTasks';
import { ApiClientFactory } from '../../utils/api-client/client-factory';

// Mock dependencies
jest.mock('../../utils/api-client/client-factory');
jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: {
      session_token: 'mock-token',
      user: { id: 'user-1', name: 'Test User' },
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

describe('useTasks - Dependency Stability', () => {
  const mockTasksClient = {
    getTasksByEntity: jest.fn(),
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

  it('should not trigger infinite fetches when notifications change', async () => {
    mockTasksClient.getTasksByEntity.mockResolvedValue({
      data: [],
      total: 0,
    });

    const { rerender } = renderHook(() =>
      useTasks({
        entityType: 'Test',
        entityId: '123',
        autoFetch: true,
      })
    );

    await waitFor(() => {
      expect(mockTasksClient.getTasksByEntity).toHaveBeenCalledTimes(1);
    });

    // Simulate multiple re-renders (like when notifications change)
    for (let i = 0; i < 5; i++) {
      rerender();
    }

    // Should still only have fetched once - no infinite loop
    await waitFor(() => {
      expect(mockTasksClient.getTasksByEntity).toHaveBeenCalledTimes(1);
    });
  });
});
