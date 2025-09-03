'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Avatar,
  Link,
  Popover,
  Button,
  TextareaAutosize,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  EmojiEmotions as EmojiIcon,
} from '@mui/icons-material';
import { formatDistanceToNow, format } from 'date-fns';
import EmojiPicker from 'emoji-picker-react';
import { Comment } from '@/types/comments';
import { DeleteCommentModal } from './DeleteCommentModal';

interface CommentItemProps {
  comment: Comment;
  onEdit: (commentId: string, newText: string) => Promise<void>;
  onDelete: (commentId: string) => Promise<void>;
  onReact: (commentId: string, emoji: string) => Promise<void>;
  currentUserId: string;
}

export function CommentItem({ 
  comment, 
  onEdit, 
  onDelete, 
  onReact, 
  currentUserId 
}: CommentItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(comment.content);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [emojiAnchorEl, setEmojiAnchorEl] = useState<HTMLElement | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const isOwner = comment.user_id === currentUserId;
  const canEdit = isOwner;
  const canDelete = isOwner;

  const handleSaveEdit = async () => {
    if (!editText.trim()) return;
    
    setIsSubmitting(true);
    try {
      await onEdit(comment.id, editText.trim());
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to edit comment:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelEdit = () => {
    setEditText(comment.content);
    setIsEditing(false);
  };

  const handleDeleteClick = () => {
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete(comment.id);
      setShowDeleteModal(false);
    } catch (error) {
      console.error('Failed to delete comment:', error);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCancelDelete = () => {
    setShowDeleteModal(false);
  };

  const handleEmojiClick = (emojiData: any) => {
    onReact(comment.id, emojiData.emoji);
    setEmojiAnchorEl(null);
  };

  const openEmojiPicker = (event: React.MouseEvent<HTMLElement>) => {
    setEmojiAnchorEl(event.currentTarget);
  };

  const closeEmojiPicker = () => {
    setEmojiAnchorEl(null);
  };

  const formatDate = (dateString: string) => {
    // Backend sends timestamps without timezone info, so we need to treat them as UTC
    // Add 'Z' suffix to ensure UTC parsing
    const date = new Date(dateString + 'Z');
    const now = new Date();
    const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
    
    // If less than 24 hours, use relative time
    if (diffInHours < 24) {
      return formatDistanceToNow(date, { addSuffix: true }).toUpperCase();
    } else {
      // If more than 24 hours, use absolute date
      return format(date, 'dd MMM yyyy HH:mm').toUpperCase();
    }
  };

  return (
    <>
      <Box sx={{ 
        display: 'flex', 
        gap: 2, 
        mb: 3,
        alignItems: 'flex-start'
      }}>
        {/* User Avatar */}
        <Avatar 
          sx={{ 
            width: 40, 
            height: 40, 
            bgcolor: 'primary.main',
            flexShrink: 0
          }}
          src={comment.user?.picture}
          alt={comment.user?.name || 'User'}
        >
          {comment.user?.name ? comment.user.name.charAt(0).toUpperCase() : 'U'}
        </Avatar>

        {/* Comment Content */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle2" fontWeight={600}>
              {comment.user?.name || 'UNKNOWN USER'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {formatDate(comment.created_at)}
            </Typography>
          </Box>

          {isEditing ? (
            <Box sx={{ mt: 1 }}>
              <TextareaAutosize
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                minRows={3}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid #ddd',
                  borderRadius: '8px',
                  fontFamily: 'inherit',
                  fontSize: '14px',
                  resize: 'vertical',
                  outline: 'none',
                }}
              />
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 1 }}>
                <Button 
                  size="small" 
                  onClick={handleCancelEdit}
                  sx={{ textTransform: 'none', borderRadius: '16px' }}
                >
                  Cancel
                </Button>
                <Button 
                  size="small" 
                  variant="contained" 
                  onClick={handleSaveEdit} 
                  disabled={isSubmitting || !editText.trim()}
                  sx={{ textTransform: 'none', borderRadius: '16px' }}
                >
                  {isSubmitting ? 'Saving...' : 'Save'}
                </Button>
              </Box>
            </Box>
          ) : (
            <Typography 
              variant="body2" 
              sx={{ 
                mt: 1, 
                mb: 2, 
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
                color: 'text.primary'
              }}
            >
              {comment.content}
            </Typography>
          )}

          {/* Action Buttons */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      {/* Emoji Picker Button */}
          <IconButton
            size="small"
            onClick={openEmojiPicker}
            sx={{ 
              color: 'text.secondary',
              '&:hover': { color: 'primary.main' }
            }}
          >
            <EmojiIcon fontSize="small" />
          </IconButton>

            {/* Edit/Delete Links (only for comment owner) */}
            {canEdit && (
              <Link
                component="button"
                variant="body2"
                onClick={() => setIsEditing(true)}
                sx={{ 
                  color: 'text.secondary',
                  textDecoration: 'none',
                  fontSize: '12px',
                  fontWeight: 500,
                  '&:hover': { color: 'primary.main' }
                }}
              >
                EDIT
              </Link>
            )}
            
            {canDelete && (
              <Link
                component="button"
                variant="body2"
                onClick={handleDeleteClick}
                sx={{ 
                  color: 'text.secondary',
                  textDecoration: 'none',
                  fontSize: '12px',
                  fontWeight: 500,
                  '&:hover': { color: 'error.main' }
                }}
              >
                DELETE
              </Link>
            )}
          </Box>

          {/* Emoji Reactions Display */}
          {Object.keys(comment.emojis || {}).length > 0 && (
            <Box sx={{ display: 'flex', gap: 1, mt: 1, flexWrap: 'wrap' }}>
              {Object.entries(comment.emojis).map(([emoji, reactions]) => {
                const hasReacted = reactions.some(reaction => 
                  reaction.user_id === currentUserId
                );
                const reactionCount = reactions.length;
                return (
                  <Box
                    key={emoji}
                    onClick={() => onReact(comment.id, emoji)}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      bgcolor: hasReacted ? 'primary.light' : 'background.default',
                      color: hasReacted ? 'primary.main' : 'text.secondary',
                      border: '1px solid',
                      borderColor: hasReacted ? 'primary.main' : 'divider',
                      borderRadius: '16px',
                      px: 1,
                      py: 0.5,
                      cursor: 'pointer',
                      '&:hover': {
                        bgcolor: hasReacted ? 'primary.main' : 'action.hover',
                        color: hasReacted ? 'white' : 'text.primary',
                        borderColor: hasReacted ? 'primary.main' : 'text.primary'
                      }
                    }}
                  >
                    <Typography variant="caption">{emoji}</Typography>
                    <Typography variant="caption" fontWeight={600} sx={{ 
                      color: hasReacted ? 'primary.contrastText' : 'text.primary' 
                    }}>
                      {reactionCount}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          )}
        </Box>

        {/* Emoji Picker Popover */}
        <Popover
          open={Boolean(emojiAnchorEl)}
          anchorEl={emojiAnchorEl}
          onClose={closeEmojiPicker}
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'left',
          }}
          transformOrigin={{
            vertical: 'top',
            horizontal: 'left',
          }}
        >
          <EmojiPicker onEmojiClick={handleEmojiClick} />
        </Popover>
      </Box>

      {/* Delete Confirmation Modal */}
      <DeleteCommentModal
        open={showDeleteModal}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
        isLoading={isDeleting}
      />
    </>
  );
}
