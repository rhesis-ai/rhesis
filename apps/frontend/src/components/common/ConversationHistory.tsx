'use client';

import React, { useCallback, useState } from 'react';
import { useSession } from 'next-auth/react';
import type { AnnotationSummaryEntry } from '@/utils/api-client/interfaces/annotation';
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
import AttachFileIcon from '@mui/icons-material/AttachFile';
import {
  ConversationTurn,
  GoalEvaluation,
  MetricResult,
} from '@/utils/api-client/interfaces/test-results';
import type { FileResponse } from '@/utils/api-client/interfaces/file';
import MarkdownContent from '@/components/common/MarkdownContent';
import StatusChip from '@/components/common/StatusChip';
import { STATUS_LABEL } from '@/constants/outcomes';
import { JsonPreview } from '@/app/(protected)/endpoints/components/JsonPreview';
import { testPreviewSx } from '@/app/(protected)/endpoints/components/endpoint-styles';
import { looksLikeMarkdown, parseJsonString } from '@/utils/message-content';
import { getProjectIconComponent } from '@/components/common/ProjectIcons';
import { Project } from '@/utils/api-client/interfaces/project';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import {
  buildTurnFindings,
  findingsForTurn,
  turnStatus,
  turnHasConversationFindings,
  uncitedFailures,
  type TurnFinding,
} from '@/utils/turn-findings';

// Superhero (female) emoji built from code points to avoid linter emoji detection.
// U+1F9B8 (superhero) + U+200D (ZWJ) + U+2640 (female sign) + U+FE0F (variation selector)
const PENELOPE_ICON = String.fromCodePoint(0x1f9b8, 0x200d, 0x2640, 0xfe0f);

function renderJsonPreview(value: unknown) {
  return (
    <Box component="pre" sx={{ ...testPreviewSx, minHeight: 'unset', m: 0 }}>
      <JsonPreview value={value} />
    </Box>
  );
}

function renderMessageContent(content: string) {
  const parsed = parseJsonString(content);
  if (parsed !== null) {
    return renderJsonPreview(parsed);
  }
  if (looksLikeMarkdown(content)) {
    return <MarkdownContent content={content} variant="body2" />;
  }
  return (
    <Typography
      variant="body2"
      sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0 }}
    >
      {content}
    </Typography>
  );
}

interface ConversationHistoryProps {
  conversationSummary: ConversationTurn[];
  goalEvaluation?: GoalEvaluation;
  /** The test's metric results, so turns they cite show the metric's verdict. */
  metrics?: Record<string, MetricResult>;
  project?: Project | { icon?: string; useCase?: string; name?: string };
  projectName?: string;
  onResponseClick?: (turnNumber: number) => void;
  /** `turnPassed` is the status shown on the turn, or undefined when it shows none. */
  onAnnotateTurn?: (turnNumber: number, turnPassed?: boolean) => void;
  onConfirmAutomatedAnnotation?: () => void;
  hasExistingAnnotation?: boolean;
  annotationMatchesAutomated?: boolean;
  isConfirmingAnnotation?: boolean;
  maxHeight?: number | string;
  turnAnnotationMap?: Map<number, AnnotationSummaryEntry>;
  /** Required when turns carry penelope_files for authenticated downloads. */
}

/**
 * ConversationHistory Component
 * Displays multi-turn conversation between Penelope (agent) and Target (endpoint)
 * in a chat-bubble style interface.
 */
