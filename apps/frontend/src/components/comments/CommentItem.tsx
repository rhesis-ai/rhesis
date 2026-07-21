'use client';

import React, { useMemo, useState } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Popover,
  Button,
  TextField,
  Tooltip,
} from '@mui/material';
import {
  EditIcon,
  DeleteIcon,
  EmojiIcon,
  AddTaskIcon,
} from '@/components/icons';
import { formatDistanceToNow, format } from 'date-fns';
import EmojiPicker from 'emoji-picker-react';
import { Comment, EntityType } from '@/types/comments';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { DeleteModal } from '@/components/common/DeleteModal';
import { UserAvatar } from '@/components/common/UserAvatar';
import { createReactionTooltipText } from '@/utils/comment-utils';
import { EntityActionBar } from '@/components/common/EntityActionBar';
import type { EntityAction } from '@/components/common/entity-actions';
import { Capability } from '@/constants/capabilities';
import { can, Can } from '@/components/common/Can';

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

  const canReact = can(comment, Capability.Comment.REACT);

  // Actions declared as data; EntityActionBar renders only those the server
  // permits (capability) and `isVisible` allows. No canEdit/canDelete booleans,
  // no per-button wiring — adding an action is one entry here.
  const actions = useMemo<EntityAction<Comment>[]>(() => {
    const list: EntityAction<Comment>[] = [];
    if (onCreateTask) {
      list.push({
        id: 'create-task',
        label: 'Create task from comment',
        icon: AddTaskIcon,
        isVisible: () => entityType !== EntityType.TASK,
        onSelect: c => onCreateTask(c.id),
      });
    }
    list.push(
      {
        id: 'edit',
        label: 'Edit comment',
        icon: EditIcon,
        capability: Capability.Comment.UPDATE,
        onSelect: () => setIsEditing(true),
      },
      {
        id: 'delete',
        label: 'Delete comment',
        icon: DeleteIcon,
        capability: Capability.Comment.DELETE,
        onSelect: () => setShowDeleteModal(true),
      }
    );
    return list;
  }, [onCreateTask, entityType]);

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

          {/* Action icons — gated + rendered generically from `actions` */}
          <EntityActionBar subject={comment} actions={actions} />
        </Box>

        {/* ── Content box ── */}
        <Box
          sx={{
            bgcolor: theme => theme.palette.greyscale.surface1,
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
                    onClick={
                      canReact ? () => onReact(comment.id, emoji) : undefined
                    }
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      border: '1px solid',
                      borderColor: theme =>
                        hasReacted
                          ? theme.palette.primary.main
                          : theme.palette.greyscale.border,
                      borderRadius: BORDER_RADIUS.pill,
                      px: '10px',
                      py: '2px',
                      cursor: canReact ? 'pointer' : 'default',
                      userSelect: 'none',
                      '&:hover': canReact
                        ? { borderColor: 'text.primary' }
                        : {},
                    }}
                  >
                    <Typography sx={{ fontSize: 14, lineHeight: '22px' }}>
                      {emoji}
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: 14,
                        lineHeight: '22px',
                        color: theme => theme.palette.greyscale.body,
                      }}
                    >
                      {reactions.length}
                    </Typography>
                  </Box>
                </Tooltip>
              );
            })}

            <Can subject={comment} capability={Capability.Comment.REACT}>
              <Tooltip title="Add reaction">
                <IconButton
                  size="small"
                  color="primary"
                  onClick={e => setEmojiAnchorEl(e.currentTarget)}
                  sx={{ p: 0 }}
                >
                  <EmojiIcon sx={{ fontSize: 20 }} />
                </IconButton>
              </Tooltip>
            </Can>
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
