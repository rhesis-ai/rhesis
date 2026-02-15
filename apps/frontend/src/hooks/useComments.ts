import { useState, useCallback, useEffect } from 'react';
import { Comment, EntityType } from '@/types/comments';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';

interface UseCommentsProps {
  entityType: string;
  entityId: string;
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export function useComments({
  entityType,
  entityId,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: UseCommentsProps) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const notifications = useNotifications();

  const fetchComments = useCallback(async () => {
    if (!sessionToken) {
      setError('No session token available');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const commentsClient = clientFactory.getCommentsClient();
      const fetchedComments = await commentsClient.getComments(
        entityType,
        entityId
      );
      setComments(fetchedComments);
    } catch (_err) {
      setError('Failed to fetch comments');
      notifications.show('Failed to fetch comments', {
        severity: 'error',
        autoHideDuration: 3000,
      });
    } finally {
      setIsLoading(false);
    }
  }, [entityType, entityId, sessionToken, notifications]);

  const createComment = useCallback(
    async (text: string) => {
      if (!sessionToken) {
        throw new Error('No session token available');
      }

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const commentsClient = clientFactory.getCommentsClient();
        const newComment = await commentsClient.createComment({
          content: text,
          entity_type: entityType as EntityType,
          entity_id: entityId,
        });

        // Add user information to the new comment since the API doesn't return it
        const commentWithUser: Comment = {
          ...newComment,
          user: {
            id: currentUserId,
            name: currentUserName,
            email: '',
            picture: currentUserPicture,
          },
        };

        setComments(prev => [commentWithUser, ...prev]);

        notifications.show('Comment posted successfully', {
          severity: 'neutral',
          autoHideDuration: 3000,
        });
        return commentWithUser;
      } catch (err) {
        throw err;
      }
    },
    [
      entityType,
      entityId,
      sessionToken,
      currentUserId,
      currentUserName,
      currentUserPicture,
      notifications,
    ]
  );

  const editComment = useCallback(
    async (commentId: string, newText: string) => {
      if (!sessionToken) {
        throw new Error('No session token available');
      }

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const commentsClient = clientFactory.getCommentsClient();
        const updatedComment = await commentsClient.updateComment(commentId, {
          content: newText,
        });

        // Preserve the existing user information from the current comment
        const currentComment = comments.find(c => c.id === commentId);
        const commentWithUser: Comment = {
          ...updatedComment,
          user: currentComment?.user || {
            id: currentUserId,
            name: currentUserName,
            email: '',
            picture: currentUserPicture,
          },
        };

        setComments(prev =>
          prev.map(comment =>
            comment.id === commentId ? commentWithUser : comment
          )
        );

        notifications.show('Comment updated successfully', {
          severity: 'neutral',
          autoHideDuration: 3000,
        });
        return commentWithUser;
      } catch (err) {
        throw err;
      }
    },
    [
      sessionToken,
      comments,
      currentUserId,
      currentUserName,
      currentUserPicture,
      notifications,
    ]
  );

  const deleteComment = useCallback(
    async (commentId: string) => {
      if (!sessionToken) {
        throw new Error('No session token available');
      }

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const commentsClient = clientFactory.getCommentsClient();
        const deletedComment = await commentsClient.deleteComment(commentId);

        setComments(prev => prev.filter(comment => comment.id !== commentId));

        notifications.show('Comment deleted successfully', {
          severity: 'neutral',
          autoHideDuration: 3000,
        });

        return deletedComment;
      } catch (err) {
        throw err;
      }
    },
    [sessionToken, notifications]
  );

  const reactToComment = useCallback(
    async (commentId: string, emoji: string) => {
      if (!sessionToken) {
        throw new Error('No session token available');
      }

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const commentsClient = clientFactory.getCommentsClient();

        // Check if user already reacted with this emoji
        const comment = comments.find(c => c.id === commentId);
        const hasReacted = comment?.emojis?.[emoji]?.some(
          reaction => reaction.user_id === currentUserId
        );

        let updatedComment: Comment;
        if (hasReacted) {
          // Remove reaction
          updatedComment = await commentsClient.removeEmojiReaction(
            commentId,
            emoji
          );
        } else {
          // Add reaction
          updatedComment = await commentsClient.addEmojiReaction(
            commentId,
            emoji
          );
        }

        // Preserve the existing user information from the current comment
        const commentWithUser: Comment = {
          ...updatedComment,
          user: comment?.user || {
            id: currentUserId,
            name: currentUserName,
            email: '',
            picture: currentUserPicture,
          },
        };

        setComments(prev =>
          prev.map(c => (c.id === commentId ? commentWithUser : c))
        );
      } catch (err) {
        throw err;
      }
    },
    [sessionToken, comments, currentUserId, currentUserName, currentUserPicture]
  );

  useEffect(() => {
    fetchComments();
  }, [fetchComments]);

  return {
    comments,
    isLoading,
    error,
    createComment,
    editComment,
    deleteComment,
    reactToComment,
    refetch: fetchComments,
  };
}