export default function ConversationHistory({
  conversationSummary,
  goalEvaluation,
  metrics,
  project,
  projectName,
  onResponseClick,
  onAnnotateTurn,
  onConfirmAutomatedAnnotation,
  hasExistingAnnotation = false,
  annotationMatchesAutomated = true,
  isConfirmingAnnotation = false,
  maxHeight = 600,
  turnAnnotationMap = new Map<number, AnnotationSummaryEntry>(),
}: ConversationHistoryProps) {
  const theme = useTheme();
  const { status } = useSession();

  const handleDownloadFile = useCallback(
    async (file: FileResponse) => {
      if (!isAuthenticated(status)) return;
      try {
        const factory = new ApiClientFactory();
        const client = factory.getFilesClient();
        const blob = await client.getFileContent(file.id);
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = file.filename;
        link.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        console.error('Failed to download file:', err);
      }
    },
    [status]
  );

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

  // Filter out turns that don't have actual conversation content
  // (e.g., internal analysis-only turns where Penelope used analyze_response tool)
  const actualConversationTurns =
    conversationSummary?.filter(
      turn => turn.penelope_message || turn.target_response
    ) || [];

  const findings = buildTurnFindings(
    goalEvaluation,
    metrics,
    actualConversationTurns.length
  );
  const conversationFailures = uncitedFailures(findings);

  // Findings on one turn, grouped by the metric that made them.
  const groupByMetric = (turnFindings: TurnFinding[]) =>
    turnFindings.reduce<Record<string, TurnFinding[]>>((groups, f) => {
      (groups[f.metric] ??= []).push(f);
      return groups;
    }, {});

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
      {conversationFailures.length > 0 && (
        <Paper
          elevation={0}
          sx={{
            p: 2,
            mb: 3,
            bgcolor: alpha(
              theme.palette.error.main,
              theme.palette.mode === 'light' ? 0.06 : 0.16
            ),
            border: `1px solid ${alpha(theme.palette.error.main, 0.3)}`,
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
            Failed on the conversation as a whole
          </Typography>
          {conversationFailures.map(f => (
            <Typography
              key={f.key}
              variant="body2"
              color="text.secondary"
              sx={{ mb: 0.5 }}
            >
              <strong>
                {f.label === f.metric ? f.metric : `${f.metric}: ${f.label}`}
              </strong>
              {f.evidence ? ` — ${f.evidence}` : ''}
            </Typography>
          ))}
        </Paper>
      )}

      {actualConversationTurns.map((turn, index) => {
        const turnFindings = findingsForTurn(findings, turn.turn);
        const findingGroups = Object.entries(groupByMetric(turnFindings));

        // A human override wins. Otherwise a turn shows the verdict of the findings that cite
        // it, and no verdict at all when none do, unless the call to the target itself failed.
        const shownStatus = turn.override
          ? turn.success
            ? 'Pass'
            : 'Fail'
          : (turnStatus(findings, turn.turn) ??
            (turn.success ? undefined : 'Error'));
        const turnPassed =
          shownStatus === 'Pass'
            ? true
            : shownStatus === 'Fail'
              ? false
              : undefined;

        // Soft indicator: no per-turn verdict, but a conversation-level finding cites this turn.
        const isEvaluated =
          !shownStatus && turnHasConversationFindings(findings, turn.turn);

        const turnAnnotation = turnAnnotationMap.get(turn.turn);
        const turnIsOverruled = !!turn.override;
        const turnIsConfirmed = !!turnAnnotation && !turnIsOverruled;

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
              <Tooltip
                title={
                  turnIsOverruled
                    ? `Annotated by ${turnAnnotation?.user?.name}: status changed to ${turnAnnotation?.status?.name}`
                    : turnIsConfirmed
                      ? `Confirmed by ${turnAnnotation?.user?.name}`
                      : ''
                }
                disableHoverListener={!turnAnnotation}
                arrow
              >
                <Chip
                  label={`Turn ${turn.turn}`}
                  size="small"
                  color="primary"
                  variant="outlined"
                  sx={{
                    ...(turnIsOverruled && {
                      borderColor: theme.palette.warning.main,
                    }),
                    ...(turnIsConfirmed && {
                      borderColor: theme.palette.success.light,
                    }),
                  }}
                />
              </Tooltip>

              {shownStatus && (
                <StatusChip
                  status={shownStatus}
                  label={STATUS_LABEL[shownStatus]}
                  size="small"
                  variant="filled"
                />
              )}

              {isEvaluated && (
                <Chip
                  label="Evaluated"
                  size="small"
                  variant="outlined"
                  sx={{
                    color: 'text.secondary',
                    borderColor: theme.palette.divider,
                    fontSize: theme.typography.caption.fontSize,
                  }}
                />
              )}

              {/* Collapsible Evaluation Toggle */}
              {turnFindings.length > 0 && (
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

              {/* Annotate Turn Button */}
              {onAnnotateTurn && (
                <Tooltip title="Annotate this turn">
                  <IconButton
                    size="small"
                    onClick={() => onAnnotateTurn(turn.turn, turnPassed)}
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
            {turnFindings.length > 0 && (
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
                  {findingGroups.map(([metric, group], groupIdx) => (
                    <Box
                      key={`${turn.turn}-${metric}`}
                      sx={{ mb: groupIdx < findingGroups.length - 1 ? 2 : 0 }}
                    >
                      <Typography
                        variant="body2"
                        sx={{ fontWeight: 600, display: 'block', mb: 1 }}
                      >
                        {metric}
                      </Typography>
                      {group.map(finding => (
                        <Box
                          key={`${turn.turn}-${finding.key}`}
                          sx={{ pl: 2, mb: 1 }}
                        >
                          {finding.label !== metric && (
                            <Typography variant="body2" sx={{ mb: 0.5 }}>
                              {finding.label}
                            </Typography>
                          )}
                          <Typography
                            variant="caption"
                            sx={{
                              display: 'block',
                              fontWeight: 600,
                              color: finding.met
                                ? 'success.main'
                                : 'error.main',
                            }}
                          >
                            {finding.met ? 'Met' : 'Not met'}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {finding.evidence}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  ))}
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
                <Box
                  sx={{
                    wordBreak: 'break-word',
                    mb:
                      turn.penelope_reasoning ||
                      (turn.penelope_files && turn.penelope_files.length > 0) ||
                      (turn.sent_files && turn.sent_files.length > 0)
                        ? 1
                        : 0,
                  }}
                >
                  <MarkdownContent
                    content={turn.penelope_message || ''}
                    variant="body2"
                  />
                </Box>

                {turn.penelope_files &&
                  turn.penelope_files.length > 0 &&
                  isAuthenticated(status) && (
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 0.5,
                        mt: 0.5,
                      }}
                    >
                      {turn.penelope_files.map(file => (
                        <Chip
                          key={file.id}
                          icon={
                            <AttachFileIcon
                              sx={{ fontSize: theme.spacing(2) }}
                            />
                          }
                          label={file.filename}
                          size="small"
                          variant="outlined"
                          clickable
                          onClick={() => handleDownloadFile(file)}
                          sx={{
                            color: 'text.secondary',
                            borderColor: theme.palette.divider,
                            fontSize: theme.typography.caption.fontSize,
                          }}
                        />
                      ))}
                    </Box>
                  )}

                {/* Fallback: show sent_files when no span-based penelope_files */}
                {(!turn.penelope_files || turn.penelope_files.length === 0) &&
                  turn.sent_files &&
                  turn.sent_files.length > 0 && (
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 0.5,
                        mt: 0.5,
                      }}
                    >
                      {turn.sent_files.map(file => (
                        <Chip
                          key={`${file.filename}-${file.content_type ?? ''}`}
                          icon={
                            <AttachFileIcon
                              sx={{ fontSize: theme.spacing(2) }}
                            />
                          }
                          label={file.filename}
                          size="small"
                          variant="outlined"
                          sx={{
                            color: 'text.secondary',
                            borderColor: theme.palette.divider,
                            fontSize: theme.typography.caption.fontSize,
                          }}
                        />
                      ))}
                    </Box>
                  )}

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
                <Box
                  sx={{
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
                  {renderMessageContent(turn.target_response || '')}
                </Box>

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
                        {(turn.context ?? []).map((item, idx, arr) => {
                          const itemContent =
                            typeof item === 'string'
                              ? renderMessageContent(item)
                              : renderJsonPreview(item);
                          return (
                            <Box
                              key={`ctx-${turn.turn}-${typeof item === 'string' ? item : idx}`}
                              sx={{
                                color: theme.palette.text.secondary,
                                mb: idx < arr.length - 1 ? 1 : 0,
                                pl: 1,
                                borderLeft: `2px solid ${theme.palette.info.light}`,
                              }}
                            >
                              {itemContent}
                            </Box>
                          );
                        })}
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
                        {renderJsonPreview(turn.metadata)}
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
                        {renderJsonPreview(turn.tool_calls)}
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

        {/* Confirmed indicator only when an annotation exists AND matches the automated result; otherwise the Confirm button. */}
        {hasExistingAnnotation && annotationMatchesAutomated ? (
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
        ) : !hasExistingAnnotation && onConfirmAutomatedAnnotation ? (
          <Tooltip title="Confirm automated result">
            <span>
              <IconButton
                size="small"
                onClick={onConfirmAutomatedAnnotation}
                disabled={isConfirmingAnnotation}
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
