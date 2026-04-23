'use client';

import React, { useState } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Paper,
  Typography,
  IconButton,
  Tooltip,
} from '@mui/material';
import EngineeringIcon from '@mui/icons-material/Engineering';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import EditIcon from '@mui/icons-material/Edit';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import ThinkingDots from './ThinkingDots';
import ToolCallList from './ToolCallList';
import Chip from '@mui/material/Chip';
import { ArchitectChatMessage, StreamingState } from '@/hooks/useArchitectChat';
import MarkdownContent from '@/components/common/MarkdownContent';
import { UserAvatar } from '@/components/common/UserAvatar';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';

interface ArchitectMessageBubbleProps {
  message: ArchitectChatMessage;
  userName?: string;
  userPicture?: string;
  showActions?: boolean;
  showWaitingSpinner?: boolean;
  streamingState?: StreamingState;
  onAccept?: () => void;
  onReject?: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ArchitectMessageBubble({
  message,
  userName,
  userPicture,
  showActions,
  showWaitingSpinner,
  streamingState,
  onAccept,
  onReject,
}: ArchitectMessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const renderedContent = null;

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const formatTime = (date: Date) =>
    date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 1.5,
        mb: 2,
        flexDirection: isUser ? 'row-reverse' : 'row',
        alignItems: 'flex-start',
      }}
    >
      {/* Avatar */}
      {isUser ? (
        <UserAvatar
          userName={userName}
          userPicture={userPicture}
          size={AVATAR_SIZES.MEDIUM}
          sx={{ mt: 0.5 }}
        />
      ) : (
        <Box
          sx={{
            width: AVATAR_SIZES.MEDIUM,
            height: AVATAR_SIZES.MEDIUM,
            borderRadius: theme => theme.shape.circular,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: 'action.selected',
            color: 'text.secondary',
            flexShrink: 0,
            mt: 0.5,
          }}
        >
          {message.isError ? (
            <ErrorOutlineIcon sx={{ fontSize: 18, color: 'error.main' }} />
          ) : (
            <EngineeringIcon sx={{ fontSize: 18 }} />
          )}
        </Box>
      )}

      {/* Message content */}
      <Paper
        elevation={0}
        sx={{
          p: 1.5,
          maxWidth: '75%',
          bgcolor: isUser
            ? 'primary.main'
            : message.isError
              ? 'error.lighter'
              : 'background.paper',
          color: isUser ? 'primary.contrastText' : 'text.primary',
          borderRadius: theme =>
            `${(theme.shape.borderRadius as number) * 2}px`,
          border: isUser ? 'none' : 1,
          borderColor: message.isError ? 'error.light' : 'divider',
          position: 'relative',
          '&:hover .copy-btn': { opacity: 1 },
        }}
      >
        {/* Streaming indicators (thinking + tool calls) */}
        {streamingState && (
          <Box sx={{ mb: message.content ? 1 : 0 }}>
            {streamingState.isThinking && (
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}
              >
                <ThinkingDots size={5} color="text.secondary" />
                <Typography variant="body2" color="text.secondary">
                  Thinking
                  {streamingState.currentIteration
                    ? ` (step ${streamingState.currentIteration})`
                    : ''}
                </Typography>
              </Box>
            )}

            <ToolCallList
              completedTools={streamingState.completedTools}
              activeTools={streamingState.activeTools}
            />
          </Box>
        )}

        {/* Message content */}
        {isUser && renderedContent ? (
          renderedContent
        ) : (
          <MarkdownContent content={message.content} variant="body2" />
        )}

        {/* File attachment chips (user messages) */}
        {isUser && message.files && message.files.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
            {message.files.map(f => (
              <Chip
                key={`${f.filename}-${f.size}`}
                icon={<InsertDriveFileIcon />}
                label={
                  f.size
                    ? `${f.filename} (${formatFileSize(f.size)})`
                    : f.filename
                }
                size="small"
                variant="outlined"
                sx={{
                  borderColor: 'primary.contrastText',
                  color: 'primary.contrastText',
                  '& .MuiChip-icon': { color: 'primary.contrastText' },
                  opacity: 0.85,
                }}
              />
            ))}
          </Box>
        )}

        {/* Footer with time and copy */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mt: 0.5,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography
              variant="caption"
              sx={{
                opacity: 0.6,
                color: isUser ? 'primary.contrastText' : 'text.secondary',
              }}
            >
              {formatTime(message.timestamp)}
            </Typography>
            {showWaitingSpinner && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <CircularProgress
                  size={10}
                  thickness={5}
                  color="inherit"
                  sx={{ opacity: 0.5 }}
                />
                <Typography variant="caption" sx={{ opacity: 0.5 }}>
                  Working…
                </Typography>
              </Box>
            )}
          </Box>
          {!isUser && (
            <Tooltip title={copied ? 'Copied!' : 'Copy'}>
              <IconButton
                className="copy-btn"
                size="small"
                onClick={handleCopy}
                sx={{
                  opacity: 0,
                  transition: 'opacity 0.2s',
                  color: 'text.secondary',
                  p: 0.25,
                }}
              >
                {copied ? (
                  <CheckIcon sx={{ fontSize: 14 }} />
                ) : (
                  <ContentCopyIcon sx={{ fontSize: 14 }} />
                )}
              </IconButton>
            </Tooltip>
          )}
        </Box>

        {/* Accept / Reject actions */}
        {showActions && !isUser && (
          <Box sx={{ display: 'flex', gap: 1, mt: 1.5 }}>
            <Button
              size="small"
              variant="outlined"
              color="success"
              startIcon={<CheckCircleOutlineIcon sx={{ fontSize: 16 }} />}
              onClick={onAccept}
              sx={{ textTransform: 'none', borderRadius: 2, py: 0.25 }}
            >
              Accept
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="inherit"
              startIcon={<EditIcon sx={{ fontSize: 16 }} />}
              onClick={onReject}
              sx={{ textTransform: 'none', borderRadius: 2, py: 0.25 }}
            >
              Change
            </Button>
          </Box>
        )}
      </Paper>
    </Box>
  );
}
