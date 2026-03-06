import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import { CommentItem } from '../CommentItem';

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider theme={lightTheme}>{ui}</ThemeProvider>);
}

// Heavy dependencies mocked for isolation
jest.mock('emoji-picker-react', () => ({
  __esModule: true,
  default: ({
    onEmojiClick,
  }: {
    onEmojiClick: (e: { emoji: string }) => void;
  }) => (
    <div data-testid="emoji-picker">
      <button onClick={() => onEmojiClick({ emoji: '😊' })}>pick emoji</button>
    </div>
  ),
}));

jest.mock('@/hooks/useTasks', () => ({
  useTasks: () => ({
    fetchTasksByCommentId: jest.fn().mockResolvedValue([]),
  }),
}));

jest.mock('@/components/common/DeleteModal', () => ({
  DeleteModal: ({
    open,
    onConfirm,
    onClose,
  }: {
    open: boolean;
    onConfirm: () => void;
    onClose: () => void;
  }) =>
    open ? (
      <div data-testid="delete-modal">
        <button onClick={onConfirm}>confirm-delete</button>
        <button onClick={onClose}>cancel-delete</button>
      </div>
    ) : null,
}));

jest.mock('@/components/common/UserAvatar', () => ({
  UserAvatar: ({ userName }: { userName: string }) => (
    <span data-testid="user-avatar">{userName}</span>
  ),
}));

jest.mock('@/utils/comment-utils', () => ({
  createReactionTooltipText: jest.fn(() => 'Reaction tooltip'),
}));

jest.mock('@/components/icons', () => ({
  EditIcon: () => <span data-testid="edit-icon" />,
  DeleteIcon: () => <span data-testid="delete-icon" />,
  EmojiIcon: () => <span data-testid="emoji-icon" />,
  AssignmentIcon: () => <span data-testid="assignment-icon" />,
  AddTaskIcon: () => <span data-testid="add-task-icon" />,
}));

function makeComment(
  overrides: Partial<{
    id: string;
    content: string;
    user_id: string;
    user_name: string;
    created_at: string;
    reactions: unknown[];
  }> = {}
) {
  return {
    id: 'c1',
    content: 'Hello world',
    user_id: 'u1',
    user_name: 'Alice',
    created_at: '2024-01-01T12:00:00',
    updated_at: '2024-01-01T12:00:00',
    reactions: [],
    ...overrides,
  };
}

describe('CommentItem', () => {
  const baseProps = {
    comment: makeComment(),
    onEdit: jest.fn().mockResolvedValue(undefined),
    onDelete: jest.fn().mockResolvedValue(undefined),
    onReact: jest.fn().mockResolvedValue(undefined),
    currentUserId: 'u1',
  };

  beforeEach(() => {
    jest.clearAllMocks();
    baseProps.onEdit = jest.fn().mockResolvedValue(undefined);
    baseProps.onDelete = jest.fn().mockResolvedValue(undefined);
    baseProps.onReact = jest.fn().mockResolvedValue(undefined);
  });

  it('renders the comment content', () => {
    renderWithTheme(<CommentItem {...baseProps} />);
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });

  it('shows edit and delete buttons when the current user owns the comment', () => {
    renderWithTheme(<CommentItem {...baseProps} />);
    expect(screen.getByTestId('edit-icon')).toBeInTheDocument();
    expect(screen.getByTestId('delete-icon')).toBeInTheDocument();
  });

  it('does not show edit/delete buttons for comments owned by another user', () => {
    renderWithTheme(
      <CommentItem
        {...baseProps}
        comment={makeComment({ user_id: 'other-user' })}
        currentUserId="u1"
      />
    );
    expect(screen.queryByTestId('edit-icon')).not.toBeInTheDocument();
    expect(screen.queryByTestId('delete-icon')).not.toBeInTheDocument();
  });

  it('enters edit mode when the edit button is clicked', async () => {
    const user = userEvent.setup();
    renderWithTheme(<CommentItem {...baseProps} />);

    await user.click(screen.getByTestId('edit-icon').closest('button')!);

    // Edit mode shows a textfield with the comment's content
    expect(screen.getByDisplayValue('Hello world')).toBeInTheDocument();
  });

  it('cancels editing without calling onEdit when Escape is pressed', async () => {
    const user = userEvent.setup();
    renderWithTheme(<CommentItem {...baseProps} />);

    await user.click(screen.getByTestId('edit-icon').closest('button')!);
    await user.keyboard('{Escape}');

    expect(screen.getByText('Hello world')).toBeInTheDocument();
    expect(baseProps.onEdit).not.toHaveBeenCalled();
  });

  it('shows the delete confirmation modal when delete icon is clicked', async () => {
    const user = userEvent.setup();
    renderWithTheme(<CommentItem {...baseProps} />);

    await user.click(screen.getByTestId('delete-icon').closest('button')!);

    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
  });

  it('calls onDelete with the comment id when deletion is confirmed', async () => {
    const user = userEvent.setup();
    renderWithTheme(<CommentItem {...baseProps} />);

    await user.click(screen.getByTestId('delete-icon').closest('button')!);
    await user.click(screen.getByRole('button', { name: 'confirm-delete' }));

    await waitFor(() => expect(baseProps.onDelete).toHaveBeenCalledWith('c1'));
  });

  it('cancels deletion when the cancel button is clicked', async () => {
    const user = userEvent.setup();
    renderWithTheme(<CommentItem {...baseProps} />);

    await user.click(screen.getByTestId('delete-icon').closest('button')!);
    await user.click(screen.getByRole('button', { name: 'cancel-delete' }));

    expect(baseProps.onDelete).not.toHaveBeenCalled();
    expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument();
  });
});
