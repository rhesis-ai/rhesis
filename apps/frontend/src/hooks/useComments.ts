import { useState, useCallback, useEffect } from 'react';
import { Comment, CreateCommentRequest, UpdateCommentRequest } from '@/types/comments';
import { mockCommentsService } from '@/utils/mock-data/comments';

interface UseCommentsProps {
  entityType: string;
  entityId: string;
}

export function useComments({ entityType, entityId }: UseCommentsProps) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchComments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const fetchedComments = await mockCommentsService.getComments(entityType, entityId);
      setComments(fetchedComments);
    } catch (err) {
      setError('Failed to fetch comments');
      console.error('Error fetching comments:', err);
    } finally {
      setIsLoading(false);
    }
  }, [entityType, entityId]);

  const createComment = useCallback(async (text: string) => {
    try {
      const newComment = await mockCommentsService.createComment({
        comment_text: text,
        entity_type: entityType,
        entity_id: entityId
      });
      
      setComments(prev => [newComment, ...prev]);
      return newComment;
    } catch (err) {
      console.error('Error creating comment:', err);
      throw err;
    }
  }, [entityType, entityId]);

  const editComment = useCallback(async (commentId: string, newText: string) => {
    try {
      const updatedComment = await mockCommentsService.updateComment(commentId, {
        comment_text: newText
      });
      
      setComments(prev => 
        prev.map(comment => 
          comment.id === commentId ? updatedComment : comment
        )
      );
      return updatedComment;
    } catch (err) {
      console.error('Error editing comment:', err);
      throw err;
    }
  }, []);

  const deleteComment = useCallback(async (commentId: string) => {
    try {
      await mockCommentsService.deleteComment(commentId);
      
      setComments(prev => 
        prev.filter(comment => comment.id !== commentId)
      );
    } catch (err) {
      console.error('Error deleting comment:', err);
      throw err;
    }
  }, []);

  const reactToComment = useCallback(async (commentId: string, emoji: string) => {
    try {
      const currentUserId = mockCommentsService.getCurrentUserId();
      await mockCommentsService.addEmojiReaction(commentId, emoji, currentUserId);
      
      // Update local state directly instead of refetching
      setComments(prev => 
        prev.map(comment => {
          if (comment.id === commentId) {
            // Get the updated emoji data from the service
            const updatedEmojis = mockCommentsService.getCommentEmojis(commentId);
            return {
              ...comment,
              emojis: updatedEmojis
            };
          }
          return comment;
        })
      );
    } catch (err) {
      console.error('Error reacting to comment:', err);
      throw err;
    }
  }, []);

  const getCurrentUserId = useCallback(() => {
    return mockCommentsService.getCurrentUserId();
  }, []);

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
    getCurrentUserId,
    refetch: fetchComments
  };
}
