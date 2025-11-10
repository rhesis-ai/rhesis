'use client';

import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  useTheme,
  alpha,
  Divider,
  Collapse,
  IconButton,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { ConversationTurn } from '@/utils/api-client/interfaces/test-results';
import StatusChip from '@/components/common/StatusChip';

interface ConversationHistoryProps {
  conversationSummary: ConversationTurn[];
  maxHeight?: number | string;
}

/**
 * ConversationHistory Component
 * Displays multi-turn conversation between Penelope (agent) and Target (endpoint)
 * in a chat-bubble style interface.
 */
export default function ConversationHistory({
  conversationSummary,
  maxHeight = 600,
}: ConversationHistoryProps) {
  const theme = useTheme();

  // Track expanded state for each turn's reasoning
  const [expandedTurns, setExpandedTurns] = useState<Record<number, boolean>>(
    {}
  );

  const toggleReasoning = (turnNumber: number) => {
    setExpandedTurns(prev => ({
      ...prev,
      [turnNumber]: !prev[turnNumber],
    }));
  };

  if (!conversationSummary || conversationSummary.length === 0) {
    return (
      <Box
        sx={{
          p: 3,
          textAlign: 'center',
          color: 'text.secondary',
        }}
      >
        <Typography variant="body2">
          No conversation history available
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        maxHeight,
        height: maxHeight === '100%' ? '100%' : 'auto',
        overflow: 'auto',
        p: 2,
        bgcolor: theme.palette.background.default,
        borderRadius: 1,
        flex: maxHeight === '100%' ? 1 : 'none',
        '&::-webkit-scrollbar': {
          width: '8px',
        },
        '&::-webkit-scrollbar-track': {
          background: theme.palette.background.default,
          borderRadius: '4px',
        },
        '&::-webkit-scrollbar-thumb': {
          background: theme.palette.divider,
          borderRadius: '4px',
          '&:hover': {
            background: theme.palette.action.hover,
          },
        },
      }}
    >
      {/* Conversation Initialized Marker */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          mb: 3,
          py: 2,
        }}
      >
        <Chip
          label="Conversation Initialized"
          size="small"
          sx={{
            bgcolor: alpha(theme.palette.success.main, 0.1),
            color: theme.palette.success.main,
            fontWeight: 500,
            border: `1px solid ${alpha(theme.palette.success.main, 0.3)}`,
          }}
        />
      </Box>

      {conversationSummary.map((turn, index) => (
        <Box key={turn.turn} sx={{ mb: 3 }}>
          {/* Turn Header */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              mb: 2,
            }}
          >
            <Chip
              label={`Turn ${turn.turn}`}
              size="small"
              color="primary"
              variant="outlined"
            />

            {/* Result Status Chip */}
            <StatusChip
              status={turn.success ? 'Pass' : 'Fail'}
              label={turn.success ? 'Passed' : 'Failed'}
              size="small"
              variant="filled"
            />

            {/* Collapsible Reasoning Toggle */}
            {turn.penelope_reasoning && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  cursor: 'pointer',
                  '&:hover': { opacity: 0.7 },
                }}
                onClick={() => toggleReasoning(turn.turn)}
              >
                <Typography
                  variant="caption"
                  sx={{
                    color: theme.palette.info.main,
                    fontWeight: 500,
                    fontSize: '0.75rem',
                  }}
                >
                  {expandedTurns[turn.turn] ? 'Hide' : 'Show'} Reasoning
                </Typography>
                <IconButton
                  size="small"
                  sx={{
                    padding: 0,
                    transform: expandedTurns[turn.turn]
                      ? 'rotate(180deg)'
                      : 'rotate(0deg)',
                    transition: 'transform 0.2s',
                  }}
                >
                  <ExpandMoreIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Box>
            )}
          </Box>

          {/* Penelope's Reasoning (collapsible) */}
          {turn.penelope_reasoning && (
            <Collapse
              in={expandedTurns[turn.turn]}
              timeout="auto"
              unmountOnExit
            >
              <Paper
                elevation={0}
                sx={{
                  p: 1.5,
                  mb: 1.5,
                  bgcolor: alpha(theme.palette.info.main, 0.05),
                  border: `1px solid ${alpha(theme.palette.info.main, 0.2)}`,
                }}
              >
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}
                >
                  Reasoning
                </Typography>
                <Typography
                  variant="body2"
                  sx={{
                    fontSize: '0.875rem',
                    fontStyle: 'italic',
                    color: 'text.secondary',
                  }}
                >
                  {turn.penelope_reasoning}
                </Typography>
              </Paper>
            </Collapse>
          )}

          {/* Penelope's Message (Left - Agent) */}
          <Box
            sx={{
              display: 'flex',
              gap: 1,
              mb: 1.5,
              alignItems: 'flex-start',
            }}
          >
            <SmartToyIcon
              sx={{
                fontSize: 20,
                color: theme.palette.primary.main,
                mt: 0.5,
              }}
            />
            <Paper
              elevation={1}
              sx={{
                p: 2,
                maxWidth: '85%',
                bgcolor: alpha(theme.palette.primary.main, 0.08),
                border: `1px solid ${alpha(theme.palette.primary.main, 0.2)}`,
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  fontWeight: 600,
                  color: theme.palette.primary.main,
                  display: 'block',
                  mb: 0.5,
                }}
              >
                Penelope
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {turn.penelope_message}
              </Typography>
            </Paper>
          </Box>

          {/* Target's Response (Right - Endpoint) */}
          <Box
            sx={{
              display: 'flex',
              gap: 1,
              justifyContent: 'flex-end',
              alignItems: 'flex-start',
            }}
          >
            <Paper
              elevation={1}
              sx={{
                p: 2,
                maxWidth: '85%',
                bgcolor: alpha(theme.palette.secondary.main, 0.08),
                border: `1px solid ${alpha(theme.palette.secondary.main, 0.2)}`,
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  fontWeight: 600,
                  color: theme.palette.secondary.main,
                  display: 'block',
                  mb: 0.5,
                }}
              >
                Target
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {turn.target_response}
              </Typography>
            </Paper>
            <AccountCircleIcon
              sx={{
                fontSize: 20,
                color: theme.palette.secondary.main,
                mt: 0.5,
              }}
            />
          </Box>

          {/* Divider between turns (except last) */}
          {index < conversationSummary.length - 1 && <Divider sx={{ mt: 3 }} />}
        </Box>
      ))}

      {/* Conversation Concluded Marker */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          mt: 3,
          py: 2,
        }}
      >
        <Chip
          label="Conversation Concluded"
          size="small"
          sx={{
            bgcolor: alpha(theme.palette.info.main, 0.1),
            color: theme.palette.info.main,
            fontWeight: 500,
            border: `1px solid ${alpha(theme.palette.info.main, 0.3)}`,
          }}
        />
      </Box>
    </Box>
  );
}
