import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import { TaskItem } from '../TaskItem';
import { EntityType } from '@/types/entity-type';

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

function makeTask(permitted_actions: string[] = [], overrides = {}) {
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
    entity_type: EntityType.TEST,
    entity_id: 'e1',
    permitted_actions,
    ...overrides,
  };
}

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider theme={lightTheme}>{ui}</ThemeProvider>);
}

function getIconButton(testId: string) {
  const button = screen.getByTestId(testId).closest('button');
  if (!button) {
    throw new Error(`Expected ${testId} to be inside a button`);
  }
  return button;
}

describe('TaskItem', () => {
  it('renders the task title', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} />);
    expect(screen.getByText('Fix the bug')).toBeInTheDocument();
  });

  it('renders the task description', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} />);
    expect(screen.getByText('Something is broken')).toBeInTheDocument();
  });

  it('renders the status chip', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} />);
    expect(screen.getByText('Open')).toBeInTheDocument();
  });

  it('renders the priority chip', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} />);
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('shows edit icon when task:update is in permitted_actions', () => {
    renderWithTheme(
      <TaskItem task={makeTask(['task:update', 'task:delete']) as never} />
    );
    expect(screen.getByTestId('edit-icon')).toBeInTheDocument();
  });

  it('shows delete icon when task:delete is in permitted_actions', () => {
    renderWithTheme(
      <TaskItem task={makeTask(['task:update', 'task:delete']) as never} />
    );
    expect(screen.getByTestId('delete-icon')).toBeInTheDocument();
  });

  it('hides edit icon when task:update is not in permitted_actions', () => {
    renderWithTheme(<TaskItem task={makeTask(['task:delete']) as never} />);
    expect(screen.queryByTestId('edit-icon')).not.toBeInTheDocument();
  });

  it('hides delete icon when task:delete is not in permitted_actions', () => {
    renderWithTheme(<TaskItem task={makeTask(['task:update']) as never} />);
    expect(screen.queryByTestId('delete-icon')).not.toBeInTheDocument();
  });

  it('hides both actions when permitted_actions is empty', () => {
    renderWithTheme(<TaskItem task={makeTask([]) as never} />);
    expect(screen.queryByTestId('edit-icon')).not.toBeInTheDocument();
    expect(screen.queryByTestId('delete-icon')).not.toBeInTheDocument();
  });

  it('calls onEdit with task id when edit button is clicked', async () => {
    const user = userEvent.setup();
    const onEdit = jest.fn();

    renderWithTheme(
      <TaskItem
        task={makeTask(['task:update', 'task:delete']) as never}
        onEdit={onEdit}
      />
    );

    await user.click(getIconButton('edit-icon'));
    expect(onEdit).toHaveBeenCalledWith('task-1');
  });

  it('calls onDelete with task id when delete button is clicked', async () => {
    const user = userEvent.setup();
    const onDelete = jest.fn();

    renderWithTheme(
      <TaskItem
        task={makeTask(['task:update', 'task:delete']) as never}
        onDelete={onDelete}
      />
    );

    await user.click(getIconButton('delete-icon'));
    expect(onDelete).toHaveBeenCalledWith('task-1');
  });

  it('shows the entity link when showEntityLink=true', () => {
    renderWithTheme(
      <TaskItem task={makeTask() as never} showEntityLink={true} />
    );
    expect(screen.getByText(/related to/i)).toBeInTheDocument();
  });

  it('does not show entity link when showEntityLink=false (default)', () => {
    renderWithTheme(<TaskItem task={makeTask() as never} />);
    expect(screen.queryByText(/related to/i)).not.toBeInTheDocument();
  });
});
