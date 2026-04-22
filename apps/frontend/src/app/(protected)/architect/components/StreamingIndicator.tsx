'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { StreamingState } from '@/hooks/useArchitectChat';
import ThinkingDots from './ThinkingDots';
import ToolCallList from './ToolCallList';

interface StreamingIndicatorProps {
  state: StreamingState;
}

export default function StreamingIndicator({ state }: StreamingIndicatorProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        gap: 1.5,
        mb: 2,
        alignItems: 'flex-start',
      }}
    >
      {/* Avatar */}
      <Box
        sx={{
          width: 32,
          height: 32,
          borderRadius: (theme) => theme.shape.circular,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'action.selected',
          color: 'text.secondary',
          flexShrink: 0,
          mt: 0.5,
        }}
      >
        <SmartToyIcon sx={{ fontSize: 18 }} />
      </Box>

      {/* Streaming content */}
      <Box
        sx={{
          p: 1.5,
          maxWidth: '75%',
          bgcolor: 'background.paper',
          borderRadius: (theme) => theme.shape.borderRadius * 2,
          border: 1,
          borderColor: 'divider',
        }}
      >
        {/* Thinking indicator */}
        {state.isThinking && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <ThinkingDots size={5} color="text.secondary" />
            <Typography variant="body2" color="text.secondary">
              Thinking
              {state.currentIteration
                ? ` (step ${state.currentIteration})`
                : ''}
            </Typography>
          </Box>
        )}

        <ToolCallList
          completedTools={state.completedTools}
          activeTools={state.activeTools}
        />
      </Box>
    </Box>
  );
}
