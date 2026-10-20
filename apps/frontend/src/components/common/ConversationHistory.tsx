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
  Collapse,
  IconButton,
  Tooltip,
  Button,
  alpha,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RateReviewIcon from '@mui/icons-material/RateReview';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import {
  ConversationTurn,
  GoalEvaluation,
  MetricResult,
} from '@/utils/api-client/interfaces/test-results';
import type { FileResponse } from '@/utils/api-client/interfaces/file';
import MarkdownContent from '@/components/common/MarkdownContent';
import StatusChip from '@/components/common/StatusChip';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { STATUS_LABEL, type TestResultStatus } from '@/constants/outcomes';
import { JsonPreview } from '@/app/(protected)/endpoints/components/JsonPreview';
import { testPreviewSx } from '@/app/(protected)/endpoints/components/endpoint-styles';
import { looksLikeMarkdown, parseJsonString } from '@/utils/message-content';
import { getProjectIconComponent } from '@/components/common/ProjectIcons';
import { Project } from '@/utils/api-client/interfaces/project';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import ResultCheckCard from '@/components/common/ResultCheckCard';
import ConversationResult from '@/components/common/ConversationResult';
import type { MetricsSource } from '@/utils/api-client/interfaces/test-configuration';
import {
  buildResultChecks,
  checksForTurn,
  countChecks,
  turnVerdict,
  type ResultCheckGroup,
} from '@/utils/result-checks';

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
  /** Shows a per-turn button that turns that exchange into a single-turn test. */
  onCreateTestFromTurn?: (turnNumber: number) => void;
  onConfirmAutomatedAnnotation?: () => void;
  hasExistingAnnotation?: boolean;
  annotationMatchesAutomated?: boolean;
  isConfirmingAnnotation?: boolean;
  maxHeight?: number | string;
  turnAnnotationMap?: Map<number, AnnotationSummaryEntry>;
  /** The result's status for the closing summary; derived from the checks when omitted. */
  resultStatus?: TestResultStatus;
  /** Opens the full evaluation from the closing summary's link. */
  onShowEvaluation?: () => void;
  /** Who annotated the result, shown once it has been reviewed. */
  reviewerName?: string;
  /** Opens the annotation flow with the opposite of the automated verdict. */
  onOverrideVerdict?: () => void;
  /** Takes the review back; only given when the reviewer may delete it. */
  onUndoReview?: () => void;
  isUndoingReview?: boolean;
  /** Names the group of metrics that came from the test's requirement. */
  requirementName?: string;
  metricsSource?: MetricsSource | string;
  /** Required when turns carry penelope_files for authenticated downloads. */
}

