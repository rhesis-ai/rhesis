'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Avatar,
  Stack,
  Divider,
  Alert,
  useTheme,
  Button,
  ToggleButton,
  ToggleButtonGroup,
  Collapse,
  IconButton,
  Tooltip,
} from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import {
  SpanNode,
  TraceDetailResponse,
  TraceReview,
  TRACE_REVIEW_TARGET_TYPES,
} from '@/utils/api-client/interfaces/telemetry';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status } from '@/utils/api-client/interfaces/status';
import { alpha } from '@mui/material/styles';
import { DeleteModal } from '@/components/common/DeleteModal';
import StatusChip from '@/components/common/StatusChip';
import {
  findStatusByCategory,
  isPassedStatusName,
} from '@/utils/test-result-status';
import MentionTextInput, {
  MentionOption,
  renderMentionText,
  inferReviewTarget,
} from '@/components/common/MentionTextInput';

const TRACE_REVIEW_TARGET_LABELS: Record<string, string> = {
  [TRACE_REVIEW_TARGET_TYPES.TRACE]: 'Trace',
  [TRACE_REVIEW_TARGET_TYPES.METRIC]: 'Metric',
  [TRACE_REVIEW_TARGET_TYPES.TURN]: 'Turn',
};

interface TraceReviewsTabProps {
  selectedSpan: SpanNode;
  trace: TraceDetailResponse;
  sessionToken: string;
  currentUserId: string;
  onTraceUpdated: () => void;
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
  initialComment?: string;
  initialStatus?: 'passed' | 'failed';
  onCommentUsed?: () => void;
}

