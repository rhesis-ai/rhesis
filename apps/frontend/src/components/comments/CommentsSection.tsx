'use client';

import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  CircularProgress,
  Divider,
  Paper,
} from '@mui/material';
import { Send as SendIcon, ChatBubbleOutline as ChatIcon } from '@mui/icons-material';
import { Comment, EntityType } from '@/types/comments';
import { CommentItem } from './CommentItem';
import { UserAvatar } from '@/components/common/UserAvatar';

interface CommentsSectionProps {
  entityType: EntityType;
  entityId: string;
  comments: Comment[];
  onCreateComment: (text: string) => Promise<void>;
  onEditComment: (commentId: string, newText: string) => Promise<void>;
  onDeleteComment: (commentId: string) => Promise<void>;
  onReactToComment: (commentId: string, emoji: string) => Promise<void>;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
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
  currentUserName,
  currentUserPicture,
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
    new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

    return (
    <Paper 
      elevation={0}
      sx={{ 
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        overflow: 'hidden',
        bgcolor: 'background.paper',
        mt: 4,
        mb: 3,
        mx: 2
      }}
    >
      {/* Section Header with Icon */}
      <Box 
        sx={{ 
          p: 3,
          borderBottom: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.default'
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <ChatIcon color="primary" />
          <Typography variant="h6" fontWeight={600}>
            Comments ({comments.length})
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary">
          Share your thoughts, ask questions, or provide feedback about this {entityType}.
        </Typography>
      </Box>

      {/* Comments Content */}
      <Box sx={{ p: 4 }}>
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

        {/* Divider before comment form */}
        <Divider sx={{ my: 3 }} />

        {/* Comment Form */}
        <Box component="form" onSubmit={handleSubmit}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
            {/* User Avatar */}
            <UserAvatar 
              userName={currentUserName}
              userPicture={currentUserPicture}
              size={40}
            />

            {/* Comment Input */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <TextField
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Add comment ..."
                multiline
                rows={3}
                fullWidth
                variant="outlined"
                size="small"
                sx={{ mb: 2 }}
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
    </Paper>
  );
}
