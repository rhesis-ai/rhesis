'use client';

import React from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Tooltip,
  Skeleton,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import TimelineIcon from '@mui/icons-material/Timeline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { ChatMessage } from '@/hooks/usePlaygroundChat';

interface MessageBubbleProps {
  /** The chat message to display */
  message: ChatMessage;
  /** Callback when the trace icon is clicked (for assistant messages with traces) */
  onViewTrace?: (traceId: string) => void;
}

/**
 * MessageBubble Component
 *
 * Displays a single chat message in a bubble format.
 * User messages appear on the right, assistant messages on the left.
 */
export default function MessageBubble({
  message,
  onViewTrace,
}: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const hasTrace = !isUser && message.traceId && !message.isError;

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        mb: 2,
      }}
    >
      {/* Message Content */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 1,
          maxWidth: '80%',
          flexDirection: isUser ? 'row-reverse' : 'row',
        }}
      >
        {/* Avatar */}
        <Box
          sx={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: isUser
              ? 'primary.main'
              : message.isError
                ? 'error.light'
                : 'action.hover',
            color: isUser
              ? 'primary.contrastText'
              : message.isError
                ? 'error.contrastText'
                : 'text.secondary',
            flexShrink: 0,
          }}
        >
          {isUser ? (
            <PersonIcon fontSize="small" />
          ) : message.isError ? (
            <ErrorOutlineIcon fontSize="small" />
          ) : (
            <SmartToyIcon fontSize="small" />
          )}
        </Box>

        {/* Bubble */}
        <Paper
          elevation={0}
          sx={{
            p: 2,
            borderRadius: 2,
            bgcolor: isUser
              ? 'primary.main'
              : message.isError
                ? 'error.light'
                : 'action.hover',
            color: isUser
              ? 'primary.contrastText'
              : message.isError
                ? 'error.contrastText'
                : 'text.primary',
            borderTopRightRadius: isUser ? 0 : 2,
            borderTopLeftRadius: isUser ? 2 : 0,
          }}
        >
          <Typography
            variant="body2"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {message.content}
          </Typography>
        </Paper>

        {/* Trace Button (for assistant messages with traces) */}
        {hasTrace && onViewTrace && (
          <Tooltip title="View trace details">
            <IconButton
              size="small"
              onClick={() => onViewTrace(message.traceId!)}
              sx={{
                alignSelf: 'center',
                color: 'text.secondary',
                '&:hover': {
                  color: 'primary.main',
                },
              }}
            >
              <TimelineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>

      {/* Timestamp */}
      <Typography
        variant="caption"
        color="text.disabled"
        sx={{
          mt: 0.5,
          mx: 5,
        }}
      >
        {formatTime(message.timestamp)}
      </Typography>
    </Box>
  );
}

/**
 * Loading skeleton for message bubble.
 */
export function MessageBubbleSkeleton() {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1,
        mb: 2,
      }}
    >
      <Skeleton variant="circular" width={32} height={32} />
      <Box sx={{ flex: 1, maxWidth: '60%' }}>
        <Skeleton
          variant="rounded"
          height={60}
          sx={{
            borderRadius: 2,
            borderTopLeftRadius: 0,
          }}
        />
      </Box>
    </Box>
  );
}
