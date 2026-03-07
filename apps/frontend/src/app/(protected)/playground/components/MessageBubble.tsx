'use client';

/* eslint-disable react/no-array-index-key -- file attachment lists are display-only and have no stable IDs */

import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Tooltip,
  Skeleton,
  IconButton,
  Chip,
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import TimelineIcon from '@mui/icons-material/Timeline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';
import DownloadIcon from '@mui/icons-material/Download';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import { ChatMessage } from '@/hooks/usePlaygroundChat';
import MarkdownContent from '@/components/common/MarkdownContent';

interface MessageBubbleProps {
  /** The chat message to display */
  message: ChatMessage;
  /** Callback when the trace icon is clicked (for assistant messages with traces) */
  onViewTrace?: (traceId: string) => void;
  /** Callback to create a single-turn test from this user message */
  onCreateSingleTurnTest?: (messageId: string) => void;
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
  onCreateSingleTurnTest,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);

  const isUser = message.role === 'user';
  const hasTrace = !isUser && message.traceId && !message.isError;

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleDownloadFile = (
    filename: string,
    contentType: string,
    contentBase64: string
  ) => {
    const link = document.createElement('a');
    link.href = `data:${contentType};base64,${contentBase64}`;
    link.download = filename;
    link.click();
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
            width: theme => theme.spacing(4),
            height: theme => theme.spacing(4),
            borderRadius: theme => theme.shape.circular,
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
        <Tooltip
          title={hasTrace ? 'Click to view trace details' : ''}
          placement="top"
          disableHoverListener={!hasTrace}
        >
          <Paper
            elevation={0}
            onClick={
              hasTrace && onViewTrace && message.traceId
                ? () => onViewTrace(message.traceId as string)
                : undefined
            }
            sx={{
              p: 2,
              borderRadius: theme => theme.shape.borderRadius * 0.5,
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
              ...(hasTrace && {
                cursor: 'pointer',
                transition: theme =>
                  theme.transitions.create(['background-color', 'box-shadow'], {
                    duration: theme.transitions.duration.short,
                  }),
                '&:hover': {
                  bgcolor: 'action.selected',
                  boxShadow: 1,
                },
              }),
            }}
          >
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
              }}
            >
              <Box sx={{ flex: 1, minWidth: 0 }}>
                {isUser ? (
                  // User messages: plain text with pre-wrap
                  <Typography
                    variant="body2"
                    sx={{
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {message.content}
                  </Typography>
                ) : (
                  // Assistant messages: render markdown with same variant as user text
                  <MarkdownContent content={message.content} variant="body2" />
                )}
              </Box>

              {/* Action icons */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  flexShrink: 0,
                  ml: 1,
                }}
              >
                {/* Create single-turn test button (user messages only) */}
                {isUser && (
                  <Tooltip title="Create single-turn test from this message">
                    <IconButton
                      size="small"
                      onClick={e => {
                        e.stopPropagation();
                        onCreateSingleTurnTest?.(message.id);
                      }}
                      sx={{
                        p: 0.5,
                        color: 'primary.contrastText',
                        opacity: 0.7,
                        '&:hover': {
                          opacity: 1,
                          bgcolor: 'primary.dark',
                        },
                      }}
                    >
                      <ScienceOutlinedIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Tooltip>
                )}

                {/* Copy button (assistant messages only) */}
                {!isUser && (
                  <Tooltip title={copied ? 'Copied!' : 'Copy message'}>
                    <IconButton
                      size="small"
                      onClick={handleCopy}
                      sx={{
                        p: 0.5,
                        color: 'action.active',
                        opacity: 0.7,
                        '&:hover': {
                          opacity: 1,
                          bgcolor: 'action.hover',
                        },
                      }}
                    >
                      {copied ? (
                        <CheckIcon sx={{ fontSize: 16 }} />
                      ) : (
                        <ContentCopyIcon sx={{ fontSize: 16 }} />
                      )}
                    </IconButton>
                  </Tooltip>
                )}

                {/* Trace Icon indicator (for assistant messages with traces) */}
                {hasTrace && (
                  <Tooltip title="View trace">
                    <TimelineIcon
                      sx={{
                        fontSize: 18,
                        color: 'action.active',
                      }}
                    />
                  </Tooltip>
                )}
              </Box>
            </Box>

            {/* User message: show attached file names (clickable for download) */}
            {isUser && message.files && message.files.length > 0 && (
              <Box
                sx={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 0.5,
                  mt: 1,
                }}
              >
                {message.files.map((file, idx) => (
                  <Chip
                    key={`${file.filename}-${idx}`}
                    icon={<DownloadIcon />}
                    label={file.filename}
                    size="small"
                    variant="outlined"
                    clickable
                    onClick={e => {
                      e.stopPropagation();
                      handleDownloadFile(
                        file.filename,
                        file.content_type,
                        file.data
                      );
                    }}
                    sx={{
                      color: 'primary.contrastText',
                      borderColor: 'primary.contrastText',
                      '& .MuiChip-icon': {
                        color: 'primary.contrastText',
                      },
                      opacity: 0.85,
                    }}
                  />
                ))}
              </Box>
            )}

            {/* Assistant message: show output files */}
            {!isUser &&
              message.outputFiles &&
              message.outputFiles.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  {message.outputFiles.map((file, idx) =>
                    file.content_type.startsWith('image/') ? (
                      <Box
                        key={`${file.filename}-${idx}`}
                        sx={{
                          mt: 1,
                          cursor: 'pointer',
                          '&:hover': { opacity: 0.85 },
                        }}
                        onClick={e => {
                          e.stopPropagation();
                          handleDownloadFile(
                            file.filename,
                            file.content_type,
                            file.data
                          );
                        }}
                      >
                        <Tooltip title={`Download ${file.filename}`}>
                          <Box
                            component="img"
                            src={`data:${file.content_type};base64,${file.data}`}
                            alt={file.filename}
                            sx={{
                              maxWidth: '100%',
                              maxHeight: theme => theme.spacing(37.5),
                              borderRadius: theme =>
                                `${theme.shape.borderRadius}px`,
                            }}
                          />
                        </Tooltip>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          display="block"
                        >
                          {file.filename}
                        </Typography>
                      </Box>
                    ) : (
                      <Chip
                        key={`${file.filename}-${idx}`}
                        icon={<DownloadIcon />}
                        label={file.filename}
                        size="small"
                        variant="outlined"
                        clickable
                        onClick={e => {
                          e.stopPropagation();
                          handleDownloadFile(
                            file.filename,
                            file.content_type,
                            file.data
                          );
                        }}
                        sx={{ mr: 0.5, mt: 0.5 }}
                      />
                    )
                  )}
                </Box>
              )}
          </Paper>
        </Tooltip>
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
      <Skeleton
        variant="circular"
        sx={{
          width: theme => theme.spacing(4),
          height: theme => theme.spacing(4),
        }}
      />
      <Box sx={{ flex: 1, maxWidth: '60%' }}>
        <Skeleton
          variant="rounded"
          sx={{
            height: theme => theme.spacing(7.5),
            borderRadius: theme => theme.shape.borderRadius * 0.5,
            borderTopLeftRadius: 0,
          }}
        />
      </Box>
    </Box>
  );
}
