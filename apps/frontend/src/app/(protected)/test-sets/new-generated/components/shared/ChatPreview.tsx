'use client';

import React from 'react';
import { Box, Paper, Typography } from '@mui/material';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatPreviewProps {
  messages: ChatMessage[];
}

/**
 * ChatPreview Component
 * Visual representation of chat messages for single-turn vs multi-turn distinction
 */
export default function ChatPreview({ messages }: ChatPreviewProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        p: 2,
        bgcolor: theme =>
          theme.palette.mode === 'dark' ? 'background.default' : 'grey.50',
        borderRadius: theme => theme.shape.borderRadius,
        minHeight: '400px',
      }}
    >
      {messages.map((message, index) => {
        const isLeft = index % 2 === 0;
        // Create a stable key from role, index, and a hash of content
        const messageKey = `${message.role}-${index}-${message.content.substring(0, 20)}`;
        return (
          <Box
            key={messageKey}
            sx={{
              display: 'flex',
              justifyContent: isLeft ? 'flex-start' : 'flex-end',
            }}
          >
            <Paper
              elevation={0}
              sx={{
                px: 2,
                py: 1,
                maxWidth: '80%',
                bgcolor:
                  message.role === 'user'
                    ? 'primary.main'
                    : 'background.light3',
                color:
                  message.role === 'user'
                    ? 'primary.contrastText'
                    : 'text.primary',
                borderRadius: theme => theme.shape.borderRadius,
                ...(isLeft && {
                  borderBottomLeftRadius: 4,
                }),
                ...(!isLeft && {
                  borderBottomRightRadius: 4,
                }),
                ...(message.role === 'assistant' && {
                  border: '1px solid',
                  borderColor: 'divider',
                }),
              }}
            >
              <Typography variant="caption" sx={{ lineHeight: 1.4 }}>
                {message.content}
              </Typography>
            </Paper>
          </Box>
        );
      })}
    </Box>
  );
}
