import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import { TaskItem } from '../TaskItem';

jest.mock('@/components/icons', () => ({
  EditIcon: () => <span data-testid="edit-icon" />,
  DeleteIcon: () => <span data-testid="delete-icon" />,
  AssignmentIcon: () => <span data-testid="assignment-icon" />,
}));

jest.mock('@/components/common/UserAvatar', () => ({
  UserAvatar: ({ userName }: { userName: string }) => (
    <span data-testid="user-avatar">{userName}</span>
  ),
}));

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(() => ({ push: jest.fn() })),
}));

jest.mock('@/utils/entity-helpers', () => ({
  getEntityDisplayName: (t: string) => t,
}));

function makeTask(overrides = {}) {
  return {
    id: 'task-1',
    nano_id: 'T-001',
    title: 'Fix the bug',
    description: 'Something is broken',
    user_id: 'u1',
    assignee_id: 'u2',
    status: { name: 'Open' },
    priority: { type_value: 'High' },
    assignee: { name: 'Bob' },
    user: { name: 'Alice' },
    entity_type: 'Test',
    entity_id: 'e1',
    ...overrides,
  };
}

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider theme={lightTheme}>{ui}</ThemeProvider>);
}

describe('TaskItem', () => {
  it('renders the task title', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} currentUserId="u1" />);
    expect(screen.getByText('Fix the bug')).toBeInTheDocument();
  });

  it('renders the task description', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} currentUserId="u1" />);
    expect(screen.getByText('Something is broken')).toBeInTheDocument();
  });

  it('renders the status chip', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} currentUserId="u1" />);
    expect(screen.getByText('Open')).toBeInTheDocument();
  });

  it('renders the priority chip', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} currentUserId="u1" />);
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('shows edit icon for task owner', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} currentUserId="u1" />);
    expect(screen.getByTestId('edit-icon')).toBeInTheDocument();
  });

  it('shows delete icon for task owner', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} currentUserId="u1" />);
    expect(screen.getByTestId('delete-icon')).toBeInTheDocument();
  });

  it('does NOT show delete for non-owner, non-assignee', () => {
    renderWithTheme(
      <TaskItem task={makeTask() as never} currentUserId="other-user" />
    );
    expect(screen.queryByTestId('delete-icon')).not.toBeInTheDocument();
  });

  it('calls onEdit with task id when edit button is clicked', async () => {
    const user = userEvent.setup();
    const onEdit = jest.fn();

    renderWithTheme(
      <TaskItem task={makeTask() as never} currentUserId="u1" onEdit={onEdit} />
    );

    await user.click(screen.getByTestId('edit-icon').closest('button')!);
    expect(onEdit).toHaveBeenCalledWith('task-1');
  });

  it('calls onDelete with task id when delete button is clicked', async () => {
    const user = userEvent.setup();
    const onDelete = jest.fn();

    renderWithTheme(
      <TaskItem
        task={makeTask() as never}
        currentUserId="u1"
        onDelete={onDelete}
      />
    );

    await user.click(screen.getByTestId('delete-icon').closest('button')!);
    expect(onDelete).toHaveBeenCalledWith('task-1');
  });

  it('shows the entity link when showEntityLink=true', () => {
    renderWithTheme(
      <TaskItem
        task={makeTask() as never}
        currentUserId="u1"
        showEntityLink={true}
      />
    );
    expect(screen.getByText(/related to/i)).toBeInTheDocument();
  });

  it('does not show entity link when showEntityLink=false (default)', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} currentUserId="u1" />);
    expect(screen.queryByText(/related to/i)).not.toBeInTheDocument();
  });
});
