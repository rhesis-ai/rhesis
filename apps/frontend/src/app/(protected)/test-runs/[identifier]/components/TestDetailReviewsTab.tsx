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
  TextField,
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
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status } from '@/utils/api-client/interfaces/status';
import { DeleteModal } from '@/components/common/DeleteModal';
import StatusChip from '@/components/common/StatusChip';
import { findStatusByCategory } from '@/utils/test-result-status';

interface TestDetailReviewsTabProps {
  test: TestResultDetail;
  sessionToken: string;
  onTestResultUpdate: (updatedTest: TestResultDetail) => void;
  currentUserId: string;
  initialComment?: string;
  initialStatus?: 'passed' | 'failed';
  onCommentUsed?: () => void;
}

export default function TestDetailReviewsTab({
  test,
  sessionToken,
  onTestResultUpdate,
  currentUserId,
  initialComment = '',
  initialStatus,
  onCommentUsed,
}: TestDetailReviewsTabProps) {
  const theme = useTheme();

  // Review creation state
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [newStatus, setNewStatus] = useState<'passed' | 'failed'>('passed');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [statuses, setStatuses] = useState<Status[]>([]);

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [reviewToDelete, setReviewToDelete] = useState<any>(null);
  const [deleting, setDeleting] = useState(false);

  // Handle initial comment and status from turn review
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

  // Fetch available statuses
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

  // Handle review submission
  const handleSubmitReview = async () => {
    if (!reason.trim()) {
      setError('Please provide a reason for your review.');
      return;
    }

    // Find the appropriate status using centralized utility
    const targetStatus = findStatusByCategory(
      statuses,
      newStatus === 'passed' ? 'passed' : 'failed'
    );

    if (!targetStatus) {
      setError('Could not find appropriate status. Please try again.');
      return;
    }

    try {
      setSubmitting(true);
      setError('');

      // Create the review via API
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();

      await testResultsClient.createReview(
        test.id,
        targetStatus.id,
        reason.trim(),
        { type: 'test', reference: null }
      );

      // Refresh the test result to get updated reviews
      const updatedTest = await testResultsClient.getTestResult(test.id);
      onTestResultUpdate(updatedTest);

      // Reset form
      setReason('');
      setShowReviewForm(false);
    } catch (err) {
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

  // Handle delete review
  const handleDeleteReview = (review: any) => {
    setReviewToDelete(review);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!reviewToDelete) return;

    try {
      setDeleting(true);

      // Delete the review via API
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();

      await testResultsClient.deleteReview(test.id, reviewToDelete.review_id);

      // Refresh the test result to get updated reviews
      const updatedTest = await testResultsClient.getTestResult(test.id);
      onTestResultUpdate(updatedTest);

      // Close dialog
      setDeleteDialogOpen(false);
      setReviewToDelete(null);
    } catch (err) {
      // Could add error handling here
    } finally {
      setDeleting(false);
    }
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
    setReviewToDelete(null);
  };

  // Calculate automated status for comparison
  const getAutomatedStatus = () => {
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
  };

  const automatedStatus = getAutomatedStatus();
  const hasReviews =
    test.test_reviews?.reviews && test.test_reviews.reviews.length > 0;
  const lastReview = test.last_review;

  // Calculate conflict ourselves (don't trust backend's matches_review)
  // A conflict exists if the review decision differs from the automated decision
  let hasConflict = false;
  if (lastReview && lastReview.status?.name) {
    const reviewStatusName = lastReview.status.name.toLowerCase();
    const reviewPassed =
      reviewStatusName.includes('pass') ||
      reviewStatusName.includes('success') ||
      reviewStatusName.includes('completed');

    hasConflict = reviewPassed !== automatedStatus.passed;
  }

  // Format date helper
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return 'N/A';
    return date.toLocaleString();
  };

  // Get review status with normalized display label
  const getReviewStatusDisplay = (
    statusName: string
  ): {
    passed: boolean;
    label: string;
  } => {
    const name = statusName.toLowerCase();
    const isPassed =
      name.includes('pass') ||
      name.includes('success') ||
      name.includes('completed');

    // Normalize status labels for consistency
    let label = statusName;
    if (name === 'fail') {
      label = 'Failed';
    } else if (name === 'pass') {
      label = 'Passed';
    }

    return {
      passed: isPassed,
      label,
    };
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Status Overview */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" fontWeight={600} gutterBottom>
          Review Status
        </Typography>

        {/* Automated vs Review Status Comparison */}
        <Paper
          variant="outlined"
          sx={{
            p: 2,
            backgroundColor: hasConflict
              ? `${theme.palette.warning.main}08`
              : theme.palette.background.default,
            border: hasConflict
              ? `1px solid ${theme.palette.warning.light}`
              : undefined,
          }}
        >
          <Stack spacing={2}>
            {/* Automated Status */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography
                variant="body2"
                fontWeight={600}
                sx={{ minWidth: 120 }}
              >
                Automated:
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <StatusChip
                  passed={automatedStatus.passed}
                  label={`${automatedStatus.label} ${automatedStatus.count}`}
                  size="small"
                  variant="outlined"
                />
              </Box>
            </Box>

            {/* Review Status */}
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
                            icon={<WarningAmberIcon sx={{ fontSize: 14 }} />}
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

        {/* Conflict Alert */}
        {hasConflict && (
          <Alert severity="warning" icon={<WarningAmberIcon />} sx={{ mt: 2 }}>
            <Typography variant="body2">
              <strong>Status Conflict Detected:</strong> The human review status
              differs from the automated test result. This indicates the
              reviewer disagreed with the automation.
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
            {test
              .test_reviews!.reviews.sort(
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
                        ? `${theme.palette.primary.main}08`
                        : theme.palette.background.default,
                      border: isLatest
                        ? `1px solid ${theme.palette.primary.light}`
                        : undefined,
                    }}
                  >
                    <Stack spacing={2}>
                      {/* Review Header */}
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
                          <Avatar sx={{ width: 32, height: 32, fontSize: 14 }}>
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
                          {/* Delete button - only show for review owner */}
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
                                    backgroundColor:
                                      theme.palette.error.main + '20',
                                    color: theme.palette.error.main,
                                  },
                                }}
                              >
                                <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                              </IconButton>
                            </Tooltip>
                          )}
                        </Box>
                      </Box>

                      {/* Review Content */}
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
                            {review.comments}
                          </Typography>
                        </Paper>
                      </Box>

                      {/* Review Metadata */}
                      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                        {review.target.reference && (
                          <Chip
                            label={`Target: ${review.target.reference}`}
                            size="small"
                            variant="outlined"
                            color="default"
                          />
                        )}
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
                fontSize: 48,
                color: theme.palette.text.disabled,
                mb: 2,
              }}
            />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No Reviews Yet
            </Typography>
            <Typography variant="body2" color="text.secondary">
              This test result has not been reviewed by any human evaluators.
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

                {/* Status Toggle */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
                    Review Status
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
                      <CheckCircleOutlineIcon sx={{ mr: 1, fontSize: 18 }} />
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
                      <CancelOutlinedIcon sx={{ mr: 1, fontSize: 18 }} />
                      Fail
                    </ToggleButton>
                  </ToggleButtonGroup>
                </Box>

                {/* Comments */}
                <Box sx={{ mb: 3 }}>
                  <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
                    Comments
                  </Typography>
                  <TextField
                    multiline
                    rows={4}
                    fullWidth
                    placeholder="Explain your review decision..."
                    value={reason}
                    onChange={e => setReason(e.target.value)}
                    error={!!error}
                    helperText={error}
                  />
                </Box>

                {/* Actions */}
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
