'use client';

import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  useTheme,
  Divider,
  Collapse,
  IconButton,
  Tooltip,
  alpha,
} from '@mui/material';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RateReviewIcon from '@mui/icons-material/RateReview';
import CheckIcon from '@mui/icons-material/Check';
import {
  ConversationTurn,
  GoalEvaluation,
} from '@/utils/api-client/interfaces/test-results';
import StatusChip from '@/components/common/StatusChip';
import { getProjectIconComponent } from '@/utils/projectIcons';
import { Project } from '@/utils/api-client/interfaces/project';

interface ConversationHistoryProps {
  conversationSummary: ConversationTurn[];
  goalEvaluation?: GoalEvaluation;
  project?: Project | { icon?: string; useCase?: string; name?: string };
  projectName?: string;
  onReviewTurn?: (turnNumber: number, turnSuccess: boolean) => void;
  onConfirmAutomatedReview?: () => void;
  hasExistingReview?: boolean;
  reviewMatchesAutomated?: boolean; // True if review matches automated result, false if conflict
  isConfirmingReview?: boolean;
  maxHeight?: number | string;
}

/**
 * ConversationHistory Component
 * Displays multi-turn conversation between Penelope (agent) and Target (endpoint)
 * in a chat-bubble style interface.
 */
export default function ConversationHistory({
  conversationSummary,
  goalEvaluation,
  project,
  projectName,
  onReviewTurn,
  onConfirmAutomatedReview,
  hasExistingReview = false,
  reviewMatchesAutomated = true,
  isConfirmingReview = false,
  maxHeight = 600,
}: ConversationHistoryProps) {
  const theme = useTheme();

  // Get the project icon component
  const ProjectIcon = getProjectIconComponent(project);

  // Determine the project name for tooltip
  const displayProjectName =
    projectName ||
    (project && typeof project !== 'string' ? project.name : undefined) ||
    'Project';

  // Track expanded state for each turn's reasoning and evaluation
  const [expandedReasoningTurns, setExpandedReasoningTurns] = useState<
    Record<number, boolean>
  >({});
  const [expandedEvaluationTurns, setExpandedEvaluationTurns] = useState<
    Record<number, boolean>
  >({});

  const toggleReasoning = (turnNumber: number) => {
    setExpandedReasoningTurns(prev => ({
      ...prev,
      [turnNumber]: !prev[turnNumber],
    }));
  };

  const toggleEvaluation = (turnNumber: number) => {
    setExpandedEvaluationTurns(prev => ({
      ...prev,
      [turnNumber]: !prev[turnNumber],
    }));
  };

  // Get relevant criteria evaluations for a specific turn
  const getCriteriaForTurn = (turnNumber: number) => {
    if (!goalEvaluation?.criteria_evaluations) return [];
    return (
      goalEvaluation.criteria_evaluations?.filter(criterion =>
        criterion.relevant_turns.includes(turnNumber)
      ) || []
    );
  };

  // Filter out turns that don't have actual conversation content
  // (e.g., internal analysis-only turns where Penelope used analyze_response tool)
  const actualConversationTurns =
    conversationSummary?.filter(
      turn => turn.penelope_message || turn.target_response
    ) || [];

  if (actualConversationTurns.length === 0) {
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
        borderRadius: theme.shape.borderRadius,
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
      {actualConversationTurns.map((turn, index) => {
        const criteriaForTurn = getCriteriaForTurn(turn.turn);

        // Determine turn status based on criteria evaluation
        // If there are criteria for this turn, use those to determine pass/fail
        // Otherwise, don't show a status chip (tool success is not meaningful for users)
        const turnHasCriteria = criteriaForTurn.length > 0;
        const turnCriteriaMet =
          turnHasCriteria && criteriaForTurn.every(c => c.met);
        const turnCriteriaFailed =
          turnHasCriteria && criteriaForTurn.some(c => !c.met);

        return (
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

              {/* Result Status Chip - Only show if there are criteria for this turn */}
              {turnHasCriteria && (
                <StatusChip
                  status={turnCriteriaMet ? 'Pass' : 'Fail'}
                  label={turnCriteriaMet ? 'Passed' : 'Failed'}
                  size="small"
                  variant="filled"
                />
              )}

              {/* Collapsible Evaluation Toggle */}
              {criteriaForTurn.length > 0 && (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                    cursor: 'pointer',
                    '&:hover': { opacity: 0.7 },
                  }}
                  onClick={() => toggleEvaluation(turn.turn)}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      color: theme.palette.primary.main,
                      fontWeight: 500,
                    }}
                  >
                    {expandedEvaluationTurns[turn.turn] ? 'Hide' : 'Show'}{' '}
                    Evaluation
                  </Typography>
                  <IconButton
                    size="small"
                    sx={{
                      padding: 0,
                      transform: expandedEvaluationTurns[turn.turn]
                        ? 'rotate(180deg)'
                        : 'rotate(0deg)',
                      transition: 'transform 0.2s',
                      color: theme.palette.primary.main,
                    }}
                  >
                    <ExpandMoreIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Box>
              )}

              {/* Review Turn Button */}
              {onReviewTurn && (
                <Tooltip title="Review this turn">
                  <IconButton
                    size="small"
                    onClick={() => onReviewTurn(turn.turn, turn.success)}
                    sx={{
                      padding: 0.5,
                      color: theme.palette.text.secondary,
                      '&:hover': {
                        color: theme.palette.primary.main,
                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                      },
                    }}
                  >
                    <RateReviewIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Tooltip>
              )}
            </Box>

            {/* Evaluation (collapsible) */}
            {criteriaForTurn.length > 0 && (
              <Collapse
                in={expandedEvaluationTurns[turn.turn]}
                timeout="auto"
                unmountOnExit
              >
                <Paper
                  elevation={0}
                  sx={{
                    p: 2,
                    mb: 1.5,
                    bgcolor:
                      theme.palette.mode === 'light' ? '#FFFBF0' : '#2A2520',
                    border: `1px solid ${theme.palette.mode === 'light' ? '#E8DABC' : '#3F3020'}`,
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 600, display: 'block', mb: 1.5 }}
                  >
                    Criteria Evaluations
                  </Typography>
                  {criteriaForTurn.map((criterion, idx) => (
                    <Box
                      key={idx}
                      sx={{ mb: idx < criteriaForTurn.length - 1 ? 2 : 0 }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 600,
                          mb: 0.5,
                        }}
                      >
                        {criterion.criterion}
                      </Typography>
                      <Box sx={{ pl: 2 }}>
                        <Typography
                          variant="body2"
                          sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}
                        >
                          Evidence:
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {criterion.evidence}
                        </Typography>
                      </Box>
                    </Box>
                  ))}
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
              <Tooltip title="Penelope by Rhesis AI" placement="left">
                <SmartToyIcon
                  sx={{
                    fontSize: 20,
                    color: theme.palette.primary.main,
                    mt: 0.5,
                  }}
                />
              </Tooltip>
              <Paper
                elevation={0}
                sx={{
                  p: 2,
                  maxWidth: '85%',
                  bgcolor:
                    theme.palette.mode === 'light' ? '#FFFFFF' : '#1F242B',
                  border: `1px solid ${theme.palette.divider}`,
                  borderLeft: `3px solid ${theme.palette.primary.main}`,
                }}
              >
                <Typography
                  variant="body2"
                  sx={{
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    mb: turn.penelope_reasoning ? 1 : 0,
                  }}
                >
                  {turn.penelope_message}
                </Typography>

                {/* Penelope's Reasoning (collapsible within message) */}
                {turn.penelope_reasoning && (
                  <>
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        cursor: 'pointer',
                        '&:hover': { opacity: 0.7 },
                        mt: 1,
                      }}
                      onClick={() => toggleReasoning(turn.turn)}
                    >
                      <Typography
                        variant="caption"
                        sx={{
                          color: theme.palette.primary.main,
                          fontWeight: 500,
                        }}
                      >
                        {expandedReasoningTurns[turn.turn] ? 'Hide' : 'Show'}{' '}
                        Reasoning
                      </Typography>
                      <IconButton
                        size="small"
                        sx={{
                          padding: 0,
                          transform: expandedReasoningTurns[turn.turn]
                            ? 'rotate(180deg)'
                            : 'rotate(0deg)',
                          transition: 'transform 0.2s',
                          color: theme.palette.primary.main,
                        }}
                      >
                        <ExpandMoreIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Box>

                    <Collapse
                      in={expandedReasoningTurns[turn.turn]}
                      timeout="auto"
                      unmountOnExit
                    >
                      <Box
                        sx={{
                          mt: 1,
                          pt: 1,
                          borderTop: `1px solid ${theme.palette.divider}`,
                        }}
                      >
                        <Typography
                          variant="body2"
                          sx={{ fontWeight: 600, display: 'block', mb: 0.5 }}
                        >
                          Reasoning
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {turn.penelope_reasoning}
                        </Typography>
                      </Box>
                    </Collapse>
                  </>
                )}
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
                elevation={0}
                sx={{
                  p: 2,
                  maxWidth: '85%',
                  bgcolor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRight: `3px solid ${theme.palette.secondary.main}`,
                }}
              >
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
              <Tooltip title={displayProjectName} placement="right">
                <Box
                  sx={{
                    fontSize: 20,
                    color: theme.palette.secondary.main,
                    mt: 0.5,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <ProjectIcon />
                </Box>
              </Tooltip>
            </Box>

            {/* Divider between turns (except last) */}
            {index < conversationSummary.length - 1 && (
              <Divider sx={{ mt: 3 }} />
            )}
          </Box>
        );
      })}

      {/* Conversation Concluded Marker */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          mt: 3,
          py: 2,
          gap: 2,
        }}
      >
        <Chip
          label="Conversation Concluded"
          size="small"
          sx={{
            bgcolor: theme.palette.mode === 'light' ? '#F0F7FC' : '#1A2331',
            color: theme.palette.primary.main,
            fontWeight: 500,
            border: `1px solid ${theme.palette.primary.main}`,
          }}
        />

        {/* Show Confirmed Indicator only if review exists AND matches automated result, otherwise show Confirm button */}
        {hasExistingReview && reviewMatchesAutomated ? (
          <Chip
            icon={<CheckIcon sx={{ fontSize: 16 }} />}
            label="Confirmed"
            size="medium"
            color="success"
            variant="filled"
            sx={{
              fontWeight: 600,
            }}
          />
        ) : !hasExistingReview && onConfirmAutomatedReview ? (
          <Tooltip title="Confirm automated review">
            <span>
              <IconButton
                size="small"
                onClick={onConfirmAutomatedReview}
                disabled={isConfirmingReview}
                sx={{
                  color: theme.palette.success.main,
                  border: `1px solid ${theme.palette.success.main}`,
                  '&:hover': {
                    backgroundColor: alpha(theme.palette.success.main, 0.1),
                  },
                  '&:disabled': {
                    color: theme.palette.action.disabled,
                    borderColor: theme.palette.action.disabled,
                  },
                }}
              >
                <CheckIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </span>
          </Tooltip>
        ) : null}
      </Box>
    </Box>
  );
}
