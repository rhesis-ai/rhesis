'use client';

import React, { useState } from 'react';
import { Box, Button, Paper, Typography, IconButton, Tooltip } from '@mui/material';
import ArchitectureIcon from '@mui/icons-material/Architecture';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import EditIcon from '@mui/icons-material/Edit';
import { ArchitectChatMessage } from '@/hooks/useArchitectChat';
import MarkdownContent from '@/components/common/MarkdownContent';
import { UserAvatar } from '@/components/common/UserAvatar';
import { AVATAR_SIZES } from '@/constants/avatar-sizes';

interface ArchitectMessageBubbleProps {
  message: ArchitectChatMessage;
  userName?: string;
  userPicture?: string;
  showActions?: boolean;
  onAccept?: () => void;
  onReject?: () => void;
}

export default function ArchitectMessageBubble({
  message,
  userName,
  userPicture,
  showActions,
  onAccept,
  onReject,
}: ArchitectMessageBubbleProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

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
            borderRadius: '50%',
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
            <ArchitectureIcon sx={{ fontSize: 18 }} />
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
          borderRadius: 2,
          border: isUser ? 'none' : 1,
          borderColor: message.isError ? 'error.light' : 'divider',
          position: 'relative',
          '&:hover .copy-btn': { opacity: 1 },
        }}
      >
        <MarkdownContent content={message.content} variant="body2" />

        {/* Footer with time and copy */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mt: 0.5,
          }}
        >
          <Typography
            variant="caption"
            sx={{
              opacity: 0.6,
              color: isUser ? 'primary.contrastText' : 'text.secondary',
            }}
          >
            {formatTime(message.timestamp)}
          </Typography>
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
