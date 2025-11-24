/* eslint-disable @typescript-eslint/no-explicit-any */
import { renderHook, waitFor } from '@testing-library/react';
import { useComments } from '../useComments';
import { ApiClientFactory } from '../../utils/api-client/client-factory';

// Mock dependencies
jest.mock('../../utils/api-client/client-factory');
jest.mock('../../components/common/NotificationContext', () => ({
  useNotifications: () => ({
    show: jest.fn(),
  }),
}));

const mockApiClientFactory = ApiClientFactory as jest.MockedClass<
  typeof ApiClientFactory
>;

describe('useComments - Dependency Stability', () => {
  const mockCommentsClient = {
    getComments: jest.fn(),
  };

  const defaultProps = {
    entityType: 'Test' as const,
    entityId: '123',
    sessionToken: 'mock-token',
    currentUserId: 'user-1',
    currentUserName: 'Test User',
    currentUserPicture: 'http://example.com/pic.jpg',
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockApiClientFactory.mockImplementation(
      () =>
        (({
          getCommentsClient: () => mockCommentsClient
        }) as any)
    );
  });

  it('should not trigger infinite fetches when notifications change', async () => {
    mockCommentsClient.getComments.mockResolvedValue([]);

    const { rerender } = renderHook(() => useComments(defaultProps));

    await waitFor(() => {
      expect(mockCommentsClient.getComments).toHaveBeenCalledTimes(1);
    });

    // Simulate multiple re-renders (like when notifications change)
    for (let i = 0; i < 5; i++) {
      rerender();
    }

    // Should still only have fetched once - no infinite loop
    await waitFor(() => {
      expect(mockCommentsClient.getComments).toHaveBeenCalledTimes(1);
    });
  });
});