export default function TraceReviewsTab({
  selectedSpan,
  trace,
  sessionToken,
  currentUserId,
  onTraceUpdated,
  mentionableMetrics = [],
  mentionableTurns = [],
  initialComment = '',
  initialStatus,
  onCommentUsed,
}: TraceReviewsTabProps) {
  const theme = useTheme();

  const [showReviewForm, setShowReviewForm] = useState(false);
  const [newStatus, setNewStatus] = useState<'passed' | 'failed'>('passed');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [statuses, setStatuses] = useState<Status[]>([]);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [reviewToDelete, setReviewToDelete] = useState<TraceReview | null>(
    null
  );
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (initialComment) {
      setReason(initialComment);
      setShowReviewForm(true);
      if (initialStatus) {
        setNewStatus(initialStatus);
      }
      onCommentUsed?.();
    }
  }, [initialComment, initialStatus, onCommentUsed]);

  useEffect(() => {
    const fetchStatuses = async () => {
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const statusClient = clientFactory.getStatusClient();
        const statusList = await statusClient.getStatuses({
          entity_type: 'TestResult',
        });
        setStatuses(statusList);
      } catch (err) {
        console.error('Failed to fetch statuses:', err);
      }
    };

    if (showReviewForm) {
      fetchStatuses();
    }
  }, [sessionToken, showReviewForm]);

  const handleSubmitReview = async () => {
    if (!reason.trim()) {
      setError('Please provide a reason for your review.');
      return;
    }

    const targetStatus = findStatusByCategory(
      statuses,
      newStatus === 'passed' ? 'passed' : 'failed'
    );

    if (!targetStatus) {
      setError('Could not find appropriate status. Please try again.');
      return;
    }

    if (!selectedSpan.id) {
      setError('Span ID not available. Please try again.');
      return;
    }

    try {
      setSubmitting(true);
      setError('');

      const clientFactory = new ApiClientFactory(sessionToken);
      const telemetryClient = clientFactory.getTelemetryClient();

      const reviewTarget = inferReviewTarget(reason);
      const targetType =
        reviewTarget.type === 'metric'
          ? TRACE_REVIEW_TARGET_TYPES.METRIC
          : reviewTarget.type === 'turn'
            ? TRACE_REVIEW_TARGET_TYPES.TURN
            : TRACE_REVIEW_TARGET_TYPES.TRACE;
      const target = {
        type: targetType,
        reference: reviewTarget.reference,
      };

      await telemetryClient.createReview(
        selectedSpan.id,
        targetStatus.id,
        reason.trim(),
        target
      );

      onTraceUpdated();

      setReason('');
      setShowReviewForm(false);
    } catch (_err) {
      setError('Failed to save review. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelReview = () => {
    setReason('');
    setError('');
    setShowReviewForm(false);
  };

  const handleDeleteReview = (review: TraceReview) => {
    setReviewToDelete(review);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!reviewToDelete || !selectedSpan.id) return;

    try {
      setDeleting(true);

      const clientFactory = new ApiClientFactory(sessionToken);
      const telemetryClient = clientFactory.getTelemetryClient();

      await telemetryClient.deleteReview(
        selectedSpan.id,
        reviewToDelete.review_id
      );

      onTraceUpdated();

      setDeleteDialogOpen(false);
      setReviewToDelete(null);
    } catch (_err) {
      // Error handling
    } finally {
      setDeleting(false);
    }
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
    setReviewToDelete(null);
  };

  const getAutomatedStatus = () => {
    const traceMetrics = selectedSpan.trace_metrics as Record<
      string,
      Record<string, unknown>
    > | null;
    if (!traceMetrics) return { passed: false, label: 'N/A', count: '0/0' };

    let totalMetrics = 0;
    let passedMetrics = 0;

    for (const section of ['turn_metrics', 'conversation_metrics']) {
      const sectionData = traceMetrics[section] as
        | Record<string, unknown>
        | undefined;
      const metrics = (sectionData?.metrics ?? {}) as Record<
        string,
        { is_successful?: boolean }
      >;
      for (const m of Object.values(metrics)) {
        totalMetrics++;
        if (m.is_successful) passedMetrics++;
      }
    }

    return {
      passed: totalMetrics > 0 && passedMetrics === totalMetrics,
      label:
        totalMetrics > 0 && passedMetrics === totalMetrics
          ? 'Passed'
          : 'Failed',
      count: `${passedMetrics}/${totalMetrics}`,
    };
  };

  const automatedStatus = getAutomatedStatus();
  const reviews = selectedSpan.trace_reviews?.reviews ?? [];
  const hasReviews = reviews.length > 0;
  const lastReview = selectedSpan.last_review ?? null;

  let hasConflict = false;
  if (lastReview && lastReview.status?.name) {
    const reviewPassed = isPassedStatusName(lastReview.status.name);
    hasConflict = reviewPassed !== automatedStatus.passed;
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return 'N/A';
    return date.toLocaleString();
  };

  const getReviewStatusDisplay = (statusName: string) => {
    const isPassed = isPassedStatusName(statusName);
    const name = statusName.toLowerCase();
    let label = statusName;
    if (name === 'fail') label = 'Failed';
    else if (name === 'pass') label = 'Passed';
    return { passed: isPassed, label };
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Status Overview */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" fontWeight={600} gutterBottom>
          Trace Evaluation
        </Typography>

        <Paper
          variant="outlined"
          sx={{
            p: 2,
            backgroundColor: hasConflict
              ? alpha(
                  theme.palette.warning.main,
                  theme.palette.action.hoverOpacity
                )
              : theme.palette.background.default,
            border: hasConflict
              ? `1px solid ${theme.palette.warning.light}`
              : undefined,
          }}
        >
          <Stack spacing={2}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography
                variant="body2"
                fontWeight={600}
                sx={{ minWidth: 120 }}
              >
                Automated:
              </Typography>
              <StatusChip
                passed={automatedStatus.passed}
                label={`${automatedStatus.label} ${automatedStatus.count}`}
                size="small"
                variant="outlined"
              />
            </Box>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography
                variant="body2"
                fontWeight={600}
                sx={{ minWidth: 120 }}
              >
                Human Review:
              </Typography>
              {lastReview ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {(() => {
                    const display = getReviewStatusDisplay(
                      lastReview.status.name
                    );
                    return (
                      <>
                        <StatusChip
                          passed={display.passed}
                          label={display.label}
                          size="small"
                          variant="outlined"
                        />
                        {hasConflict && (
                          <Chip
                            icon={
                              <WarningAmberIcon
                                sx={{ fontSize: 'caption.fontSize' }}
                              />
                            }
                            label="Conflict"
                            size="small"
                            color="warning"
                            variant="filled"
                            sx={{ ml: 1 }}
                          />
                        )}
                      </>
                    );
                  })()}
                </Box>
              ) : (
                <Chip
                  label="No Review"
                  size="small"
                  color="default"
                  variant="outlined"
                />
              )}
            </Box>
          </Stack>
        </Paper>

        {hasConflict && (
          <Alert severity="warning" icon={<WarningAmberIcon />} sx={{ mt: 2 }}>
            <Typography variant="body2">
              <strong>Status Conflict Detected:</strong> The human review status
              differs from the automated evaluation. This indicates the reviewer
              disagreed with the automated metrics.
            </Typography>
          </Alert>
        )}
      </Box>

      <Divider sx={{ my: 3 }} />

      {/* Reviews History */}
      <Box>
        <Typography variant="h6" fontWeight={600} gutterBottom>
          Review History
        </Typography>

        {hasReviews ? (
          <Stack spacing={2}>
            {[...reviews]
              .sort(
                (a, b) =>
                  new Date(b.updated_at).getTime() -
                  new Date(a.updated_at).getTime()
              )
              .map((review, index) => {
                const isLatest = index === 0;
                const display = getReviewStatusDisplay(review.status.name);

                return (
                  <Paper
                    key={review.review_id}
                    variant="outlined"
                    sx={{
                      p: 2,
                      backgroundColor: isLatest
                        ? alpha(
                            theme.palette.primary.main,
                            theme.palette.action.hoverOpacity
                          )
                        : theme.palette.background.default,
                      border: isLatest
                        ? `1px solid ${theme.palette.primary.light}`
                        : undefined,
                    }}
                  >
                    <Stack spacing={2}>
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <Box
                          sx={{ display: 'flex', alignItems: 'center', gap: 2 }}
                        >
                          <Avatar
                            sx={{
                              width: theme.spacing(4),
                              height: theme.spacing(4),
                              fontSize: 'caption.fontSize',
                            }}
                          >
                            {review.user.name.charAt(0).toUpperCase()}
                          </Avatar>
                          <Box>
                            <Typography variant="body2" fontWeight={600}>
                              {review.user.name}
                            </Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              {formatDate(review.updated_at)}
                            </Typography>
                          </Box>
                        </Box>

                        <Box
                          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                        >
                          {isLatest && (
                            <Chip
                              label="Latest"
                              size="small"
                              color="primary"
                              variant="filled"
                              sx={{ mr: 1 }}
                            />
                          )}
                          <StatusChip
                            passed={display.passed}
                            label={display.label}
                            size="small"
                            variant="outlined"
                          />
                          {review.user.user_id === currentUserId && (
                            <Tooltip title="Delete review">
                              <IconButton
                                size="small"
                                onClick={e => {
                                  e.stopPropagation();
                                  handleDeleteReview(review);
                                }}
                                sx={{
                                  ml: 0.5,
                                  '&:hover': {
                                    backgroundColor: alpha(
                                      theme.palette.error.main,
                                      theme.palette.action.focusOpacity
                                    ),
                                    color: theme.palette.error.main,
                                  },
                                }}
                              >
                                <DeleteOutlineIcon
                                  sx={{ fontSize: 'body2.fontSize' }}
                                />
                              </IconButton>
                            </Tooltip>
                          )}
                        </Box>
                      </Box>

                      <Box>
                        <Typography variant="body2" sx={{ mb: 1 }}>
                          <strong>Comments:</strong>
                        </Typography>
                        <Paper
                          variant="outlined"
                          sx={{
                            p: 1.5,
                            backgroundColor: theme.palette.background.paper,
                          }}
                        >
                          <Typography
                            variant="body2"
                            sx={{
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                            }}
                          >
                            {renderMentionText(
                              review.comments,
                              {
                                user: theme.palette.success.main,
                                metric: theme.palette.secondary.main,
                                turn: theme.palette.info.main,
                              },
                              {
                                user: alpha(
                                  theme.palette.success.main,
                                  theme.palette.action.disabledOpacity
                                ),
                                metric: alpha(
                                  theme.palette.secondary.main,
                                  theme.palette.action.disabledOpacity
                                ),
                                turn: alpha(
                                  theme.palette.info.main,
                                  theme.palette.action.disabledOpacity
                                ),
                              }
                            )}
                          </Typography>
                        </Paper>
                      </Box>

                      <Box
                        sx={{
                          display: 'flex',
                          gap: 2,
                          flexWrap: 'wrap',
                          alignItems: 'center',
                        }}
                      >
                        <Chip
                          icon={<TrackChangesIcon />}
                          label={
                            TRACE_REVIEW_TARGET_LABELS[review.target?.type] ??
                            TRACE_REVIEW_TARGET_LABELS[
                              TRACE_REVIEW_TARGET_TYPES.TRACE
                            ]
                          }
                          size="small"
                          variant="outlined"
                          color={
                            review.target?.type ===
                            TRACE_REVIEW_TARGET_TYPES.METRIC
                              ? 'secondary'
                              : review.target?.type ===
                                  TRACE_REVIEW_TARGET_TYPES.TURN
                                ? 'info'
                                : 'default'
                          }
                        />
                        {review.created_at !== review.updated_at && (
                          <Chip
                            label="Edited"
                            size="small"
                            variant="outlined"
                            color="info"
                          />
                        )}
                      </Box>
                    </Stack>
                  </Paper>
                );
              })}
          </Stack>
        ) : (
          <Paper
            variant="outlined"
            sx={{
              p: 4,
              textAlign: 'center',
              backgroundColor: theme.palette.background.default,
            }}
          >
            <InfoOutlinedIcon
              sx={{
                fontSize: theme.typography.h3.fontSize,
                color: theme.palette.text.disabled,
                mb: 2,
              }}
            />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No Reviews Yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              This trace has not been reviewed by any human evaluators.
            </Typography>
          </Paper>
        )}

        {/* Add Review Section */}
        <Box sx={{ mt: 3 }}>
          {!showReviewForm ? (
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() => setShowReviewForm(true)}
              fullWidth
              sx={{ py: 1.5 }}
            >
              Add Review
            </Button>
          ) : (
            <Collapse in={showReviewForm}>
              <Paper
                variant="outlined"
                sx={{
                  p: 3,
                  backgroundColor: theme.palette.background.default,
                  border: `1px solid ${theme.palette.primary.light}`,
                }}
              >
                <Typography variant="h6" fontWeight={600} gutterBottom>
                  Add Your Review
                </Typography>

                <Box sx={{ mb: 3 }}>
                  <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
                    New Status
                  </Typography>
                  <ToggleButtonGroup
                    value={newStatus}
                    exclusive
                    onChange={(_, value) => value && setNewStatus(value)}
                    size="small"
                    fullWidth
                  >
                    <ToggleButton
                      value="passed"
                      sx={{
                        '&.Mui-selected': {
                          backgroundColor: theme.palette.success.main,
                          color: theme.palette.success.contrastText,
                          '&:hover': {
                            backgroundColor: theme.palette.success.dark,
                          },
                        },
                      }}
                    >
                      <CheckCircleOutlineIcon
                        sx={{ mr: 1, fontSize: 'body2.fontSize' }}
                      />
                      Pass
                    </ToggleButton>
                    <ToggleButton
                      value="failed"
                      sx={{
                        '&.Mui-selected': {
                          backgroundColor: theme.palette.error.main,
                          color: theme.palette.error.contrastText,
                          '&:hover': {
                            backgroundColor: theme.palette.error.dark,
                          },
                        },
                      }}
                    >
                      <CancelOutlinedIcon
                        sx={{ mr: 1, fontSize: 'body2.fontSize' }}
                      />
                      Fail
                    </ToggleButton>
                  </ToggleButtonGroup>
                </Box>

                <Box sx={{ mb: 3 }}>
                  <MentionTextInput
                    label="Comments"
                    value={reason}
                    onChange={setReason}
                    placeholder="Explain your review decision... Type @ to mention"
                    mentionableMetrics={mentionableMetrics}
                    mentionableTurns={mentionableTurns}
                    error={!!error}
                    helperText={error}
                    minRows={4}
                  />
                </Box>

                <Stack direction="row" spacing={2} justifyContent="flex-end">
                  <Button onClick={handleCancelReview} disabled={submitting}>
                    Cancel
                  </Button>
                  <Button
                    variant="contained"
                    onClick={handleSubmitReview}
                    disabled={submitting || !reason.trim()}
                  >
                    {submitting ? 'Submitting...' : 'Submit Review'}
                  </Button>
                </Stack>
              </Paper>
            </Collapse>
          )}
        </Box>
      </Box>

      <DeleteModal
        open={deleteDialogOpen}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
        isLoading={deleting}
        title="Delete Review"
        itemType="review"
        message="Are you sure you want to delete this review? This action cannot be undone."
        confirmButtonText="Delete Review"
        showTopBorder={true}
      />
    </Box>
  );
}
