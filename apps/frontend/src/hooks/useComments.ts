import { useCallback, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { Comment, EntityType } from '@/types/comments';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { commentKeys } from '@/constants/query-keys';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

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
  const queryClient = useQueryClient();
  const notifications = useNotifications();
  const { status } = useSession();
  const queryKey = useMemo(
    () => commentKeys.list(entityType, entityId),
    [entityType, entityId]
  );

  const {
    data: comments = [],
    isLoading,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey,
    queryFn: async () => {
      const clientFactory = new ApiClientFactory(sessionToken);
      return clientFactory
        .getCommentsClient()
        .getComments(entityType, entityId);
    },
    enabled: isAuthenticated(status) && !!entityType && !!entityId,
  });

  const createComment = useCallback(
    async (text: string) => {
      if (!isAuthenticated(status))
        throw new Error('No session token available');

      const clientFactory = new ApiClientFactory(sessionToken);
      const commentsClient = clientFactory.getCommentsClient();
      const newComment = await commentsClient.createComment({
        content: text,
        entity_type: entityType as EntityType,
        entity_id: entityId,
      });

      const commentWithUser: Comment = {
        ...newComment,
        user: {
          id: currentUserId,
          name: currentUserName,
          email: '',
          picture: currentUserPicture,
        },
      };

      queryClient.setQueryData<Comment[]>(queryKey, prev => [
        commentWithUser,
        ...(prev ?? []),
      ]);

      notifications.show('Comment posted successfully', {
        severity: 'neutral',
        autoHideDuration: 3000,
      });
      return commentWithUser;
    },
    [
      entityType,
      entityId,
      sessionToken,
      currentUserId,
      currentUserName,
      currentUserPicture,
      notifications,
      queryClient,
      queryKey,
      status,
    ]
  );

  const editComment = useCallback(
    async (commentId: string, newText: string) => {
      if (!isAuthenticated(status))
        throw new Error('No session token available');

      const clientFactory = new ApiClientFactory(sessionToken);
      const commentsClient = clientFactory.getCommentsClient();
      const updatedComment = await commentsClient.updateComment(commentId, {
        content: newText,
      });

      let commentWithUser: Comment = updatedComment;
      queryClient.setQueryData<Comment[]>(queryKey, prev =>
        (prev ?? []).map(comment => {
          if (comment.id !== commentId) return comment;
          commentWithUser = {
            ...updatedComment,
            user: comment.user ?? {
              id: currentUserId,
              name: currentUserName,
              email: '',
              picture: currentUserPicture,
            },
          };
          return commentWithUser;
        })
      );

      notifications.show('Comment updated successfully', {
        severity: 'neutral',
        autoHideDuration: 3000,
      });
      return commentWithUser;
    },
    [
      sessionToken,
      currentUserId,
      currentUserName,
      currentUserPicture,
      notifications,
      queryClient,
      queryKey,
      status,
    ]
  );

  const deleteComment = useCallback(
    async (commentId: string) => {
      if (!isAuthenticated(status))
        throw new Error('No session token available');

      const clientFactory = new ApiClientFactory(sessionToken);
      const commentsClient = clientFactory.getCommentsClient();
      const deletedComment = await commentsClient.deleteComment(commentId);

      queryClient.setQueryData<Comment[]>(queryKey, prev =>
        (prev ?? []).filter(comment => comment.id !== commentId)
      );

      notifications.show('Comment deleted successfully', {
        severity: 'neutral',
        autoHideDuration: 3000,
      });
      return deletedComment;
    },
    [sessionToken, notifications, queryClient, queryKey, status]
  );

  const reactToComment = useCallback(
    async (commentId: string, emoji: string) => {
      if (!isAuthenticated(status))
        throw new Error('No session token available');

      const clientFactory = new ApiClientFactory(sessionToken);
      const commentsClient = clientFactory.getCommentsClient();

      const current = queryClient.getQueryData<Comment[]>(queryKey) ?? [];
      const comment = current.find(c => c.id === commentId);
      const hasReacted = comment?.emojis?.[emoji]?.some(
        reaction => reaction.user_id === currentUserId
      );

      const updatedComment = hasReacted
        ? await commentsClient.removeEmojiReaction(commentId, emoji)
        : await commentsClient.addEmojiReaction(commentId, emoji);

      let commentWithUser: Comment = updatedComment;
      queryClient.setQueryData<Comment[]>(queryKey, prev =>
        (prev ?? []).map(c => {
          if (c.id !== commentId) return c;
          commentWithUser = {
            ...updatedComment,
            user: c.user ?? {
              id: currentUserId,
              name: currentUserName,
              email: '',
              picture: currentUserPicture,
            },
          };
          return commentWithUser;
        })
      );
      return commentWithUser;
    },
    [
      sessionToken,
      currentUserId,
      currentUserName,
      currentUserPicture,
      queryClient,
      queryKey,
      status,
    ]
  );

  return {
    comments,
    isLoading,
    error: queryError ? 'Failed to fetch comments' : null,
    createComment,
    editComment,
    deleteComment,
    reactToComment,
    refetch,
  };
}
