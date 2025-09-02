'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Avatar,
  Link,
  Popover,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  EmojiEmotions as EmojiIcon,
} from '@mui/icons-material';
import { formatDistanceToNow, format } from 'date-fns';
import EmojiPicker from 'emoji-picker-react';
import { Comment } from '@/types/comments';

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
    const date = new Date(dateString);
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
      >
        {comment.user?.name?.charAt(0)?.toUpperCase() || 'U'}
      </Avatar>

      {/* Comment Content */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {/* User Info and Timestamp */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography 
            variant="subtitle2" 
            sx={{ 
              fontWeight: 700,
              color: 'text.primary'
            }}
          >
            {comment.user?.name?.toUpperCase() || 'UNKNOWN USER'}
          </Typography>
          <Typography 
            variant="caption" 
            sx={{ 
              color: 'text.secondary',
              fontSize: '0.75rem'
            }}
          >
            {formatDate(comment.created_at)}
          </Typography>
        </Box>

        {/* Comment Text */}
        {isEditing ? (
          <Box sx={{ mb: 2 }}>
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              style={{
                width: '100%',
                minHeight: '80px',
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderRadius: '8px',
                fontFamily: 'inherit',
                fontSize: '14px',
                resize: 'vertical',
                outline: 'none'
              }}
              placeholder="Edit your comment..."
            />
            <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
              <button
                onClick={handleSaveEdit}
                disabled={!editText.trim() || isSubmitting}
                style={{
                  padding: '6px 12px',
                  backgroundColor: '#1976d2',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                {isSubmitting ? 'Saving...' : 'Save'}
              </button>
              <button
                onClick={handleCancelEdit}
                disabled={isSubmitting}
                style={{
                  padding: '6px 12px',
                  backgroundColor: 'transparent',
                  color: '#666',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                Cancel
              </button>
            </Box>
          </Box>
        ) : (
          <Typography 
            variant="body2" 
            sx={{ 
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
          {/* Quick Emoji Reactions */}
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            {['👍', '❤️', '😊', '🎉'].map((emoji) => {
              const hasReacted = comment.emojis?.[emoji]?.some(reaction => 
                reaction.user_id === currentUserId
              );
              return (
                <IconButton
                  key={emoji}
                  size="small"
                  onClick={() => onReact(comment.id, emoji)}
                  sx={{ 
                    color: hasReacted ? 'primary.main' : 'text.secondary',
                    backgroundColor: hasReacted ? 'primary.light' : 'transparent',
                    '&:hover': { 
                      backgroundColor: hasReacted ? 'primary.main' : 'rgba(0, 0, 0, 0.04)',
                      color: hasReacted ? 'white' : 'primary.main'
                    },
                    fontSize: '16px',
                    width: 32,
                    height: 32
                  }}
                  title={hasReacted ? `Remove ${emoji} reaction` : `Add ${emoji} reaction`}
                >
                  {emoji}
                </IconButton>
              );
            })}
          </Box>

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
              onClick={() => onDelete(comment.id)}
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
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                    padding: '4px 8px',
                    backgroundColor: hasReacted ? 'primary.light' : 'rgba(0, 0, 0, 0.04)',
                    borderRadius: '16px',
                    fontSize: '12px',
                    color: hasReacted ? 'primary.contrastText' : 'text.secondary',
                    border: hasReacted ? '1px solid' : 'none',
                    borderColor: hasReacted ? 'primary.main' : 'transparent',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    '&:hover': {
                      backgroundColor: hasReacted ? 'primary.main' : 'rgba(0, 0, 0, 0.08)',
                      transform: 'scale(1.05)'
                    }
                  }}
                  onClick={() => onReact(comment.id, emoji)}
                  title={hasReacted ? `Remove ${emoji} reaction` : `Add ${emoji} reaction`}
                >
                  <span>{emoji}</span>
                  <span>{reactionCount}</span>
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
        <EmojiPicker
          onEmojiClick={handleEmojiClick}
          width={300}
          height={400}
        />
      </Popover>
    </Box>
  );
}
