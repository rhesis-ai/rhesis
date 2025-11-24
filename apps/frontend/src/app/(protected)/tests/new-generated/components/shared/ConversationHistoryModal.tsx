'use client';

import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Box,
  Typography,
  Collapse,
  Button,
  Chip,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ConversationHistory from '@/components/common/ConversationHistory';
import { ConversationTurn } from '@/utils/api-client/interfaces/test-results';
import { MultiTurnPrompt } from './types';

interface ConversationHistoryModalProps {
  open: boolean;
  onClose: () => void;
  conversationSummary: ConversationTurn[];
  testConfiguration: MultiTurnPrompt;
  behavior?: string;
  topic?: string;
  category?: string;
}

/**
 * ConversationHistoryModal Component
 * Modal wrapper for displaying multi-turn conversation history with test configuration
 */
export default function ConversationHistoryModal({
  open,
  onClose,
  conversationSummary,
  testConfiguration,
  behavior,
  topic,
  category,
}: ConversationHistoryModalProps) {
  const [expandedDetails, setExpandedDetails] = React.useState(false);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          maxHeight: '90vh',
          height: '90vh',
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 1,
        }}
      >
        <Box>
          <Typography variant="h6">Conversation History</Typography>
          <Typography variant="body2" color="text.secondary">
            Multi-turn test simulation result
          </Typography>
        </Box>
        <IconButton edge="end" onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ p: 0, display: 'flex', flexDirection: 'column' }}>
        {/* Test Configuration Section */}
        <Box
          sx={{
            p: 2,
            borderBottom: 1,
            borderColor: 'divider',
            bgcolor: 'background.light2',
          }}
        >
          {/* Metadata Chips */}
          {(behavior || topic || category) && (
            <Box sx={{ display: 'flex', gap: 0.5, mb: 1.5 }}>
              {behavior && (
                <Chip
                  label={behavior}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
              )}
              {topic && <Chip label={topic} size="small" variant="outlined" />}
              {category && (
                <Chip
                  label={category}
                  size="small"
                  color="secondary"
                  variant="outlined"
                />
              )}
            </Box>
          )}

          {/* Goal - Always Visible */}
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}
          >
            Goal:
          </Typography>
          <Typography
            variant="body2"
            sx={{
              mb: 1,
              fontStyle: 'italic',
            }}
          >
            {testConfiguration.goal}
          </Typography>

          {/* Expand/Collapse Button */}
          <Button
            size="small"
            onClick={() => setExpandedDetails(!expandedDetails)}
            endIcon={expandedDetails ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            sx={{
              textTransform: 'none',
              fontSize: theme => theme.typography.caption.fontSize,
              color: 'text.secondary',
              p: 0,
              minWidth: 'auto',
              '&:hover': {
                bgcolor: 'transparent',
                color: 'primary.main',
              },
            }}
          >
            {expandedDetails ? 'Hide details' : 'Show details'}
          </Button>

          {/* Collapsible Details Section */}
          <Collapse in={expandedDetails}>
            <Box
              sx={{
                mt: 1.5,
                pt: 1.5,
                borderTop: 1,
                borderColor: 'divider',
              }}
            >
              {/* Instructions */}
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}
              >
                Instructions:
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  mb: 1.5,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {testConfiguration.instructions}
              </Typography>

              {/* Scenario */}
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}
              >
                Scenario:
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  mb: 1.5,
                  fontStyle: 'italic',
                }}
              >
                {testConfiguration.scenario}
              </Typography>

              {/* Restrictions */}
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontWeight: 'bold', display: 'block', mb: 0.5 }}
              >
                Restrictions:
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  whiteSpace: 'pre-wrap',
                }}
              >
                {testConfiguration.restrictions}
              </Typography>
            </Box>
          </Collapse>
        </Box>

        {/* Conversation History - fills remaining space */}
        <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
          <ConversationHistory
            conversationSummary={conversationSummary}
            maxHeight="100%"
          />
        </Box>
      </DialogContent>
    </Dialog>
  );
}
