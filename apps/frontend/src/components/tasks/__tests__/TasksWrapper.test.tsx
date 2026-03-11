import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { TasksWrapper } from '../TasksWrapper';

const mockCreateTask = jest.fn();
const mockDeleteTask = jest.fn();

jest.mock('@/hooks/useTasks', () => ({
  useTasks: jest.fn(() => ({
    createTask: mockCreateTask,
    deleteTask: mockDeleteTask,
    tasks: [],
    isLoading: false,
    error: null,
    refetch: jest.fn(),
  })),
}));

// Capture callbacks passed to TasksSection for testing
let capturedOnCreate:
  | ((data: Record<string, unknown>) => Promise<void>)
  | null = null;
let capturedOnDelete: ((id: string) => Promise<void>) | null = null;

jest.mock('../TasksSection', () => ({
  TasksSection: ({
    onCreateTask,
    onDeleteTask,
  }: {
    onCreateTask: (data: Record<string, unknown>) => Promise<void>;
    onDeleteTask: (id: string) => Promise<void>;
  }) => {
    capturedOnCreate = onCreateTask;
    capturedOnDelete = onDeleteTask;
    return (
      <div data-testid="tasks-section">
        <button onClick={() => onCreateTask({ title: 'New Task' })}>
          create
        </button>
        <button onClick={() => onDeleteTask('task-1')}>delete</button>
      </div>
    );
  },
}));

jest.mock('../TaskCreationDrawer', () => ({
  TaskCreationDrawer: () => <div data-testid="task-creation-drawer" />,
}));

const DEFAULT_PROPS = {
  entityType: 'Test' as const,
  entityId: 'e1',
  sessionToken: 'tok',
  currentUserId: 'u1',
  currentUserName: 'Alice',
};

describe('TasksWrapper', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedOnCreate = null;
    capturedOnDelete = null;
  });

  it('renders TasksSection', () => {
    render(<TasksWrapper {...DEFAULT_PROPS} />);
    expect(screen.getByTestId('tasks-section')).toBeInTheDocument();
  });

  it('calls createTask when onCreateTask is triggered', async () => {
    const user = userEvent.setup();
    mockCreateTask.mockResolvedValue({ id: 'new-task' });

    render(<TasksWrapper {...DEFAULT_PROPS} />);
    await user.click(screen.getByRole('button', { name: 'create' }));

    expect(mockCreateTask).toHaveBeenCalledWith({ title: 'New Task' });
  });

  it('calls deleteTask when onDeleteTask is triggered', async () => {
    const user = userEvent.setup();
    mockDeleteTask.mockResolvedValue(undefined);

    render(<TasksWrapper {...DEFAULT_PROPS} />);
    await user.click(screen.getByRole('button', { name: 'delete' }));

    expect(mockDeleteTask).toHaveBeenCalledWith('task-1');
  });

  it('does not throw if createTask rejects', async () => {
    const user = userEvent.setup();
    mockCreateTask.mockRejectedValue(new Error('Server error'));

    render(<TasksWrapper {...DEFAULT_PROPS} />);
    await expect(
      user.click(screen.getByRole('button', { name: 'create' }))
    ).resolves.not.toThrow();
  });
});
