'use client';

import React from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Chip,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { StreamingState } from '@/hooks/useArchitectChat';

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
        <SmartToyIcon sx={{ fontSize: 18 }} />
      </Box>

      {/* Streaming content */}
      <Box
        sx={{
          p: 1.5,
          maxWidth: '75%',
          bgcolor: 'background.paper',
          borderRadius: 2,
          border: 1,
          borderColor: 'divider',
        }}
      >
        {/* Thinking indicator */}
        {state.isThinking && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <CircularProgress size={14} />
            <Typography variant="body2" color="text.secondary">
              Thinking
              {state.currentIteration
                ? ` (step ${state.currentIteration})`
                : '...'}
            </Typography>
          </Box>
        )}

        {/* Active tool calls */}
        {state.activeTools.map((tool, i) => (
          <Box
            key={`active-${tool.tool}-${i}`}
            sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}
          >
            <CircularProgress size={12} />
            <Chip
              label={tool.tool}
              size="small"
              variant="outlined"
              color="primary"
            />
          </Box>
        ))}

        {/* Completed tool calls */}
        {state.completedTools.map((tool, i) => (
          <Box
            key={`done-${tool.tool}-${i}`}
            sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}
          >
            {tool.success ? (
              <CheckCircleIcon
                sx={{ fontSize: 14, color: 'success.main' }}
              />
            ) : (
              <ErrorIcon sx={{ fontSize: 14, color: 'error.main' }} />
            )}
            <Chip
              label={tool.tool}
              size="small"
              variant="outlined"
              color={tool.success ? 'success' : 'error'}
            />
          </Box>
        ))}
      </Box>
    </Box>
  );
}