/** "Findings · 1 failed", or how many passed when none failed. */
function findingsLabel(groups: ResultCheckGroup[]): string {
  const { passed, total } = countChecks(groups.flatMap(g => g.checks));
  return total > passed
    ? `Findings · ${total - passed} failed`
    : `Findings · ${passed} passed`;
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
  onCreateTestFromTurn,
  onConfirmAutomatedAnnotation,
  hasExistingAnnotation = false,
  annotationMatchesAutomated = true,
  isConfirmingAnnotation = false,
  maxHeight = 600,
  turnAnnotationMap = new Map<number, AnnotationSummaryEntry>(),
  resultStatus,
  onShowEvaluation,
  requirementName,
  metricsSource,
  reviewerName,
  onOverrideVerdict,
  onUndoReview,
  isUndoingReview = false,
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

  const checkGroups = buildResultChecks({
    metrics,
    goalEvaluation,
    requirementName,
    metricsSource,
  });
  const checks = checkGroups.flatMap(g => g.checks);
  const shownResultStatus: TestResultStatus | undefined =
    resultStatus ??
    (checks.length === 0
      ? undefined
      : checks.some(c => c.passed === false)
        ? 'Fail'
        : checks.every(c => c.passed)
          ? 'Pass'
          : 'Inconclusive');

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
      {actualConversationTurns.map(turn => {
        const turnGroups = checksForTurn(checkGroups, turn.turn);

        // A human override wins. Otherwise a turn shows the verdict of the findings that cite
        // it, and no verdict at all when none do, unless the call to the target itself failed.
        const shownStatus = turn.override
          ? turn.success
            ? 'Pass'
            : 'Fail'
          : (turnVerdict(checkGroups, turn.turn) ??
            (turn.success ? undefined : 'Error'));
        const turnPassed =
          shownStatus === 'Pass'
            ? true
            : shownStatus === 'Fail'
              ? false
              : undefined;

        const turnAnnotation = turnAnnotationMap.get(turn.turn);
        const turnIsOverruled = !!turn.override;
        const turnIsConfirmed = !!turnAnnotation && !turnIsOverruled;

        return (
          <Box key={turn.turn} sx={{ mb: 4 }}>
            {/* Turn header: a section divider, so turns read as sections and not as chat */}
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
                <Typography
                  variant="caption"
                  component="h3"
                  sx={{
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: theme.typography.overline.letterSpacing,
                    whiteSpace: 'nowrap',
                    color: turnIsOverruled
                      ? 'warning.dark'
                      : turnIsConfirmed
                        ? 'success.dark'
                        : 'text.secondary',
                  }}
                >
                  {`Turn ${turn.turn}`}
                </Typography>
              </Tooltip>

              {shownStatus && (
                <StatusChip
                  status={shownStatus}
                  label={STATUS_LABEL[shownStatus]}
                  size="small"
                  variant="filled"
                />
              )}

              <Box
                aria-hidden
                sx={{ flexGrow: 1, height: '1px', bgcolor: 'divider' }}
              />

              {turnGroups.length > 0 && (
                <Button
                  size="small"
                  variant="outlined"
                  color="inherit"
                  aria-expanded={!!expandedEvaluationTurns[turn.turn]}
                  onClick={() => toggleEvaluation(turn.turn)}
                  endIcon={
                    <ExpandMoreIcon
                      sx={{
                        transform: expandedEvaluationTurns[turn.turn]
                          ? 'rotate(180deg)'
                          : 'none',
                        transition: 'transform 0.2s',
                      }}
                    />
                  }
                  sx={{
                    borderRadius: BORDER_RADIUS.pill,
                    borderColor: 'divider',
                    color: 'text.primary',
                    textTransform: 'none',
                    fontWeight: 500,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {findingsLabel(turnGroups)}
                </Button>
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

              {onCreateTestFromTurn && (
                <Tooltip title="Create single-turn test from this turn">
                  <IconButton
                    size="small"
                    aria-label={`Create single-turn test from turn ${turn.turn}`}
                    onClick={() => onCreateTestFromTurn(turn.turn)}
                    sx={{
                      padding: 0.5,
                      color: theme.palette.text.secondary,
                      '&:hover': {
                        color: theme.palette.primary.main,
                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                      },
                    }}
                  >
                    <ScienceOutlinedIcon sx={{ fontSize: theme.spacing(2) }} />
                  </IconButton>
                </Tooltip>
              )}
            </Box>

            {/* Findings (collapsible) */}
            {turnGroups.length > 0 && (
              <Collapse
                in={expandedEvaluationTurns[turn.turn]}
                timeout="auto"
                unmountOnExit
              >
                {/* Tinted and indented, so the verdict never reads as part of the chat */}
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 1.5,
                    ml: 4,
                    mb: 2.5,
                    p: 1.5,
                    borderRadius: BORDER_RADIUS.md,
                    bgcolor: 'action.hover',
                  }}
                >
                  {turnGroups.map(group => (
                    <ResultCheckCard
                      key={`${turn.turn}-${group.key}`}
                      group={group}
                      flat
                    />
                  ))}
                </Box>
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
          </Box>
        );
      })}

      <ConversationResult
        groups={checkGroups}
        status={shownResultStatus}
        turnCount={actualConversationTurns.length}
        onShowEvaluation={onShowEvaluation}
        reviewed={hasExistingAnnotation}
        reviewMatches={annotationMatchesAutomated}
        reviewerName={reviewerName}
        onConfirm={onConfirmAutomatedAnnotation}
        onOverride={onOverrideVerdict}
        onUndo={onUndoReview}
        isUndoing={isUndoingReview}
        isConfirming={isConfirmingAnnotation}
      />
    </Box>
  );
}
