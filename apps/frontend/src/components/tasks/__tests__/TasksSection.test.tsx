/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
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
const mockShow = jest.fn();
const mockClose = jest.fn();
const mockNotifications = { show: mockShow, close: mockClose };
jest.mock('../../../components/common/NotificationContext', () => ({
  useNotifications: () => mockNotifications,
}));

const mockApiClientFactory = ApiClientFactory as jest.MockedClass<
  typeof ApiClientFactory
>;

function wrap(ui: React.ReactElement) {
  return render(<ThemeProvider theme={lightTheme}>{ui}</ThemeProvider>);
}

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

    const { rerender } = wrap(<TasksSection {...defaultProps} />);

    // Wait for initial fetch
    await waitFor(() => {
      expect(mockTasksClient.getTasks).toHaveBeenCalledTimes(1);
    });

    // Rerender multiple times with same props
    rerender(
      <ThemeProvider theme={lightTheme}>
        <TasksSection {...defaultProps} />
      </ThemeProvider>
    );
    rerender(
      <ThemeProvider theme={lightTheme}>
        <TasksSection {...defaultProps} />
      </ThemeProvider>
    );
    rerender(
      <ThemeProvider theme={lightTheme}>
        <TasksSection {...defaultProps} />
      </ThemeProvider>
    );

    // Should still only have one fetch - no infinite loop
    await waitFor(() => {
      expect(mockTasksClient.getTasks).toHaveBeenCalledTimes(1);
    });
  });

  it('should set loading to false when required props are missing', async () => {
    wrap(<TasksSection {...defaultProps} sessionToken="" />);

    // Should show empty state, not loading spinner
    await waitFor(() => {
      expect(screen.getByText(/no task created yet/i)).toBeInTheDocument();
    });

    // Should not have attempted to fetch
    expect(mockTasksClient.getTasks).not.toHaveBeenCalled();
  });

  it('should display empty state when no tasks', async () => {
    mockTasksClient.getTasks.mockResolvedValue({
      data: [],
      totalCount: 0,
    });

    wrap(<TasksSection {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText(/no task created yet/i)).toBeInTheDocument();
    });
  });

  it('should refetch when entity changes', async () => {
    mockTasksClient.getTasks.mockResolvedValue({
      data: [],
      totalCount: 0,
    });

    const { rerender } = wrap(<TasksSection {...defaultProps} />);

    await waitFor(() => {
      expect(mockTasksClient.getTasks).toHaveBeenCalledTimes(1);
    });

    // Change entity ID - should trigger new fetch
    rerender(
      <ThemeProvider theme={lightTheme}>
        <TasksSection {...defaultProps} entityId="test-456" />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(mockTasksClient.getTasks).toHaveBeenCalledTimes(2);
    });
  });
});
