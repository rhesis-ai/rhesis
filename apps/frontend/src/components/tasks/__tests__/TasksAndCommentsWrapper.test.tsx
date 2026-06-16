import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { TasksAndCommentsWrapper } from '../TasksAndCommentsWrapper';

const mockCreateTask = jest.fn();
const mockDeleteTask = jest.fn();

jest.mock('@/hooks/useTasks', () => ({
  useTasks: jest.fn(() => ({
    createTask: mockCreateTask,
    deleteTask: mockDeleteTask,
    tasks: [],
    isLoading: false,
  })),
}));

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(() => ({ push: jest.fn() })),
}));

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(() => ({
    data: { session_token: 'tok', user: { id: 'u1', name: 'Alice' } },
    status: 'authenticated',
  })),
}));

jest.mock('../TaskCreationDrawer', () => ({
  TaskCreationDrawer: () => null,
}));

jest.mock('../TasksSection', () => ({
  TasksSection: ({
    onCreateTask,
    onDeleteTask,
    refreshKey,
  }: {
    onCreateTask: (data: Record<string, unknown>) => Promise<void>;
    onDeleteTask: (id: string) => Promise<void>;
    refreshKey?: number;
  }) => (
    <div data-testid="tasks-section" data-refresh-key={refreshKey ?? 0}>
      <button type="button" onClick={() => onCreateTask({ title: 'New Task' })}>
        create
      </button>
      <button type="button" onClick={() => onDeleteTask('task-1')}>
        delete
      </button>
    </div>
  ),
}));

jest.mock('../TaskCreationDrawer', () => ({
  TaskCreationDrawer: () => null,
}));

jest.mock('@/components/comments/CommentsWrapper', () => ({
  __esModule: true,
  default: ({ onCountsChange }: { onCountsChange?: () => void }) => (
    <div data-testid="comments-wrapper">
      <button onClick={onCountsChange}>trigger-counts-change</button>
    </div>
  ),
}));

const DEFAULT_PROPS = {
  entityType: 'Test' as const,
  entityId: 'e1',
  sessionToken: 'tok',
  currentUserId: 'u1',
  currentUserName: 'Alice',
};

describe('TasksAndCommentsWrapper', () => {
  beforeEach(() => jest.clearAllMocks());

  it('renders both TasksSection and CommentsWrapper', () => {
    render(<TasksAndCommentsWrapper {...DEFAULT_PROPS} />);
    expect(screen.getByTestId('tasks-section')).toBeInTheDocument();
    expect(screen.getByTestId('comments-wrapper')).toBeInTheDocument();
  });

  it('bumps TasksSection refreshKey after creating a task', async () => {
    const user = userEvent.setup();
    mockCreateTask.mockResolvedValue({ id: 'task-1' });

    render(<TasksAndCommentsWrapper {...DEFAULT_PROPS} />);
    expect(screen.getByTestId('tasks-section')).toHaveAttribute(
      'data-refresh-key',
      '0'
    );

    await user.click(screen.getByRole('button', { name: 'create' }));

    expect(mockCreateTask).toHaveBeenCalledWith({ title: 'New Task' });
    expect(screen.getByTestId('tasks-section')).toHaveAttribute(
      'data-refresh-key',
      '1'
    );
  });

  it('bumps TasksSection refreshKey after deleting a task', async () => {
    const user = userEvent.setup();
    mockDeleteTask.mockResolvedValue(true);

    render(<TasksAndCommentsWrapper {...DEFAULT_PROPS} />);
    await user.click(screen.getByRole('button', { name: 'delete' }));

    expect(mockDeleteTask).toHaveBeenCalledWith('task-1');
    expect(screen.getByTestId('tasks-section')).toHaveAttribute(
      'data-refresh-key',
      '1'
    );
  });

  it('calls parent onCountsChange when CommentsWrapper triggers it', async () => {
    const user = userEvent.setup();
    const onCountsChange = jest.fn();

    render(
      <TasksAndCommentsWrapper
        {...DEFAULT_PROPS}
        onCountsChange={onCountsChange}
      />
    );

    await user.click(
      screen.getByRole('button', { name: 'trigger-counts-change' })
    );

    expect(onCountsChange).toHaveBeenCalled();
  });
});
