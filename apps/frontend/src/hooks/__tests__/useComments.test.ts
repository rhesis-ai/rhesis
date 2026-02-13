/* eslint-disable @typescript-eslint/no-explicit-any */
import { renderHook, waitFor } from '@testing-library/react';
import { useComments } from '../useComments';
import { ApiClientFactory } from '../../utils/api-client/client-factory';

// Mock dependencies
jest.mock('../../utils/api-client/client-factory');
const mockShow = jest.fn();
const mockNotifications = { show: mockShow };
jest.mock('../../components/common/NotificationContext', () => ({
  useNotifications: () => mockNotifications,
}));

const mockApiClientFactory = ApiClientFactory as jest.MockedClass<
  typeof ApiClientFactory
>;

describe('useComments', () => {
  const mockProps = {
    entityType: 'Test',
    entityId: '123',
    sessionToken: 'mock-session-token',
    currentUserId: 'user-1',
    currentUserName: 'John Doe',
    currentUserPicture: 'https://example.com/avatar.jpg',
  };

  const mockCommentsClient = {
    getComments: jest.fn(),
    createComment: jest.fn(),
    updateComment: jest.fn(),
    deleteComment: jest.fn(),
    addEmojiReaction: jest.fn(),
    removeEmojiReaction: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockApiClientFactory.mockImplementation(
      () =>
        ({
          getCommentsClient: () => mockCommentsClient,
        }) as any
    );
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('initialization', () => {
    it('starts with initial state', () => {
      const { result } = renderHook(() => useComments(mockProps));

      expect(result.current.comments).toEqual([]);
      expect(result.current.isLoading).toBe(true);
      expect(result.current.error).toBe(null);
    });

    it('fetches comments on mount', async () => {
      const mockComments = [
        {
          id: '1',
          content: 'Test comment',
          entity_type: 'Test',
          entity_id: '123',
          parent_id: null,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          user: {
            id: 'user-1',
            name: 'John Doe',
            email: 'john@example.com',
          },
        },
      ];

      mockCommentsClient.getComments.mockResolvedValue(mockComments);

      const { result } = renderHook(() => useComments(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockCommentsClient.getComments).toHaveBeenCalledWith(
        'Test',
        '123'
      );
      expect(result.current.comments).toEqual(mockComments);
      expect(result.current.error).toBe(null);
    });
  });

  describe('fetchComments', () => {
    it('handles successful comment fetch', async () => {
      const mockComments = [
        {
          id: '1',
          content: 'Test comment',
          entity_type: 'Test',
          entity_id: '123',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          user: {
            id: 'user-1',
            name: 'John Doe',
            email: 'john@example.com',
          },
        },
      ];

      mockCommentsClient.getComments.mockResolvedValue(mockComments);

      const { result } = renderHook(() => useComments(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.comments).toEqual(mockComments);
      expect(result.current.error).toBe(null);
    });

    it('handles fetch error', async () => {
      const error = new Error('Failed to fetch');
      mockCommentsClient.getComments.mockRejectedValue(error);

      const { result } = renderHook(() => useComments(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Failed to fetch comments');
      expect(result.current.comments).toEqual([]);
    });

    it('handles missing session token', async () => {
      const { result } = renderHook(() =>
        useComments({ ...mockProps, sessionToken: '' })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('No session token available');
      expect(mockCommentsClient.getComments).not.toHaveBeenCalled();
    });
  });

  describe('createComment', () => {
    it('creates a new comment successfully', async () => {
      const newComment = {
        id: 'new-comment-id',
        content: 'New comment',
        entity_type: 'Test' as const,
        entity_id: '123',
        parent_id: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        user: {
          id: 'user-1',
          name: 'John Doe',
          email: 'john@example.com',
        },
      };

      mockCommentsClient.createComment.mockResolvedValue(newComment);

      const { result } = renderHook(() => useComments(mockProps));

      let createCommentResult: any;
      await waitFor(async () => {
        createCommentResult = await result.current.createComment('New comment');
      });

      expect(mockCommentsClient.createComment).toHaveBeenCalledWith({
        content: 'New comment',
        entity_type: 'Test',
        entity_id: '123',
      });

      expect(createCommentResult.user).toEqual({
        id: 'user-1',
        name: 'John Doe',
        email: '',
        picture: 'https://example.com/avatar.jpg',
      });
    });

    it('handles create comment error', async () => {
      const error = new Error('Failed to create');
      mockCommentsClient.createComment.mockRejectedValue(error);

      const { result } = renderHook(() => useComments(mockProps));

      await expect(result.current.createComment('New comment')).rejects.toThrow(
        'Failed to create'
      );
    });

    it('handles missing session token for create', async () => {
      const { result } = renderHook(() =>
        useComments({ ...mockProps, sessionToken: '' })
      );

      await expect(result.current.createComment('New comment')).rejects.toThrow(
        'No session token available'
      );
    });
  });

  describe('editComment', () => {
    it('edits a comment successfully', async () => {
      const existingComment = {
        id: '1',
        content: 'Original comment',
        entity_type: 'Test',
        entity_id: '123',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        user: {
          id: 'user-1',
          name: 'John Doe',
          email: 'john@example.com',
        },
      };

      const updatedComment = {
        id: '1',
        content: 'Updated comment',
        entity_type: 'Test',
        entity_id: '123',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
        user: {
          id: 'user-1',
          name: 'John Doe',
          email: 'john@example.com',
        },
      };

      // Set up initial state with existing comment
      mockCommentsClient.getComments.mockResolvedValue([existingComment]);

      const { result } = renderHook(() => useComments(mockProps));

      await waitFor(() => {
        expect(result.current.comments.length).toBe(1);
      });

      mockCommentsClient.updateComment.mockResolvedValue(updatedComment);

      let editResult: any;
      await waitFor(async () => {
        editResult = await result.current.editComment('1', 'Updated comment');
      });

      expect(mockCommentsClient.updateComment).toHaveBeenCalledWith('1', {
        content: 'Updated comment',
      });

      expect(editResult.content).toBe('Updated comment');
      expect(editResult.user).toEqual(existingComment.user);
    });

    it('handles edit comment error', async () => {
      mockCommentsClient.getComments.mockResolvedValue([]);

      const { result } = renderHook(() => useComments(mockProps));

      await waitFor(() => {
        expect(result.current.comments.length).toBe(0);
      });

      const error = new Error('Failed to edit');
      mockCommentsClient.updateComment.mockRejectedValue(error);

      await expect(
        result.current.editComment('1', 'Updated comment')
      ).rejects.toThrow('Failed to edit');
    });
  });

  describe('deleteComment', () => {
    it('deletes a comment successfully', async () => {
      const commentToDelete = {
        id: '1',
        content: 'Comment to delete',
        entity_type: 'Test',
        entity_id: '123',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        user: {
          id: 'user-1',
          name: 'John Doe',
          email: 'john@example.com',
        },
      };

      mockCommentsClient.getComments.mockResolvedValue([commentToDelete]);
      mockCommentsClient.deleteComment.mockResolvedValue(commentToDelete);

      // Set up initial state with comment
      const { result } = renderHook(() => useComments(mockProps));

      await waitFor(() => {
        expect(result.current.comments).toHaveLength(1);
      });

      await waitFor(async () => {
        await result.current.deleteComment('1');
      });

      expect(mockCommentsClient.deleteComment).toHaveBeenCalledWith('1');

      await waitFor(() => {
        expect(result.current.comments).toHaveLength(0);
      });
    });

    it('handles delete error', async () => {
      mockCommentsClient.getComments.mockResolvedValue([]);

      const { result } = renderHook(() => useComments(mockProps));

      await waitFor(() => {
        expect(result.current.comments).toHaveLength(0);
      });

      const error = new Error('Failed to delete');
      mockCommentsClient.deleteComment.mockRejectedValue(error);

      await expect(result.current.deleteComment('1')).rejects.toThrow(
        'Failed to delete'
      );
    });
  });

  describe('reactToComment', () => {
    it('adds emoji reaction when user has not reacted', async () => {
      const commentWithEmojis = {
        id: '1',
        content: 'Test comment',
        entity_type: 'Test',
        entity_id: '123',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        user: {
          id: 'user-1',
          name: 'John Doe',
          email: 'john@example.com',
        },
        emojis: {},
      };

      const updatedComment = {
        ...commentWithEmojis,
        emojis: {
          '👍': [{ user_id: 'user-1', created_at: '2024-01-01T00:00:00Z' }],
        },
      };

      mockCommentsClient.getComments.mockResolvedValue([commentWithEmojis]);

      const { result } = renderHook(() => useComments(mockProps));

      await waitFor(() => {
        expect(result.current.comments).toHaveLength(1);
      });

      mockCommentsClient.addEmojiReaction.mockResolvedValue(updatedComment);

      await waitFor(async () => {
        await result.current.reactToComment('1', '👍');
      });

      expect(mockCommentsClient.addEmojiReaction).toHaveBeenCalledWith(
        '1',
        '👍'
      );
    });

    it('removes emoji reaction when user has already reacted', async () => {
      const commentWithEmojis = {
        id: '1',
        content: 'Test comment',
        entity_type: 'Test',
        entity_id: '123',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        user: {
          id: 'user-1',
          name: 'John Doe',
          email: 'john@example.com',
        },
        emojis: {
          '👍': [{ user_id: 'user-1', created_at: '2024-01-01T00:00:00Z' }],
        },
      };

      const updatedComment = {
        ...commentWithEmojis,
        emojis: {},
      };

      mockCommentsClient.getComments.mockResolvedValue([commentWithEmojis]);

      const { result } = renderHook(() => useComments(mockProps));

      await waitFor(() => {
        expect(result.current.comments).toHaveLength(1);
      });

      mockCommentsClient.removeEmojiReaction.mockResolvedValue(updatedComment);

      await waitFor(async () => {
        await result.current.reactToComment('1', '👍');
      });

      expect(mockCommentsClient.removeEmojiReaction).toHaveBeenCalledWith(
        '1',
        '👍'
      );
    });
  });

  describe('refetch', () => {
    it('refetches comments when refetch is called', async () => {
      mockCommentsClient.getComments.mockResolvedValue([]);

      const { result } = renderHook(() => useComments(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Clear previous calls
      mockCommentsClient.getComments.mockClear();

      // Call refetch
      await waitFor(async () => {
        await result.current.refetch();
      });

      expect(mockCommentsClient.getComments).toHaveBeenCalledTimes(1);
      expect(mockCommentsClient.getComments).toHaveBeenCalledWith(
        'Test',
        '123'
      );
    });
  });
});
