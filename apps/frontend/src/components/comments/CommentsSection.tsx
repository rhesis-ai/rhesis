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
  IconButton,
} from '@mui/material';
<<<<<<< HEAD
import { Send as SendIcon } from '@mui/icons-material';
=======
import { Add as AddIcon } from '@mui/icons-material';
>>>>>>> b300f1b (feature/tasks_for_collabortaion)
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
  onCreateTask?: (commentId: string) => void;
  onCreateTaskFromEntity?: () => void;
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
  onCreateTask,
  onCreateTaskFromEntity,
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

  const getEntityDisplayName = (entityType: EntityType): string => {
    switch (entityType) {
      case 'Test':
        return 'Test';
      case 'TestSet':
        return 'Test Set';
      case 'TestRun':
        return 'Test Run';
      case 'TestResult':
        return 'Test Result';
      default:
        return entityType;
    }
  };

  const sortedComments = [...comments].sort((a, b) => 
    new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  return (
    <Paper sx={{ p: 3 }}>
      {/* Create Task Button - Top Left */}
      {onCreateTaskFromEntity && (
        <Box sx={{ mb: 3 }}>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={onCreateTaskFromEntity}
            size="small"
          >
            Create Task
          </Button>
        </Box>
      )}

      {/* Comments List */}
      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      ) : comments.length > 0 && (
        <Box sx={{ mb: 3 }}>
          {sortedComments.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              onEdit={handleEditComment}
              onDelete={handleDeleteComment}
              onReact={handleReactToComment}
              onCreateTask={onCreateTask}
              currentUserId={currentUserId}
              entityType={entityType}
            />
          ))}
        </Box>
      )}

      {/* Divider - Only show when there are comments */}
      {comments.length > 0 && <Divider sx={{ my: 3 }} />}

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
          <Box sx={{ flex: 1, minWidth: 0, position: 'relative' }}>
            <TextField
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="Add comment ..."
              multiline
              rows={3}
              fullWidth
              variant="outlined"
              size="small"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              InputProps={{
                endAdornment: newComment.trim().length > 0 ? (
                  <IconButton
                    type="submit"
                    disabled={isSubmitting || !newComment.trim()}
                    size="small"
                    sx={{ 
                      mr: 0.5,
                      color: 'text.secondary',
                      '&:hover': {
                        color: 'primary.main',
                      },
                      '&:disabled': {
                        color: 'action.disabled',
                      }
                    }}
                  >
                    {isSubmitting ? (
                      <CircularProgress size={16} color="inherit" />
                    ) : (
                      <SendIcon fontSize="small" />
                    )}
                  </IconButton>
                ) : null
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
          </Box>
        </Box>
      </Box>
    </Paper>
  );
}
