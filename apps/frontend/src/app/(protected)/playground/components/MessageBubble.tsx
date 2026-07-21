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
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';
import DownloadIcon from '@mui/icons-material/Download';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import { TracesIcon } from '@/components/icons';
import { ChatMessage } from '@/hooks/usePlaygroundChat';
import MessageContent from '@/components/common/MessageContent';
import { BORDER_RADIUS } from '@/styles/theme-constants';

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
 * User messages are left-aligned with a teal left-border accent.
 * Assistant messages are right-aligned with a neutral right-border accent,
 * mirroring the Penelope/Target layout used in ConversationHistory.
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

  const formatTime = (date: Date) =>
    date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

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
        // user → left edge; assistant → right edge
        alignItems: isUser ? 'flex-start' : 'flex-end',
        mb: 2.5,
      }}
    >
      {/* Row: avatar + card (reversed for assistant so avatar stays outside) */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          flexDirection: isUser ? 'row' : 'row-reverse',
          gap: 1.5,
          maxWidth: '85%',
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
                : theme => theme.palette.greyscale.surface2,
            color: isUser
              ? 'primary.contrastText'
              : message.isError
                ? 'error.contrastText'
                : theme => theme.palette.greyscale.body,
            flexShrink: 0,
            mt: 0.25,
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

        {/* Card — user gets teal left accent, assistant gets neutral right accent */}
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
              borderRadius: BORDER_RADIUS.sm,
              bgcolor: message.isError
                ? 'error.light'
                : isUser
                  ? 'background.paper'
                  : theme => theme.palette.greyscale.surface1,
              color: message.isError
                ? 'error.contrastText'
                : theme => theme.palette.greyscale.body,
              border: theme => `1px solid ${theme.palette.greyscale.border}`,
              ...(isUser
                ? {
                    borderLeft: theme =>
                      `3px solid ${message.isError ? theme.palette.error.main : theme.palette.primary.main}`,
                  }
                : {
                    borderRight: theme =>
                      `3px solid ${message.isError ? theme.palette.error.main : theme.palette.greyscale.border}`,
                  }),
              ...(hasTrace && {
                cursor: 'pointer',
                transition: theme =>
                  theme.transitions.create(['background-color', 'box-shadow'], {
                    duration: theme.transitions.duration.short,
                  }),
                '&:hover': {
                  bgcolor: theme => theme.palette.greyscale.surface2,
                  boxShadow: 1,
                },
              }),
            }}
          >
            {/* Message text + inline actions */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'flex-end',
                justifyContent: 'space-between',
                gap: 1,
              }}
            >
              <Box sx={{ flex: 1, minWidth: 0 }}>
                {isUser ? (
                  <Typography
                    variant="body2"
                    sx={{
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      color: theme => theme.palette.greyscale.body,
                    }}
                  >
                    {message.content}
                  </Typography>
                ) : (
                  <MessageContent content={message.content} variant="body2" />
                )}
              </Box>

              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  flexShrink: 0,
                  alignSelf: 'flex-end',
                }}
              >
                {/* Create single-turn test (user messages) */}
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
                        color: theme => theme.palette.greyscale.label,
                        '&:hover': {
                          color: 'primary.main',
                          bgcolor: theme => theme.palette.background.light1,
                        },
                      }}
                    >
                      <ScienceOutlinedIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Tooltip>
                )}

                {/* Copy (assistant messages) */}
                {!isUser && !message.isError && (
                  <Tooltip title={copied ? 'Copied!' : 'Copy message'}>
                    <IconButton
                      size="small"
                      onClick={handleCopy}
                      sx={{
                        p: 0.5,
                        color: theme => theme.palette.greyscale.label,
                        '&:hover': {
                          color: 'primary.main',
                          bgcolor: theme => theme.palette.greyscale.surface2,
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

                {/* Trace link (assistant messages with trace) */}
                {hasTrace && (
                  <Tooltip title="View trace">
                    <IconButton
                      size="small"
                      onClick={e => {
                        e.stopPropagation();
                        if (onViewTrace && message.traceId) {
                          onViewTrace(message.traceId);
                        }
                      }}
                      sx={{
                        p: 0.5,
                        color: theme => theme.palette.greyscale.label,
                        '&:hover': {
                          color: 'primary.main',
                          bgcolor: theme => theme.palette.greyscale.surface2,
                        },
                      }}
                    >
                      <TracesIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>
            </Box>

            {/* User: attached file chips */}
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
                  />
                ))}
              </Box>
            )}

            {/* Assistant: output files */}
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
                          sx={{
                            color: theme => theme.palette.greyscale.subtitle,
                          }}
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

      {/* Timestamp — stays under the card on the correct side */}
      <Typography
        variant="caption"
        sx={{
          mt: 0.5,
          ...(isUser ? { ml: 5.5 } : { mr: 5.5 }),
          color: theme => theme.palette.greyscale.subtitle,
        }}
      >
        {formatTime(message.timestamp)}
      </Typography>
    </Box>
  );
}

/**
 * Loading skeleton for the assistant's pending response (right-aligned).
 */
export function MessageBubbleSkeleton() {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'flex-start',
        gap: 1.5,
        mb: 2.5,
      }}
    >
      <Box sx={{ flex: 1, maxWidth: '60%' }}>
        <Skeleton
          variant="rounded"
          sx={{
            height: theme => theme.spacing(7.5),
            borderRadius: BORDER_RADIUS.sm,
          }}
        />
      </Box>
      <Skeleton
        variant="circular"
        sx={{
          width: theme => theme.spacing(4),
          height: theme => theme.spacing(4),
          flexShrink: 0,
        }}
      />
    </Box>
  );
}
