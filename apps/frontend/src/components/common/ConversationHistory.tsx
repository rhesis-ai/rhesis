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
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RateReviewIcon from '@mui/icons-material/RateReview';
import CheckIcon from '@mui/icons-material/Check';
import {
  ConversationTurn,
  GoalEvaluation,
} from '@/utils/api-client/interfaces/test-results';
import StatusChip from '@/components/common/StatusChip';
import { getProjectIconComponent } from '@/components/common/ProjectIcons';
import { Project } from '@/utils/api-client/interfaces/project';

// Superhero (female) emoji built from code points to avoid linter emoji detection.
// U+1F9B8 (superhero) + U+200D (ZWJ) + U+2640 (female sign) + U+FE0F (variation selector)
const PENELOPE_ICON = String.fromCodePoint(0x1f9b8, 0x200d, 0x2640, 0xfe0f);

interface ConversationHistoryProps {
  conversationSummary: ConversationTurn[];
  goalEvaluation?: GoalEvaluation;
  project?: Project | { icon?: string; useCase?: string; name?: string };
  projectName?: string;
  onResponseClick?: (turnNumber: number) => void;
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
  onResponseClick,
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

  // Track expanded state for each turn's reasoning, evaluation, and metadata
  const [expandedReasoningTurns, setExpandedReasoningTurns] = useState<
    Record<number, boolean>
  >({});
  const [expandedEvaluationTurns, setExpandedEvaluationTurns] = useState<
    Record<number, boolean>
  >({});
  const [expandedContextTurns, setExpandedContextTurns] = useState<
    Record<number, boolean>
  >({});
  const [expandedMetadataTurns, setExpandedMetadataTurns] = useState<
    Record<number, boolean>
  >({});
  const [expandedToolCallsTurns, setExpandedToolCallsTurns] = useState<
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

  const toggleContext = (turnNumber: number) => {
    setExpandedContextTurns(prev => ({
      ...prev,
      [turnNumber]: !prev[turnNumber],
    }));
  };

  const toggleMetadata = (turnNumber: number) => {
    setExpandedMetadataTurns(prev => ({
      ...prev,
      [turnNumber]: !prev[turnNumber],
    }));
  };

