/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { TasksSection } from '../TasksSection';
import { ApiClientFactory } from '../../../utils/api-client/client-factory';

// Mock dependencies
jest.mock('../../../utils/api-client/client-factory');
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    refresh: jest.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));
jest.mock('../../../components/common/NotificationContext', () => ({
  useNotifications: () => ({
    show: jest.fn(),
    close: jest.fn(),
  }),
}));

const mockApiClientFactory = ApiClientFactory as jest.MockedClass<
  typeof ApiClientFactory
>;

describe('TasksSection - Infinite Loading Fix', () => {
  const mockTasksClient = {
    getTasks: jest.fn(),
  };

  const defaultProps = {
    entityType: 'Test' as const,
    entityId: 'test-123',
    sessionToken: 'mock-session-token',
    onCreateTask: jest.fn(),
    onEditTask: jest.fn(),
    onDeleteTask: jest.fn(),
    currentUserId: 'user-123',
    currentUserName: 'Test User',
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

  it('should not trigger infinite fetches when props are stable', async () => {
    mockTasksClient.getTasks.mockResolvedValue({
      data: [],
      totalCount: 0,
    });

    const { rerender } = render(<TasksSection {...defaultProps} />);

    // Wait for initial fetch
    await waitFor(() => {
      expect(mockTasksClient.getTasks).toHaveBeenCalledTimes(1);
    });

    // Rerender multiple times with same props
    rerender(<TasksSection {...defaultProps} />);
    rerender(<TasksSection {...defaultProps} />);
    rerender(<TasksSection {...defaultProps} />);

    // Should still only have one fetch - no infinite loop
    await waitFor(() => {
      expect(mockTasksClient.getTasks).toHaveBeenCalledTimes(1);
    });
  });

  it('should set loading to false when required props are missing', async () => {
    render(<TasksSection {...defaultProps} sessionToken="" />);

    // Should show empty state, not loading spinner
    await waitFor(() => {
      expect(screen.getByText(/no tasks yet/i)).toBeInTheDocument();
    });

    // Should not have attempted to fetch
    expect(mockTasksClient.getTasks).not.toHaveBeenCalled();
  });

  it('should display empty state when no tasks', async () => {
    mockTasksClient.getTasks.mockResolvedValue({
      data: [],
      totalCount: 0,
    });

    render(<TasksSection {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText(/no tasks yet/i)).toBeInTheDocument();
    });
  });

  it('should refetch when entity changes', async () => {
    mockTasksClient.getTasks.mockResolvedValue({
      data: [],
      totalCount: 0,
    });

    const { rerender } = render(<TasksSection {...defaultProps} />);

    await waitFor(() => {
      expect(mockTasksClient.getTasks).toHaveBeenCalledTimes(1);
    });

    // Change entity ID - should trigger new fetch
    rerender(<TasksSection {...defaultProps} entityId="test-456" />);

    await waitFor(() => {
      expect(mockTasksClient.getTasks).toHaveBeenCalledTimes(2);
    });
  });
});
