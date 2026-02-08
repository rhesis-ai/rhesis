'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  IconButton,
  Link,
  Popover,
  Button,
  TextField,
  Tooltip,
  useTheme,
  Chip,
} from '@mui/material';
import {
  EditIcon,
  DeleteIcon,
  EmojiIcon,
  AssignmentIcon,
  AddTaskIcon,
} from '@/components/icons';
import { formatDistanceToNow, format } from 'date-fns';
import EmojiPicker from 'emoji-picker-react';
import { Comment } from '@/types/comments';
import { DeleteModal } from '@/components/common/DeleteModal';
import { UserAvatar } from '@/components/common/UserAvatar';
import { createReactionTooltipText } from '@/utils/comment-utils';
import { useTasks } from '@/hooks/useTasks';
import { Task } from '@/utils/api-client/interfaces/task';

interface CommentItemProps {
  comment: Comment;
  onEdit: (commentId: string, newText: string) => Promise<void>;
  onDelete: (commentId: string) => Promise<void>;
  onReact: (commentId: string, emoji: string) => Promise<void>;
  onCreateTask?: (commentId: string) => void;
  currentUserId: string;
  entityType?: string; // Add entityType to determine if Create Task button should show
  isHighlighted?: boolean; // Add highlighting prop
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
  const theme = useTheme();
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(comment.content);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [emojiAnchorEl, setEmojiAnchorEl] = useState<HTMLElement | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [associatedTasks, setAssociatedTasks] = useState<Task[]>([]);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);

  const { fetchTasksByCommentId } = useTasks({ autoFetch: false });

  const isOwner = comment.user_id === currentUserId;
  const canEdit = isOwner;
  const canDelete = isOwner;

  // Fetch associated tasks when component mounts
  useEffect(() => {
    const loadAssociatedTasks = async () => {
      setIsLoadingTasks(true);
      try {
        const tasks = await fetchTasksByCommentId(comment.id);
        setAssociatedTasks(tasks);
      } catch (_error) {
      } finally {
        setIsLoadingTasks(false);
      }
    };

    loadAssociatedTasks();
  }, [comment.id, fetchTasksByCommentId]);

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

  const handleDeleteClick = () => {
    setShowDeleteModal(true);
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

  // Get task count for this comment (placeholder - would need API call in real implementation)
  const taskCount: number = 0; // TODO: Implement API call to get task count by comment ID

  return (
    <>
      <Box
        id={`comment-${comment.id}`}
        sx={{
          display: 'flex',
          gap: 2,
          mb: 3,
          alignItems: 'flex-start',
          // Highlighting styles
          ...(isHighlighted && {
            backgroundColor: 'primary.light',
            border: '2px solid',
            borderColor: 'primary.main',
            borderRadius: theme.shape.borderRadius,
            p: 2,
            mb: 3,
          }),
        }}
      >
        {/* User Avatar */}
        <UserAvatar
          userName={comment.user?.name}
          userPicture={comment.user?.picture}
          size={40}
        />

        {/* Comment Content */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {/* Header with user info and action buttons */}
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              mb: 1,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
              <Typography
                variant="subtitle2"
                fontWeight={600}
                sx={{ lineHeight: 1.2 }}
              >
                {comment.user?.name || 'UNKNOWN USER'}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{
                  lineHeight: 1.2,
                  fontSize: theme.typography.chartLabel.fontSize,
                }}
              >
                {formatDate(comment.created_at)}
              </Typography>
            </Box>

            {/* Action Buttons and Task Counter */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {/* Task Counter */}
              {taskCount > 0 && (
                <Tooltip
                  title={`${taskCount} task${taskCount === 1 ? '' : 's'} created from this comment`}
                >
                  <Chip
                    icon={<AddTaskIcon />}
                    label={taskCount}
                    size="small"
                    color="primary"
                    variant="outlined"
                    sx={{
                      height: 24,
                      fontSize: theme.typography.caption.fontSize,
                      '& .MuiChip-icon': {
                        fontSize: theme.typography.helperText.fontSize,
                      },
                    }}
                  />
                </Tooltip>
              )}

              {/* Create Task Button */}
              {onCreateTask && entityType !== 'Task' && (
                <Tooltip title="Create Task from Comment">
                  <IconButton
                    size="small"
                    onClick={() => onCreateTask(comment.id)}
                    sx={{
                      color: 'text.secondary',
                      '&:hover': { color: 'warning.main' },
                    }}
                  >
                    <AssignmentIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}

              {/* Edit/Delete Icons (only for comment owner) */}
              {canEdit && (
                <Tooltip title="Edit comment">
                  <IconButton
                    size="small"
                    onClick={() => setIsEditing(true)}
                    sx={{
                      color: 'text.secondary',
                      '&:hover': { color: 'primary.main' },
                    }}
                  >
                    <EditIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}

              {canDelete && (
                <Tooltip title="Delete comment">
                  <IconButton
                    size="small"
                    onClick={handleDeleteClick}
                    sx={{
                      color: 'text.secondary',
                      '&:hover': { color: 'error.main' },
                    }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}
            </Box>
          </Box>

          {isEditing ? (
            <Box sx={{ mt: 1 }}>
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
                color: 'text.primary',
              }}
            >
              {comment.content}
            </Typography>
          )}

          {/* Emoji Picker Button and Reactions */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            {/* Emoji Reactions Display */}
            {Object.keys(comment.emojis || {}).length > 0 && (
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {Object.entries(comment.emojis).map(([emoji, reactions]) => {
                  const hasReacted = reactions.some(
                    reaction => reaction.user_id === currentUserId
                  );
                  const reactionCount = reactions.length;
                  const tooltipText = createReactionTooltipText(
                    reactions,
                    emoji
                  );

                  return (
                    <Tooltip
                      key={emoji}
                      title={tooltipText}
                      arrow
                      placement="top"
                    >
                      <Box
                        onClick={() => onReact(comment.id, emoji)}
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.5,
                          bgcolor: 'background.default',
                          color: 'text.primary',
                          border: '1px solid',
                          borderColor: hasReacted ? 'primary.main' : 'divider',
                          borderRadius: theme => theme.shape.borderRadius * 4,
                          px: 1.5,
                          py: 0.75,
                          cursor: 'pointer',
                          '&:hover': {
                            bgcolor: 'action.hover',
                            color: 'text.primary',
                            borderColor: hasReacted
                              ? 'primary.main'
                              : 'text.primary',
                          },
                        }}
                      >
                        <Typography variant="subtitle1">{emoji}</Typography>
                        <Typography
                          variant="body2"
                          fontWeight={600}
                          sx={{
                            color: 'text.primary',
                          }}
                        >
                          {reactionCount}
                        </Typography>
                      </Box>
                    </Tooltip>
                  );
                })}
              </Box>
            )}

            <IconButton
              size="small"
              onClick={openEmojiPicker}
              sx={{
                color: 'text.secondary',
                '&:hover': { color: 'primary.main' },
              }}
            >
              <EmojiIcon fontSize="small" />
            </IconButton>
          </Box>

          {/* Associated Tasks */}
          {associatedTasks.length > 0 && (
            <Box
              sx={{
                mt: 2,
                pt: 2,
                borderTop: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mb: 1, display: 'block' }}
              >
                Associated Tasks:
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {associatedTasks.map(task => (
                  <Box
                    key={task.id}
                    onClick={() => window.open(`/tasks/${task.id}`, '_blank')}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      bgcolor: 'background.default',
                      color: 'text.primary',
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: theme.shape.borderRadius,
                      px: 1.5,
                      py: 0.75,
                      cursor: 'pointer',
                      '&:hover': {
                        bgcolor: 'action.hover',
                        color: 'text.primary',
                        borderColor: 'text.primary',
                      },
                    }}
                  >
                    <AddTaskIcon
                      sx={{ fontSize: '1rem', color: 'text.secondary' }}
                    />
                    <Typography
                      variant="body2"
                      fontWeight={600}
                      sx={{
                        color: 'text.primary',
                        fontSize: theme.typography.caption.fontSize,
                      }}
                    >
                      {task.title}
                    </Typography>
                  </Box>
                ))}
              </Box>
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
      <DeleteModal
        open={showDeleteModal}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
        isLoading={isDeleting}
        itemType="comment"
      />
    </>
  );
}
