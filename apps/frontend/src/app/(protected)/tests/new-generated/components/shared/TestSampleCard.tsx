'use client';

import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Box,
  Paper,
  Typography,
  TextField,
  IconButton,
  Chip,
  Fade,
  Button,
  Collapse,
} from '@mui/material';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import ThumbUpOutlinedIcon from '@mui/icons-material/ThumbUpOutlined';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';
import ThumbDownOutlinedIcon from '@mui/icons-material/ThumbDownOutlined';
import SendIcon from '@mui/icons-material/Send';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import CircularProgress from '@mui/material/CircularProgress';
import { AnyTestSample } from './types';
import ContextPreview from './ContextPreview';

interface TestSampleCardProps {
  sample: AnyTestSample;
  onRate: (sampleId: string, rating: number) => void;
  onFeedbackChange: (sampleId: string, feedback: string) => void;
  onRegenerate?: (sampleId: string, feedback: string) => void;
  isRegenerating?: boolean;
}

/**
 * TestSampleCard Component
 * Displays a test sample in a chat-like layout with rating functionality
 */
export default function TestSampleCard({
  sample,
  onRate,
  onFeedbackChange,
  onRegenerate,
  isRegenerating = false,
}: TestSampleCardProps) {
  const [showFeedback, setShowFeedback] = useState(
    sample.rating === 1 || Boolean(sample.feedback)
  );
  const [localFeedback, setLocalFeedback] = useState(sample.feedback);
  const [expandedDetails, setExpandedDetails] = useState(false);

  const handleThumbsUp = () => {
    // Toggle: if already rated 5, set to 0 (unrated), otherwise set to 5
    const newRating = sample.rating === 5 ? 0 : 5;
    onRate(sample.id, newRating);
    setShowFeedback(false);
  };

  const handleThumbsDown = () => {
    // Toggle: if already rated 1, set to 0 (unrated), otherwise set to 1
    const newRating = sample.rating === 1 ? 0 : 1;
    onRate(sample.id, newRating);
    if (newRating === 1) {
      setShowFeedback(true);
    } else {
      setShowFeedback(false);
    }
  };

  const handleSendFeedback = () => {
    if (localFeedback.trim() && onRegenerate) {
      onFeedbackChange(sample.id, localFeedback);
      onRegenerate(sample.id, localFeedback);
    }
  };

  const isPositive = sample.rating === 5;
  const isNegative = sample.rating === 1;

  // Determine what to display based on test type
  const displayText =
    sample.testType === 'multi_turn' ? sample.prompt.goal : sample.prompt;

  return (
    <Card
      elevation={0}
      sx={{
        mb: 2,
        borderRadius: theme => theme.shape.borderRadius,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        position: 'relative',
        opacity: isRegenerating ? 0.6 : 1,
      }}
    >
      {isRegenerating && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: 'background.paper',
            opacity: 0.95,
            zIndex: 1,
            borderRadius: theme => theme.shape.borderRadius,
          }}
        >
          <CircularProgress sx={{ mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            Regenerating sample...
          </Typography>
        </Box>
      )}
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          {/* Main Content */}
          <Box sx={{ flex: 1 }}>
            {/* Metadata Chips */}
            <Box
              sx={{ display: 'flex', gap: 0.5, mb: 1.5, alignItems: 'center' }}
            >
              <Chip
                label={sample.behavior}
                size="small"
                color="primary"
                variant="outlined"
              />
              <Chip label={sample.topic} size="small" variant="outlined" />
              {sample.testType === 'multi_turn' && (
                <Chip
                  label={sample.category}
                  size="small"
                  color="secondary"
                  variant="outlined"
                />
              )}
              <ContextPreview context={sample.context} />
            </Box>

            {/* Display Text (Prompt or Goal depending on test type) */}
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'flex-start',
                mb:
                  sample.response ||
                  sample.isLoadingResponse ||
                  sample.responseError
                    ? 1
                    : 0,
              }}
            >
              <Paper
                elevation={0}
                sx={{
                  maxWidth: '80%',
                  bgcolor: 'background.light2',
                  borderRadius: theme => theme.shape.borderRadius,
                  px: 1.5,
                  py: 1,
                }}
              >
                {sample.testType === 'multi_turn' ? (
                  <Box>
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
                        fontStyle: 'italic',
                        color: theme =>
                          theme.palette.mode === 'dark'
                            ? 'primary.contrastText'
                            : 'text.primary',
                      }}
                    >
                      {sample.prompt.goal}
                    </Typography>

                    {/* Expand/Collapse Button */}
                    <Button
                      size="small"
                      onClick={() => setExpandedDetails(!expandedDetails)}
                      endIcon={
                        expandedDetails ? (
                          <ExpandLessIcon />
                        ) : (
                          <ExpandMoreIcon />
                        )
                      }
                      sx={{
                        mt: 1,
                        textTransform: 'none',
                        fontSize: '0.75rem',
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
                            color: theme =>
                              theme.palette.mode === 'dark'
                                ? 'primary.contrastText'
                                : 'text.primary',
                          }}
                        >
                          {sample.prompt.instructions}
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
                            color: theme =>
                              theme.palette.mode === 'dark'
                                ? 'primary.contrastText'
                                : 'text.primary',
                          }}
                        >
                          {sample.prompt.scenario}
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
                            color: theme =>
                              theme.palette.mode === 'dark'
                                ? 'primary.contrastText'
                                : 'text.primary',
                          }}
                        >
                          {sample.prompt.restrictions}
                        </Typography>
                      </Box>
                    </Collapse>
                  </Box>
                ) : (
                  <Typography
                    variant="body2"
                    sx={{
                      fontStyle: 'italic',
                      color: theme =>
                        theme.palette.mode === 'dark'
                          ? 'primary.contrastText'
                          : 'text.primary',
                    }}
                  >
                    {displayText}
                  </Typography>
                )}
              </Paper>
            </Box>

            {/* Response (Right-aligned) - if present or loading */}
            {(sample.response ||
              sample.isLoadingResponse ||
              sample.responseError) && (
              <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Paper
                  elevation={0}
                  sx={{
                    maxWidth: '80%',
                    border: 1,
                    borderColor: sample.responseError
                      ? 'error.main'
                      : 'divider',
                    borderRadius: theme => theme.shape.borderRadius,
                    px: 1.5,
                    py: 1,
                    bgcolor: sample.responseError
                      ? 'error.lighter'
                      : 'background.paper',
                  }}
                >
                  {sample.isLoadingResponse ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CircularProgress size={16} />
                      <Typography variant="body2" color="text.secondary">
                        Loading response...
                      </Typography>
                    </Box>
                  ) : sample.responseError ? (
                    <Typography variant="body2" color="error.main">
                      Error: {sample.responseError}
                    </Typography>
                  ) : (
                    <Typography variant="body2">{sample.response}</Typography>
                  )}
                </Paper>
              </Box>
            )}
          </Box>

          {/* Rating Buttons - Right Side */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            <IconButton
              size="small"
              onClick={handleThumbsUp}
              sx={{
                color: isPositive ? 'text.primary' : 'text.disabled',
                '&:hover': {
                  bgcolor: 'action.hover',
                },
              }}
            >
              {isPositive ? (
                <ThumbUpIcon fontSize="small" />
              ) : (
                <ThumbUpOutlinedIcon fontSize="small" />
              )}
            </IconButton>
            <IconButton
              size="small"
              onClick={handleThumbsDown}
              sx={{
                color: isNegative ? 'text.primary' : 'text.disabled',
                '&:hover': {
                  bgcolor: 'action.hover',
                },
              }}
            >
              {isNegative ? (
                <ThumbDownIcon fontSize="small" />
              ) : (
                <ThumbDownOutlinedIcon fontSize="small" />
              )}
            </IconButton>
          </Box>
        </Box>

        {/* Feedback Input - Full Width Below - Only takes space when visible */}
        {showFeedback && (
          <Fade in={showFeedback} timeout={300}>
            <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                <TextField
                  fullWidth
                  size="small"
                  placeholder="What could be improved?"
                  value={localFeedback}
                  onChange={e => setLocalFeedback(e.target.value)}
                  variant="outlined"
                  disabled={!isNegative}
                  multiline
                  maxRows={3}
                />
                <Button
                  variant="contained"
                  size="small"
                  endIcon={<SendIcon />}
                  onClick={handleSendFeedback}
                  disabled={!isNegative || !localFeedback.trim()}
                  sx={{ minWidth: 100 }}
                >
                  Send
                </Button>
              </Box>
            </Box>
          </Fade>
        )}
      </CardContent>
    </Card>
  );
}
