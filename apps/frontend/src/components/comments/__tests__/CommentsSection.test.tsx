import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { CommentsSection } from '../CommentsSection';

// Mock CommentItem and UserAvatar to keep tests focused on CommentsSection behavior
jest.mock('../CommentItem', () => ({
  CommentItem: ({
    comment,
    onEdit,
    onDelete,
    onReact,
  }: {
    comment: { id: string; content: string };
    onEdit: (id: string, t: string) => void;
    onDelete: (id: string) => void;
    onReact: (id: string, e: string) => void;
  }) => (
    <div data-testid={`comment-item-${comment.id}`}>
      <span>{comment.content}</span>
      <button onClick={() => onEdit(comment.id, 'edited')}>edit</button>
      <button onClick={() => onDelete(comment.id)}>delete</button>
      <button onClick={() => onReact(comment.id, '👍')}>react</button>
    </div>
  ),
}));

jest.mock('@/components/common/UserAvatar', () => ({
  UserAvatar: ({ userName }: { userName: string }) => (
    <div data-testid="user-avatar">{userName}</div>
  ),
}));

jest.mock('@/components/icons', () => ({
  SendIcon: () => <span data-testid="send-icon" />,
}));

// Suppress scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

function makeComment(id: string, content = 'Hello') {
  return {
    id,
    content,
    user_id: 'u1',
    user_name: 'Alice',
    created_at: '2024-01-01T00:00:00',
    updated_at: '2024-01-01T00:00:00',
    reactions: [],
  };
}

const DEFAULT_PROPS = {
  entityType: 'Test' as const,
  entityId: 'e1',
  comments: [],
  onCreateComment: jest.fn(),
  onEditComment: jest.fn(),
  onDeleteComment: jest.fn(),
  onReactToComment: jest.fn(),
  currentUserId: 'u1',
  currentUserName: 'Alice',
};

describe('CommentsSection', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    DEFAULT_PROPS.onCreateComment = jest.fn().mockResolvedValue(undefined);
    DEFAULT_PROPS.onEditComment = jest.fn().mockResolvedValue(undefined);
    DEFAULT_PROPS.onDeleteComment = jest.fn().mockResolvedValue(undefined);
    DEFAULT_PROPS.onReactToComment = jest.fn().mockResolvedValue(undefined);
  });

  it('shows a loading spinner when isLoading=true', () => {
    render(<CommentsSection {...DEFAULT_PROPS} isLoading={true} />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('does not show a spinner when not loading', () => {
    render(<CommentsSection {...DEFAULT_PROPS} />);
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('renders comment items for each comment', () => {
    render(
      <CommentsSection
        {...DEFAULT_PROPS}
        comments={[makeComment('c1', 'First'), makeComment('c2', 'Second')]}
      />
    );
    expect(screen.getByTestId('comment-item-c1')).toBeInTheDocument();
    expect(screen.getByTestId('comment-item-c2')).toBeInTheDocument();
  });

  it('shows the comment input placeholder', () => {
    render(<CommentsSection {...DEFAULT_PROPS} />);
    expect(screen.getByPlaceholderText(/add comment/i)).toBeInTheDocument();
  });

  it('calls onCreateComment with trimmed text on Enter key', async () => {
    const user = userEvent.setup();
    render(<CommentsSection {...DEFAULT_PROPS} />);

    const textarea = screen.getByPlaceholderText(/add comment/i);
    await user.type(textarea, 'Great work!');
    await user.keyboard('{Enter}');

    expect(DEFAULT_PROPS.onCreateComment).toHaveBeenCalledWith('Great work!');
  });

  it('clears the input after successful comment creation', async () => {
    const user = userEvent.setup();
    render(<CommentsSection {...DEFAULT_PROPS} />);

    const textarea = screen.getByPlaceholderText(/add comment/i);
    await user.type(textarea, 'A comment');
    await user.keyboard('{Enter}');

    await waitFor(() => expect(textarea).toHaveValue(''));
  });

  it('does not call onCreateComment when input is only whitespace', async () => {
    const user = userEvent.setup();
    render(<CommentsSection {...DEFAULT_PROPS} />);

    const textarea = screen.getByPlaceholderText(/add comment/i);
    await user.type(textarea, '   ');
    await user.keyboard('{Enter}');

    expect(DEFAULT_PROPS.onCreateComment).not.toHaveBeenCalled();
  });

  it('shows an error message when onCreateComment throws', async () => {
    DEFAULT_PROPS.onCreateComment = jest
      .fn()
      .mockRejectedValue(new Error('Server error'));
    const user = userEvent.setup();
    render(<CommentsSection {...DEFAULT_PROPS} />);

    const textarea = screen.getByPlaceholderText(/add comment/i);
    await user.type(textarea, 'Will fail');
    await user.keyboard('{Enter}');

    await waitFor(() =>
      expect(screen.getByText(/failed to post comment/i)).toBeInTheDocument()
    );
  });

  it('passes onEditComment down to CommentItem', async () => {
    const user = userEvent.setup();
    render(
      <CommentsSection {...DEFAULT_PROPS} comments={[makeComment('c1')]} />
    );

    await user.click(screen.getByRole('button', { name: 'edit' }));
    expect(DEFAULT_PROPS.onEditComment).toHaveBeenCalledWith('c1', 'edited');
  });

  it('passes onDeleteComment down to CommentItem', async () => {
    const user = userEvent.setup();
    render(
      <CommentsSection {...DEFAULT_PROPS} comments={[makeComment('c1')]} />
    );

    await user.click(screen.getByRole('button', { name: 'delete' }));
    expect(DEFAULT_PROPS.onDeleteComment).toHaveBeenCalledWith('c1');
  });

  it('sorts comments chronologically (oldest first)', () => {
    const comments = [
      { ...makeComment('c2'), created_at: '2024-01-02T00:00:00' },
      { ...makeComment('c1'), created_at: '2024-01-01T00:00:00' },
    ];
    render(<CommentsSection {...DEFAULT_PROPS} comments={comments} />);

    const items = screen.getAllByTestId(/comment-item/);
    expect(items[0]).toHaveAttribute('data-testid', 'comment-item-c1');
    expect(items[1]).toHaveAttribute('data-testid', 'comment-item-c2');
  });
});
