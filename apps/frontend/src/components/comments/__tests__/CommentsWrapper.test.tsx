import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import CommentsWrapper from '../CommentsWrapper';

// Mock CommentsSection so tests stay focused on CommentsWrapper's data-binding logic
jest.mock('../CommentsSection', () => ({
  CommentsSection: ({
    comments,
    isLoading,
    onCreateComment,
    onDeleteComment,
    onEditComment,
    onReactToComment,
  }: {
    comments: { id: string }[];
    isLoading?: boolean;
    onCreateComment: (t: string) => Promise<void>;
    onDeleteComment: (id: string) => Promise<void>;
    onEditComment: (id: string, t: string) => Promise<void>;
    onReactToComment: (id: string, e: string) => Promise<void>;
  }) => (
    <div data-testid="comments-section">
      <span data-testid="comment-count">{comments.length}</span>
      <span data-testid="loading">{isLoading ? 'loading' : 'idle'}</span>
      <button onClick={() => onCreateComment('hello')}>create</button>
      <button onClick={() => onDeleteComment('c1')}>delete</button>
      <button onClick={() => onEditComment('c1', 'updated')}>edit</button>
      <button onClick={() => onReactToComment('c1', '👍')}>react</button>
    </div>
  ),
}));

const mockCreateComment = jest.fn();
const mockEditComment = jest.fn();
const mockDeleteComment = jest.fn();
const mockReactToComment = jest.fn();

jest.mock('@/hooks/useComments', () => ({
  useComments: jest.fn(() => ({
    comments: [{ id: 'c1', content: 'Hello' }],
    isLoading: false,
    error: null,
    createComment: mockCreateComment,
    editComment: mockEditComment,
    deleteComment: mockDeleteComment,
    reactToComment: mockReactToComment,
    refetch: jest.fn(),
  })),
}));

import { useComments } from '@/hooks/useComments';
import userEvent from '@testing-library/user-event';

const DEFAULT_PROPS = {
  entityType: 'Test' as const,
  entityId: 'e1',
  sessionToken: 'tok',
  currentUserId: 'u1',
  currentUserName: 'Alice',
};

describe('CommentsWrapper', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useComments as jest.Mock).mockReturnValue({
      comments: [{ id: 'c1', content: 'Hello' }],
      isLoading: false,
      error: null,
      createComment: mockCreateComment,
      editComment: mockEditComment,
      deleteComment: mockDeleteComment,
      reactToComment: mockReactToComment,
      refetch: jest.fn(),
    });
  });

  it('renders CommentsSection', () => {
    render(<CommentsWrapper {...DEFAULT_PROPS} />);
    expect(screen.getByTestId('comments-section')).toBeInTheDocument();
  });

  it('passes comments from useComments to CommentsSection', () => {
    render(<CommentsWrapper {...DEFAULT_PROPS} />);
    expect(screen.getByTestId('comment-count')).toHaveTextContent('1');
  });

  it('passes isLoading=true to CommentsSection when loading', () => {
    (useComments as jest.Mock).mockReturnValue({
      comments: [],
      isLoading: true,
      error: null,
      createComment: mockCreateComment,
      editComment: mockEditComment,
      deleteComment: mockDeleteComment,
      reactToComment: mockReactToComment,
      refetch: jest.fn(),
    });
    render(<CommentsWrapper {...DEFAULT_PROPS} />);
    expect(screen.getByTestId('loading')).toHaveTextContent('loading');
  });

  it('calls createComment and onCountsChange when create button clicked', async () => {
    const user = userEvent.setup();
    const onCountsChange = jest.fn().mockResolvedValue(undefined);
    mockCreateComment.mockResolvedValue(undefined);

    render(
      <CommentsWrapper {...DEFAULT_PROPS} onCountsChange={onCountsChange} />
    );

    await user.click(screen.getByRole('button', { name: 'create' }));

    expect(mockCreateComment).toHaveBeenCalledWith('hello');
    expect(onCountsChange).toHaveBeenCalled();
  });

  it('calls deleteComment and onCountsChange when delete button clicked', async () => {
    const user = userEvent.setup();
    const onCountsChange = jest.fn().mockResolvedValue(undefined);
    mockDeleteComment.mockResolvedValue(undefined);

    render(
      <CommentsWrapper {...DEFAULT_PROPS} onCountsChange={onCountsChange} />
    );

    await user.click(screen.getByRole('button', { name: 'delete' }));

    expect(mockDeleteComment).toHaveBeenCalledWith('c1');
    expect(onCountsChange).toHaveBeenCalled();
  });

  it('calls editComment when edit button clicked', async () => {
    const user = userEvent.setup();
    mockEditComment.mockResolvedValue(undefined);

    render(<CommentsWrapper {...DEFAULT_PROPS} />);
    await user.click(screen.getByRole('button', { name: 'edit' }));

    expect(mockEditComment).toHaveBeenCalledWith('c1', 'updated');
  });

  it('calls reactToComment when react button clicked', async () => {
    const user = userEvent.setup();
    mockReactToComment.mockResolvedValue(undefined);

    render(<CommentsWrapper {...DEFAULT_PROPS} />);
    await user.click(screen.getByRole('button', { name: 'react' }));

    expect(mockReactToComment).toHaveBeenCalledWith('c1', '👍');
  });

  it('passes entityType and entityId to useComments', () => {
    render(
      <CommentsWrapper
        {...DEFAULT_PROPS}
        entityType="TestRun"
        entityId="run-123"
      />
    );

    expect(useComments).toHaveBeenCalledWith(
      expect.objectContaining({ entityType: 'TestRun', entityId: 'run-123' })
    );
  });
});
