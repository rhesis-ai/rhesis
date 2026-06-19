'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Popover,
  Button,
  TextField,
  Tooltip,
  type Theme,
} from '@mui/material';
import {
  EditIcon,
  DeleteIcon,
  EmojiIcon,
  AddTaskIcon,
} from '@/components/icons';
import { formatDistanceToNow, format } from 'date-fns';
import EmojiPicker from 'emoji-picker-react';
import { Comment } from '@/types/comments';
import { DeleteModal } from '@/components/common/DeleteModal';
import { UserAvatar } from '@/components/common/UserAvatar';
import { createReactionTooltipText } from '@/utils/comment-utils';

interface CommentItemProps {
  comment: Comment;
  onEdit: (commentId: string, newText: string) => Promise<void>;
  onDelete: (commentId: string) => Promise<void>;
  onReact: (commentId: string, emoji: string) => Promise<void>;
  onCreateTask?: (commentId: string) => void;
  currentUserId: string;
  entityType?: string;
  isHighlighted?: boolean;
}

export function CommentItem({
  comment,
  onEdit,
  onDelete,
  onReact,
  onCreateTask,
  currentUserId,
  entityType,
  isHighlighted = false,
}: CommentItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(comment.content);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [emojiAnchorEl, setEmojiAnchorEl] = useState<HTMLElement | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const isOwner = comment.user_id === currentUserId;

  const handleSaveEdit = async () => {
    if (!editText.trim()) return;
    setIsSubmitting(true);
    try {
      await onEdit(comment.id, editText.trim());
      setIsEditing(false);
    } catch (_error) {
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelEdit = () => {
    setEditText(comment.content);
    setIsEditing(false);
  };

  const handleConfirmDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete(comment.id);
      setShowDeleteModal(false);
    } catch (_error) {
    } finally {
      setIsDeleting(false);
    }
  };

  const handleEmojiClick = (emojiData: { emoji: string }) => {
    onReact(comment.id, emojiData.emoji);
    setEmojiAnchorEl(null);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const diffInHours =
      (new Date().getTime() - date.getTime()) / (1000 * 60 * 60);
    if (diffInHours < 24) {
      return formatDistanceToNow(date, { addSuffix: true }).toUpperCase();
    }
    return format(date, 'dd MMM yyyy HH:mm').toUpperCase();
  };

  const actionIconSx = {
    p: 0,
    '& .MuiSvgIcon-root': {
      color: (theme: Theme) => `${theme.palette.primary.main} !important`,
    },
  };

  return (
    <>
      <Box
        id={`comment-${comment.id}`}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          ...(isHighlighted && {
            outline: theme => `2px solid ${theme.palette.primary.main}`,
            borderRadius: 1,
            p: 1,
          }),
        }}
      >
        {/* ── Header row ── */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <UserAvatar
            userName={comment.user?.name}
            userPicture={comment.user?.picture}
            sx={{ width: 32, height: 32, flexShrink: 0 }}
          />

          <Typography
            sx={{
              fontWeight: 700,
              fontSize: 14,
              lineHeight: '22px',
              color: 'text.primary',
              whiteSpace: 'nowrap',
            }}
          >
            {comment.user?.name || 'Unknown User'}
          </Typography>

          <Typography
            sx={{
              flex: 1,
              fontSize: 12,
              lineHeight: '18px',
              letterSpacing: '0.48px',
              textTransform: 'uppercase',
              color: 'text.secondary',
            }}
          >
            {formatDate(comment.created_at)}
          </Typography>

          {/* Action icons */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {onCreateTask && entityType !== 'Task' && (
              <Tooltip title="Create task from comment">
                <IconButton
                  size="small"
                  onClick={() => onCreateTask(comment.id)}
                  sx={actionIconSx}
                >
                  <AddTaskIcon sx={{ fontSize: 20 }} />
                </IconButton>
              </Tooltip>
            )}
            {isOwner && (
              <Tooltip title="Edit comment">
                <IconButton
                  size="small"
                  onClick={() => setIsEditing(true)}
                  sx={actionIconSx}
                >
                  <EditIcon sx={{ fontSize: 20 }} />
                </IconButton>
              </Tooltip>
            )}
            {isOwner && (
              <Tooltip title="Delete comment">
                <IconButton
                  size="small"
                  onClick={() => setShowDeleteModal(true)}
                  sx={actionIconSx}
                >
                  <DeleteIcon sx={{ fontSize: 20 }} />
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Box>

        {/* ── Content box ── */}
        <Box
          sx={{
            bgcolor: '#f9f9fa',
            borderRadius: '4px',
            p: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          {isEditing ? (
            <Box>
              <TextField
                value={editText}
                onChange={e => setEditText(e.target.value)}
                multiline
                rows={3}
                fullWidth
                variant="outlined"
                size="small"
                sx={{ mb: 1 }}
              />
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                <Button size="small" onClick={handleCancelEdit}>
                  Cancel
                </Button>
                <Button
                  size="small"
                  variant="contained"
                  onClick={handleSaveEdit}
                  disabled={isSubmitting || !editText.trim()}
                >
                  {isSubmitting ? 'Saving…' : 'Save'}
                </Button>
              </Box>
            </Box>
          ) : (
            <Typography
              sx={{
                fontSize: 16,
                lineHeight: '24px',
                color: 'text.secondary',
                whiteSpace: 'pre-wrap',
              }}
            >
              {comment.content}
            </Typography>
          )}

          {/* Reactions + emoji trigger */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              flexWrap: 'wrap',
            }}
          >
            {Object.entries(comment.emojis || {}).map(([emoji, reactions]) => {
              const hasReacted = reactions.some(
                r => r.user_id === currentUserId
              );
              return (
                <Tooltip
                  key={emoji}
                  title={createReactionTooltipText(reactions, emoji)}
                  arrow
                  placement="top"
                >
                  <Box
                    onClick={() => onReact(comment.id, emoji)}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      border: '1px solid',
                      borderColor: hasReacted ? 'primary.main' : '#b6bdc9',
                      borderRadius: '999px',
                      px: '10px',
                      py: '2px',
                      cursor: 'pointer',
                      userSelect: 'none',
                      '&:hover': { borderColor: 'text.primary' },
                    }}
                  >
                    <Typography sx={{ fontSize: 14, lineHeight: '22px' }}>
                      {emoji}
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: 14,
                        lineHeight: '22px',
                        color: '#2a2e36',
                      }}
                    >
                      {reactions.length}
                    </Typography>
                  </Box>
                </Tooltip>
              );
            })}

            <Tooltip title="Add reaction">
              <IconButton
                size="small"
                onClick={e => setEmojiAnchorEl(e.currentTarget)}
                sx={actionIconSx}
              >
                <EmojiIcon sx={{ fontSize: 20 }} />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </Box>

      <Popover
        open={Boolean(emojiAnchorEl)}
        anchorEl={emojiAnchorEl}
        onClose={() => setEmojiAnchorEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
      >
        <EmojiPicker onEmojiClick={handleEmojiClick} />
      </Popover>

      <DeleteModal
        open={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onConfirm={handleConfirmDelete}
        isLoading={isDeleting}
        itemType="comment"
      />
    </>
  );
}
