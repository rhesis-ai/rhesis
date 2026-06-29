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
import {
  TestResultDetail,
  Review,
} from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { can } from '@/utils/affordances';
import { alpha } from '@mui/material/styles';
import { DeleteModal } from '@/components/common/DeleteModal';
import StatusChip from '@/components/common/StatusChip';
import { isPassedStatusName } from '@/utils/test-result-status';
import {
  MentionOption,
  renderMentionText,
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

  const [createOpen, setCreateOpen] = useState(false);
  const [showOthers, setShowOthers] = useState(false);

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

  // Conflict: human review disagrees with automated
  const hasConflict = useMemo(() => {
    if (!lastReview?.status?.name) return false;
    return (
      isPassedStatusName(lastReview.status.name) !== automatedStatus.passed
    );
  }, [lastReview, automatedStatus]);

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
          {lastReview ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {(() => {
                const display = getReviewStatusDisplay(lastReview.status.name);
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
                            sx={{
                              fontSize: '14px !important',
                              color: '#de3355 !important',
                            }}
                          />
                        }
                        label="Conflict"
                        size="small"
                        sx={{
                          borderRadius: BORDER_RADIUS.pill,
                          bgcolor: '#fdedee',
                          color: '#de3355',
                          border: 'none',
                          '& .MuiChip-label': { color: '#de3355' },
                        }}
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
            bgcolor: '#ffab24',
            borderRadius: BORDER_RADIUS.xs,
            px: '30px',
            py: '12px',
            display: 'flex',
            alignItems: 'flex-start',
            overflow: 'hidden',
          }}
        >
          <Box sx={{ pr: '12px', py: '7px', flexShrink: 0 }}>
            <WarningAmberIcon sx={{ fontSize: 22, color: '#fff !important' }} />
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
                color: 'white',
                fontWeight: 700,
                fontSize: 18,
                lineHeight: '25px',
              }}
            >
              Status Conflict Detected:
            </Typography>
            <Typography
              sx={{ color: 'white', fontSize: 16, lineHeight: '24px' }}
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
          onCreateReview={() => setCreateOpen(true)}
        />
      ) : myReviewsEmpty && !showOthers ? (
        <EmptyStateCard
          title="You have not created any reviews yet"
          onCreateReview={() => setCreateOpen(true)}
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
            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon />}
              onClick={() => setCreateOpen(true)}
              sx={{ '& .MuiSvgIcon-root': { color: 'primary.main' } }}
            >
              Create
            </Button>
          </Box>

          {/* Review items */}
          <Stack
            divider={<Box sx={{ borderTop: 1, borderColor: 'divider' }} />}
          >
            {visibleReviews.map(review => {
              const display = getReviewStatusDisplay(review.status.name);
              return (
                <Box key={review.review_id} sx={{ px: 3, py: 2 }}>
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
                          fontSize: '0.75rem',
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
                      sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
                    >
                      <StatusChip
                        passed={display.passed}
                        label={display.label}
                        size="small"
                        variant="outlined"
                      />
                      {can(review, Capability.TestResult.DELETE) && (
                        <Tooltip title="Delete review">
                          <IconButton
                            size="small"
                            onClick={e => {
                              e.stopPropagation();
                              handleDeleteReview(review);
                            }}
                            sx={{
                              color: 'primary.main',
                              '& .MuiSvgIcon-root': { color: 'primary.main' },
                              '&:hover': {
                                bgcolor: alpha(
                                  theme.palette.error.main,
                                  theme.palette.action.focusOpacity
                                ),
                                color: 'error.main',
                                '& .MuiSvgIcon-root': { color: 'error.main' },
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
  onCreateReview: () => void;
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
      <Button
        variant="contained"
        startIcon={<AddIcon />}
        onClick={onCreateReview}
        sx={{
          borderRadius: BORDER_RADIUS.md,
          // Override the MuiDrawer theme rule that sets all icons to body color
          '& .MuiSvgIcon-root': { color: '#FFFFFF' },
        }}
      >
        Create review
      </Button>
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
