'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Avatar,
  Stack,
  Button,
  IconButton,
  Tooltip,
  useTheme,
} from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { formatDistanceToNow } from 'date-fns';
import { useQueryClient } from '@tanstack/react-query';
import {
  TestResultDetail,
  Review,
} from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { can } from '@/components/common/Can';
import { alpha } from '@mui/material/styles';
import { DeleteModal } from '@/components/common/DeleteModal';
import StatusChip from '@/components/common/StatusChip';
import { isPassedStatusName } from '@/utils/test-result-status';
import { annotationKeys } from '@/constants/query-keys';
import {
  getResultReviews,
  getLatestMetricReviewForResult,
  isExplicitTestLevelReview,
} from './test-run-summary-utils';
import {
  MentionOption,
  MentionText,
} from '@/components/common/MentionTextInput';
import ReviewJudgementDrawer from './ReviewJudgementDrawer';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';

interface TestDetailReviewsTabProps {
  test: TestResultDetail;
  sessionToken: string;
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
  currentUserId: string;
  initialComment?: string;
  initialStatus?: 'passed' | 'failed';
  onCommentUsed?: () => void;
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
}

export default function TestDetailReviewsTab({
  test,
  sessionToken,
  onTestResultUpdate,
  currentUserId,
  initialComment = '',
  initialStatus,
  onCommentUsed,
  mentionableMetrics = [],
  mentionableTurns = [],
}: TestDetailReviewsTabProps) {
  const theme = useTheme();
  const queryClient = useQueryClient();

  const invalidateAnnotations = () => {
    void queryClient.invalidateQueries({ queryKey: annotationKeys.all() });
  };

  const canCreateReview = can(test, Capability.TestResult.UPDATE);
  const [createOpen, setCreateOpen] = useState(false);
  const [showOthers, setShowOthers] = useState(false);

  // List payloads omit review affordances — refresh so resolve/delete gates work.
  useEffect(() => {
    const reviews = test.test_reviews?.reviews;
    if (!reviews?.length) return;
    const missingAffordances = reviews.some(
      r => !Array.isArray(r.permitted_actions)
    );
    if (!missingAffordances) return;

    let cancelled = false;
    (async () => {
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const testResultsClient = clientFactory.getTestResultsClient();
        const updatedTest = await testResultsClient.getTestResult(test.id);
        if (!cancelled) onTestResultUpdate(updatedTest);
      } catch (error) {
        console.error('Failed to refresh review affordances:', error);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [test.id, test.test_reviews, sessionToken, onTestResultUpdate]);

  // Stable capture of initial comment for the drawer (survives parent reset)
  const pendingCommentRef = useRef<{
    comment: string;
    status?: 'passed' | 'failed';
  } | null>(null);

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [reviewToDelete, setReviewToDelete] = useState<Review | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Open the create drawer when a pre-filled comment arrives (e.g. from turn review)
  useEffect(() => {
    if (initialComment) {
      pendingCommentRef.current = {
        comment: initialComment,
        status: initialStatus,
      };
      setCreateOpen(true);
      onCommentUsed?.();
    }
  }, [initialComment, initialStatus, onCommentUsed]);

  const handleCloseCreateDrawer = () => {
    pendingCommentRef.current = null;
    setCreateOpen(false);
  };

  const handleReviewSaved = async (testId: string) => {
    const clientFactory = new ApiClientFactory(sessionToken);
    const testResultsClient = clientFactory.getTestResultsClient();
    const updatedTest = await testResultsClient.getTestResult(testId);
    onTestResultUpdate(updatedTest);
    invalidateAnnotations();
  };

  // Delete handlers
  const handleDeleteReview = (review: Review) => {
    setReviewToDelete(review);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!reviewToDelete) return;
    try {
      setDeleting(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      await testResultsClient.deleteReview(test.id, reviewToDelete.review_id);
      const updatedTest = await testResultsClient.getTestResult(test.id);
      onTestResultUpdate(updatedTest);
      invalidateAnnotations();
      setDeleteDialogOpen(false);
      setReviewToDelete(null);
    } catch (_err) {
      // Silently fail; no error state change to avoid breaking the delete flow
    } finally {
      setDeleting(false);
    }
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
    setReviewToDelete(null);
  };

  // Automated status computation
  const automatedStatus = useMemo(() => {
    const metrics = test.test_metrics?.metrics || {};
    const metricValues = Object.values(metrics);
    const totalMetrics = metricValues.length;
    const passedMetrics = metricValues.filter(m => m.is_successful).length;
    return {
      passed: totalMetrics > 0 && passedMetrics === totalMetrics,
      label:
        totalMetrics > 0 && passedMetrics === totalMetrics
          ? 'Passed'
          : 'Failed',
      count: `${passedMetrics}/${totalMetrics}`,
    };
  }, [test]);

  const lastReview = test.last_review;

  const testLevelReviews = useMemo(
    () =>
      getResultReviews(test).filter(review =>
        isExplicitTestLevelReview(test, review)
      ),
    [test]
  );

  const latestTestLevelReview = useMemo(() => {
    if (lastReview && isExplicitTestLevelReview(test, lastReview)) {
      return lastReview;
    }
    const sorted = [...testLevelReviews].sort(
      (a, b) =>
        new Date((b as Review).updated_at).getTime() -
        new Date((a as Review).updated_at).getTime()
    );
    return (sorted[0] as Review | undefined) ?? null;
  }, [lastReview, test, testLevelReviews]);

  const latestMetricReview = useMemo(
    () => getLatestMetricReviewForResult(test) as Review | undefined,
    [test]
  );

  const hasMetricReviewOnly =
    !latestTestLevelReview && latestMetricReview !== undefined;

  // Conflict: human test-level review disagrees with automated (and not resolved)
  const hasConflict = useMemo(() => {
    if (!latestTestLevelReview?.status?.name) return false;
    if (latestTestLevelReview.resolved) return false;
    return (
      isPassedStatusName(latestTestLevelReview.status.name) !==
      automatedStatus.passed
    );
  }, [latestTestLevelReview, automatedStatus]);

  const [resolvingReviewId, setResolvingReviewId] = useState<string | null>(
    null
  );

  const handleToggleResolved = async (review: Review) => {
    try {
      setResolvingReviewId(review.review_id);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      await testResultsClient.updateReview(test.id, review.review_id, {
        resolved: !review.resolved,
      });
      const updatedTest = await testResultsClient.getTestResult(test.id);
      onTestResultUpdate(updatedTest);
      invalidateAnnotations();
    } catch (error) {
      console.error('Failed to update review resolution:', error);
    } finally {
      setResolvingReviewId(null);
    }
  };
  const getReviewStatusDisplay = (
    statusName: string
  ): { passed: boolean; label: string } => {
    const isPassed = isPassedStatusName(statusName);
    const name = statusName.toLowerCase();
    let label = statusName;
    if (name === 'fail') label = 'Failed';
    else if (name === 'pass') label = 'Passed';
    return { passed: isPassed, label };
  };

  const formatRelativeTime = (dateString: string) => {
    try {
      return formatDistanceToNow(new Date(dateString), {
        addSuffix: true,
      }).toUpperCase();
    } catch {
      return 'N/A';
    }
  };

  // Split reviews: mine vs others
  const allReviews = useMemo(
    () => test.test_reviews?.reviews ?? [],
    [test.test_reviews]
  );

  const sortedReviews = useMemo(
    () =>
      [...allReviews].sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      ),
    [allReviews]
  );

  const myReviews = useMemo(
    () => sortedReviews.filter(r => String(r.user.user_id) === currentUserId),
    [sortedReviews, currentUserId]
  );

  const otherReviews = useMemo(
    () => sortedReviews.filter(r => String(r.user.user_id) !== currentUserId),
    [sortedReviews, currentUserId]
  );

  // Once the user has their own review, always show all reviews automatically.
  // The showOthers toggle only matters before the user has reviewed.
  const visibleReviews =
    myReviews.length > 0 || showOthers ? sortedReviews : myReviews;

  const noReviewsAtAll = allReviews.length === 0;
  const myReviewsEmpty = myReviews.length === 0;

  return (
    <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Metadata row */}
      <Box
        sx={{ display: 'flex', alignItems: 'center', gap: 3, flexWrap: 'wrap' }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" color="text.primary">
            Automated:
          </Typography>
          <StatusChip
            passed={automatedStatus.passed}
            label={`${automatedStatus.label} ${automatedStatus.count}`}
            size="small"
            variant="outlined"
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" color="text.primary">
            Human Review:
          </Typography>
          {latestTestLevelReview ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {(() => {
                const display = getReviewStatusDisplay(
                  latestTestLevelReview.status.name
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
                            sx={{ fontSize: '14px !important' }}
                          />
                        }
                        label="Conflict"
                        size="small"
                        color="error"
                        variant="outlined"
                        sx={{
                          borderRadius: BORDER_RADIUS.pill,
                          '& .MuiChip-icon': { color: 'error.main' },
                        }}
                      />
                    )}
                  </>
                );
              })()}
            </Box>
          ) : hasMetricReviewOnly && latestMetricReview ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {(() => {
                const display = getReviewStatusDisplay(
                  latestMetricReview.status.name
                );
                return (
                  <StatusChip
                    passed={display.passed}
                    label={`${display.label} (metric)`}
                    size="small"
                    variant="outlined"
                  />
                );
              })()}
            </Box>
          ) : (
            <Chip
              label="No Review"
              size="small"
              variant="outlined"
              sx={{ borderRadius: BORDER_RADIUS.pill }}
            />
          )}
        </Box>
      </Box>

      {/* Conflict banner */}
      {hasConflict && (
        <Box
          sx={{
            bgcolor: theme =>
              alpha(
                theme.palette.warning.main,
                theme.palette.mode === 'light' ? 0.08 : 0.16
              ),
            border: '1px solid',
            borderColor: 'warning.main',
            borderRadius: BORDER_RADIUS.xs,
            px: '30px',
            py: '12px',
            display: 'flex',
            alignItems: 'flex-start',
            overflow: 'hidden',
          }}
        >
          <Box sx={{ pr: '12px', py: '4px', flexShrink: 0 }}>
            <WarningAmberIcon sx={{ fontSize: 18, color: 'warning.main' }} />
          </Box>
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
              py: '8px',
              flex: '1 0 0',
            }}
          >
            <Typography
              sx={{
                color: 'text.primary',
                fontWeight: 700,
                fontSize: 14,
                lineHeight: '20px',
              }}
            >
              Status Conflict Detected:
            </Typography>
            <Typography
              sx={{ color: 'text.secondary', fontSize: 13, lineHeight: '18px' }}
            >
              The human review status differs from the automated test result.
              This indicates the reviewer disagreed with the automation.
            </Typography>
          </Box>
        </Box>
      )}

      {/* Reviews section */}
      {noReviewsAtAll ? (
        <EmptyStateCard
          title="No reviews created yet"
          onCreateReview={
            canCreateReview ? () => setCreateOpen(true) : undefined
          }
        />
      ) : myReviewsEmpty && !showOthers ? (
        <EmptyStateCard
          title="You have not created any reviews yet"
          onCreateReview={
            canCreateReview ? () => setCreateOpen(true) : undefined
          }
          showOthersCount={otherReviews.length}
          onShowOthers={() => setShowOthers(true)}
        />
      ) : (
        <Paper
          variant="outlined"
          sx={{
            boxShadow: ELEVATION.xs,
            borderRadius: BORDER_RADIUS.md,
            overflow: 'hidden',
          }}
        >
          {/* Card header */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              px: 3,
              pt: 3,
              pb: 2,
            }}
          >
            <Typography variant="h6" color="primary" fontWeight={600}>
              Reviews
            </Typography>
            {canCreateReview && (
              <Button
                variant="outlined"
                size="small"
                startIcon={<AddIcon />}
                onClick={() => setCreateOpen(true)}
                sx={{ '& .MuiSvgIcon-root': { color: 'primary.main' } }}
              >
                Create
              </Button>
            )}
          </Box>

          {/* Review items */}
          <Stack
            divider={<Box sx={{ borderTop: 1, borderColor: 'divider' }} />}
          >
            {visibleReviews.map(review => {
              const display = getReviewStatusDisplay(review.status.name);
              const canUpdateReview =
                can(review, Capability.TestResult.UPDATE) ||
                (canCreateReview &&
                  String(review.user.user_id) === currentUserId);
              const isResolving = resolvingReviewId === review.review_id;
              return (
                <Box
                  key={review.review_id}
                  sx={{
                    px: 3,
                    py: 2,
                    opacity: review.resolved ? 0.7 : 1,
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      mb: 1.5,
                    }}
                  >
                    <Box
                      sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}
                    >
                      <Avatar
                        sx={{
                          width: 32,
                          height: 32,
                          fontSize: 12,
                          bgcolor: 'primary.main',
                        }}
                      >
                        {review.user.name.charAt(0).toUpperCase()}
                      </Avatar>
                      <Typography variant="body2" fontWeight={700}>
                        {review.user.name}
                      </Typography>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ letterSpacing: 0.5 }}
                      >
                        {formatRelativeTime(review.updated_at)}
                      </Typography>
                    </Box>
                    <Box
                      sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                    >
                      {review.resolved && (
                        <Chip
                          size="small"
                          label="Resolved"
                          variant="outlined"
                          sx={{
                            height: 24,
                            fontSize: theme => theme.typography.caption.fontSize,
                            borderRadius: BORDER_RADIUS.pill,
                            borderColor: 'success.main',
                            color: 'success.main',
                          }}
                        />
                      )}
                      <StatusChip
                        passed={display.passed}
                        label={display.label}
                        size="small"
                        variant="outlined"
                      />
                      {canUpdateReview && (
                        <Button
                          size="small"
                          variant="text"
                          disabled={isResolving}
                          onClick={e => {
                            e.stopPropagation();
                            void handleToggleResolved(review);
                          }}
                          sx={{
                            minWidth: 0,
                            px: 1,
                            textTransform: 'none',
                            fontWeight: 600,
                            fontSize: 13,
                            color: 'text.secondary',
                            '&:hover': {
                              color: 'text.primary',
                              bgcolor: 'action.hover',
                            },
                          }}
                        >
                          {review.resolved ? 'Reopen' : 'Resolve'}
                        </Button>
                      )}
                      {can(review, Capability.TestResult.DELETE) && (
                        <Tooltip title="Delete review">
                          <IconButton
                            size="small"
                            onClick={e => {
                              e.stopPropagation();
                              handleDeleteReview(review);
                            }}
                            sx={{
                              color: 'text.secondary',
                              '& .MuiSvgIcon-root': { color: 'inherit' },
                              '&:hover': {
                                bgcolor: alpha(
                                  theme.palette.error.main,
                                  theme.palette.action.focusOpacity
                                ),
                                color: 'error.main',
                              },
                            }}
                          >
                            <DeleteOutlineIcon sx={{ fontSize: 18 }} />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Box>
                  </Box>

                  {/* Comment */}
                  <Box
                    sx={{
                      bgcolor: theme.palette.greyscale.fieldSurface,
                      borderRadius: BORDER_RADIUS.xs,
                      p: 2,
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                    >
                      <MentionText text={review.comments} />
                    </Typography>
                  </Box>
                </Box>
              );
            })}
          </Stack>
        </Paper>
      )}

      {/* Create Review Drawer */}
      <ReviewJudgementDrawer
        open={createOpen}
        onClose={handleCloseCreateDrawer}
        test={test}
        sessionToken={sessionToken}
        onSave={handleReviewSaved}
        initialComment={pendingCommentRef.current?.comment}
        initialStatus={pendingCommentRef.current?.status}
        mentionableMetrics={mentionableMetrics}
        mentionableTurns={mentionableTurns}
      />

      {/* Delete Confirmation Modal */}
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

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface EmptyStateCardProps {
  title: string;
  /** Omit to hide the create button (user lacks test_result:update). */
  onCreateReview?: () => void;
  showOthersCount?: number;
  onShowOthers?: () => void;
}

function EmptyStateCard({
  title,
  onCreateReview,
  showOthersCount,
  onShowOthers,
}: EmptyStateCardProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 4,
        boxShadow: ELEVATION.xs,
        borderRadius: BORDER_RADIUS.md,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
        textAlign: 'center',
      }}
    >
      <InfoOutlinedIcon sx={{ fontSize: 32, color: 'primary.main' }} />
      <Typography variant="h6" color="primary" fontWeight={600}>
        {title}
      </Typography>
      <Typography variant="body2">
        Create a review to evaluate this test result and provide your assessment
        of the automated findings.
      </Typography>
      {onCreateReview && (
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={onCreateReview}
          sx={{
            borderRadius: BORDER_RADIUS.md,
          }}
        >
          Create review
        </Button>
      )}
      {showOthersCount !== undefined && showOthersCount > 0 && onShowOthers && (
        <Button
          variant="text"
          color="primary"
          onClick={onShowOthers}
          sx={{ textTransform: 'none', textDecoration: 'underline' }}
        >
          {`Show reviews from other users (${showOthersCount})`}
        </Button>
      )}
    </Paper>
  );
}