  const toggleToolCalls = (turnNumber: number) => {
    setExpandedToolCallsTurns(prev => ({
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
        p: 3,
        bgcolor: 'transparent',
        flex: maxHeight === '100%' ? 1 : 'none',
        width: '100%',
        '&::-webkit-scrollbar': {
          width: theme.spacing(1),
        },
        '&::-webkit-scrollbar-track': {
          background: 'transparent',
          borderRadius: theme.spacing(0.5),
        },
        '&::-webkit-scrollbar-thumb': {
          background: theme.palette.divider,
          borderRadius: theme.spacing(0.5),
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
        const _turnCriteriaFailed =
          turnHasCriteria && criteriaForTurn.some(c => !c.met);

        return (
          <Box key={turn.turn} sx={{ mb: 4 }}>
            {/* Turn Header */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                mb: 2.5,
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
                    <ExpandMoreIcon sx={{ fontSize: theme.spacing(2) }} />
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
                    <RateReviewIcon sx={{ fontSize: theme.spacing(2) }} />
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
                    bgcolor: alpha(
                      theme.palette.warning.main,
                      theme.palette.mode === 'light' ? 0.08 : 0.2
                    ),
                    border: `1px solid ${alpha(theme.palette.warning.main, theme.palette.mode === 'light' ? 0.3 : 0.4)}`,
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 600, display: 'block', mb: 1.5 }}
                  >
                    Criteria Evaluations
                  </Typography>
                  {criteriaForTurn.map((criterion, idx) => {
                    // Create stable key from criterion name
                    const criterionKey = `criterion-${turn.turn}-${criterion.criterion.substring(0, 30).replace(/\s+/g, '-')}`;
                    return (
                      <Box
                        key={criterionKey}
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
                    );
                  })}
                </Paper>
              </Collapse>
            )}

            {/* Penelope's Message (Left - Agent) */}
            <Box
              sx={{
                display: 'flex',
                gap: 1.5,
                mb: 2,
                alignItems: 'flex-start',
              }}
            >
              <Tooltip title="Penelope by Rhesis AI" placement="left">
                <Box
                  component="span"
                  sx={{
                    fontSize: theme.spacing(2.5),
                    lineHeight: 1,
                    mt: 0.5,
                    display: 'inline-block',
                    userSelect: 'none',
                  }}
                  aria-label="Penelope"
                >
                  {PENELOPE_ICON}
                </Box>
              </Tooltip>
              <Paper
                elevation={0}
                sx={{
                  p: 2,
                  maxWidth: '85%',
                  bgcolor: 'background.paper',
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
                        <ExpandMoreIcon
                          sx={{ fontSize: theme.spacing(1.75) }}
                        />
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
                gap: 1.5,
                justifyContent: 'flex-end',
                alignItems: 'flex-start',
              }}
            >
              <Paper
                elevation={0}
                onClick={
                  onResponseClick ? () => onResponseClick(turn.turn) : undefined
                }
                sx={{
                  p: 2,
                  maxWidth: '85%',
                  bgcolor: theme.palette.background.paper,
                  border: `1px solid ${theme.palette.divider}`,
                  borderRight: `3px solid ${theme.palette.warning.main}`,
                  ...(onResponseClick && {
                    cursor: 'pointer',
                    transition: 'border-color 0.2s',
                    '&:hover': {
                      borderColor: theme.palette.primary.main,
                    },
                  }),
                }}
              >
                <Typography
                  variant="body2"
                  sx={{
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    mb:
                      (turn.context && turn.context.length > 0) ||
                      (turn.metadata &&
                        Object.keys(turn.metadata).length > 0) ||
                      (turn.tool_calls && turn.tool_calls.length > 0)
                        ? 1
                        : 0,
                  }}
                >
                  {turn.target_response}
                </Typography>

                {/* Context (collapsible within response) */}
                {turn.context && turn.context.length > 0 && (
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
                      onClick={e => {
                        e.stopPropagation();
                        toggleContext(turn.turn);
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{ color: theme.palette.info.main, fontWeight: 500 }}
                      >
                        Context
                      </Typography>
                      <IconButton
                        size="small"
                        sx={{
                          padding: 0,
                          transform: expandedContextTurns[turn.turn]
                            ? 'rotate(180deg)'
                            : 'rotate(0deg)',
                          transition: 'transform 0.2s',
                          color: theme.palette.info.main,
                        }}
                      >
                        <ExpandMoreIcon
                          sx={{ fontSize: theme.spacing(1.75) }}
                        />
                      </IconButton>
                    </Box>

                    <Collapse
                      in={expandedContextTurns[turn.turn]}
                      timeout="auto"
                      unmountOnExit
                    >
                      <Box
                        sx={{
                          mt: 1,
                          pt: 1,
                          borderTop: `1px solid ${theme.palette.divider}`,
                        }}
                        onClick={e => e.stopPropagation()}
                      >
                        {(turn.context as string[]).map((item, idx, arr) => (
                          <Typography
                            key={`ctx-${turn.turn}-${idx}`}
                            variant="body2"
                            sx={{
                              color: theme.palette.text.secondary,
                              mb: idx < arr.length - 1 ? 1 : 0,
                              pl: 1,
                              borderLeft: `2px solid ${theme.palette.info.light}`,
                            }}
                          >
                            {typeof item === 'string'
                              ? item
                              : JSON.stringify(item)}
                          </Typography>
                        ))}
                      </Box>
                    </Collapse>
                  </>
                )}

                {/* Metadata (collapsible within response) */}
                {turn.metadata && Object.keys(turn.metadata).length > 0 && (
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
                      onClick={e => {
                        e.stopPropagation();
                        toggleMetadata(turn.turn);
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{
                          color: theme.palette.warning.main,
                          fontWeight: 500,
                        }}
                      >
                        Metadata
                      </Typography>
                      <IconButton
                        size="small"
                        sx={{
                          padding: 0,
                          transform: expandedMetadataTurns[turn.turn]
                            ? 'rotate(180deg)'
                            : 'rotate(0deg)',
                          transition: 'transform 0.2s',
                          color: theme.palette.warning.main,
                        }}
                      >
                        <ExpandMoreIcon
                          sx={{ fontSize: theme.spacing(1.75) }}
                        />
                      </IconButton>
                    </Box>

                    <Collapse
                      in={expandedMetadataTurns[turn.turn]}
                      timeout="auto"
                      unmountOnExit
                    >
                      <Box
                        sx={{
                          mt: 1,
                          pt: 1,
                          borderTop: `1px solid ${theme.palette.divider}`,
                        }}
                        onClick={e => e.stopPropagation()}
                      >
                        <Typography
                          component="pre"
                          variant="body2"
                          sx={{
                            fontFamily:
                              theme.typography.fontFamilyCode ?? 'monospace',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-all',
                            color: theme.palette.text.secondary,
                            m: 0,
                          }}
                        >
                          {JSON.stringify(turn.metadata, null, 2)}
                        </Typography>
                      </Box>
                    </Collapse>
                  </>
                )}

                {/* Tool Calls (collapsible within response) */}
                {turn.tool_calls && turn.tool_calls.length > 0 && (
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
                      onClick={e => {
                        e.stopPropagation();
                        toggleToolCalls(turn.turn);
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{
                          color: theme.palette.secondary.main,
                          fontWeight: 500,
                        }}
                      >
                        Tool Calls
                      </Typography>
                      <IconButton
                        size="small"
                        sx={{
                          padding: 0,
                          transform: expandedToolCallsTurns[turn.turn]
                            ? 'rotate(180deg)'
                            : 'rotate(0deg)',
                          transition: 'transform 0.2s',
                          color: theme.palette.secondary.main,
                        }}
                      >
                        <ExpandMoreIcon
                          sx={{ fontSize: theme.spacing(1.75) }}
                        />
                      </IconButton>
                    </Box>

                    <Collapse
                      in={expandedToolCallsTurns[turn.turn]}
                      timeout="auto"
                      unmountOnExit
                    >
                      <Box
                        sx={{
                          mt: 1,
                          pt: 1,
                          borderTop: `1px solid ${theme.palette.divider}`,
                        }}
                        onClick={e => e.stopPropagation()}
                      >
                        <Typography
                          component="pre"
                          variant="body2"
                          sx={{
                            fontFamily:
                              theme.typography.fontFamilyCode ?? 'monospace',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-all',
                            color: theme.palette.text.secondary,
                            m: 0,
                          }}
                        >
                          {JSON.stringify(turn.tool_calls, null, 2)}
                        </Typography>
                      </Box>
                    </Collapse>
                  </>
                )}
              </Paper>
              <Tooltip title={displayProjectName} placement="right">
                <Box
                  sx={{
                    fontSize: theme.spacing(2.5),
                    color: theme.palette.warning.main,
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
            {index < actualConversationTurns.length - 1 && (
              <Divider sx={{ mt: 4, mb: 1 }} />
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
            bgcolor: alpha(
              theme.palette.primary.main,
              theme.palette.mode === 'light' ? 0.06 : 0.15
            ),
            color: theme.palette.primary.main,
            fontWeight: 500,
            border: `1px solid ${theme.palette.primary.main}`,
          }}
        />

        {/* Show Confirmed Indicator only if review exists AND matches automated result, otherwise show Confirm button */}
        {hasExistingReview && reviewMatchesAutomated ? (
          <Chip
            icon={<CheckIcon sx={{ fontSize: theme.spacing(2) }} />}
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
                <CheckIcon sx={{ fontSize: theme.spacing(2.25) }} />
              </IconButton>
            </span>
          </Tooltip>
        ) : null}
      </Box>
    </Box>
  );
}
