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

jest.mock('../TasksSection', () => ({
  TasksSection: () => <div data-testid="tasks-section" />,
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
