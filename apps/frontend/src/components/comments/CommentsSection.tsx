'use client';

import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Avatar,
  TextareaAutosize,
  Button,
  CircularProgress,
} from '@mui/material';
import { Send as SendIcon } from '@mui/icons-material';
import { Comment, EntityType } from '@/types/comments';
import { CommentItem } from './CommentItem';

interface CommentsSectionProps {
  entityType: EntityType;
  entityId: string;
  comments: Comment[];
  onCreateComment: (text: string) => Promise<void>;
  onEditComment: (commentId: string, newText: string) => Promise<void>;
  onDeleteComment: (commentId: string) => Promise<void>;
  onReactToComment: (commentId: string, emoji: string) => Promise<void>;
  currentUserId: string;
  isLoading?: boolean;
}

export function CommentsSection({
  entityType,
  entityId,
  comments,
  onCreateComment,
  onEditComment,
  onDeleteComment,
  onReactToComment,
  currentUserId,
  isLoading = false,
}: CommentsSectionProps) {
  const [newComment, setNewComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    
    setIsSubmitting(true);
    setError(null);
    
    try {
      await onCreateComment(newComment.trim());
      setNewComment('');
    } catch (err) {
      setError('Failed to post comment. Please try again.');
      console.error('Failed to create comment:', err);
    } finally {
      setIsSubmitting(false);
    }
  }, [newComment, onCreateComment]);

  const handleEditComment = useCallback(async (commentId: string, newText: string) => {
    try {
      await onEditComment(commentId, newText);
    } catch (err) {
      console.error('Failed to edit comment:', err);
      throw err; // Re-throw to let CommentItem handle the error
    }
  }, [onEditComment]);

  const handleDeleteComment = useCallback(async (commentId: string) => {
    try {
      await onDeleteComment(commentId);
    } catch (err) {
      console.error('Failed to delete comment:', err);
      throw err; // Re-throw to let CommentItem handle the error
    }
  }, [onDeleteComment]);

  const handleReactToComment = useCallback(async (commentId: string, emoji: string) => {
    try {
      await onReactToComment(commentId, emoji);
    } catch (err) {
      console.error('Failed to react to comment:', err);
      throw err; // Re-throw to let CommentItem handle the error
    }
  }, [onReactToComment]);

  const sortedComments = [...comments].sort((a, b) => 
    new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <Box>
      {/* Section Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Comments ({comments.length})
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Share your thoughts, ask questions, or provide feedback about this {entityType}.
        </Typography>
      </Box>

      {/* Comments List */}
      <Box sx={{ mb: 4 }}>
        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : comments.length === 0 ? (
          <Box 
            sx={{ 
              textAlign: 'center', 
              py: 6,
              border: '2px dashed',
              borderColor: 'divider',
              borderRadius: 2,
              bgcolor: 'background.default'
            }}
          >
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No comments yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Be the first to share your thoughts about this {entityType}!
            </Typography>
          </Box>
        ) : (
          <Box>
            {sortedComments.map((comment) => (
              <CommentItem
                key={comment.id}
                comment={comment}
                onEdit={handleEditComment}
                onDelete={handleDeleteComment}
                onReact={handleReactToComment}
                currentUserId={currentUserId}
              />
            ))}
          </Box>
        )}
      </Box>

      {/* Comment Form - Fixed at bottom like in the design */}
      <Box 
        sx={{ 
          borderTop: '1px solid',
          borderColor: 'divider',
          pt: 3,
          mt: 4
        }}
      >
        <Box component="form" onSubmit={handleSubmit}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
            {/* User Avatar */}
            <Avatar 
              sx={{ 
                width: 40, 
                height: 40, 
                bgcolor: 'primary.main',
                flexShrink: 0
              }}
            >
              {currentUserId === 'current-user' ? 'Y' : 'U'}
            </Avatar>

            {/* Comment Input */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <TextareaAutosize
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Add comment ..."
                style={{
                  width: '100%',
                  minHeight: '80px',
                  padding: '12px 16px',
                  border: '1px solid #ddd',
                  borderRadius: '20px',
                  fontFamily: 'inherit',
                  fontSize: '14px',
                  resize: 'none',
                  outline: 'none',
                  lineHeight: '1.5'
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.ctrlKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
              />
              
              {/* Error Message */}
              {error && (
                <Typography 
                  variant="caption" 
                  color="error" 
                  sx={{ mt: 1, display: 'block' }}
                >
                  {error}
                </Typography>
              )}

              {/* Submit Button */}
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                <Button
                  type="submit"
                  variant="contained"
                  disabled={!newComment.trim() || isSubmitting}
                  startIcon={isSubmitting ? <CircularProgress size={16} /> : <SendIcon />}
                  sx={{
                    borderRadius: '20px',
                    textTransform: 'none',
                    px: 3
                  }}
                >
                  {isSubmitting ? 'Posting...' : 'Comment'}
                </Button>
              </Box>
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
