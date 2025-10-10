'use client';

import React from 'react';
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
} from '@mui/material';
import GavelIcon from '@mui/icons-material/Gavel';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

interface TestDetailReviewsTabProps {
  test: TestResultDetail;
}

export default function TestDetailReviewsTab({
  test,
}: TestDetailReviewsTabProps) {
  const theme = useTheme();

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
  const hasConflict = !test.matches_review && lastReview;

  // Format date helper
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  // Get review status color and icon
  const getReviewStatusDisplay = (statusName: string) => {
    const name = statusName.toLowerCase();
    const isPassed =
      name.includes('pass') ||
      name.includes('success') ||
      name.includes('completed');

    return {
      passed: isPassed,
      icon: isPassed ? <CheckCircleOutlineIcon /> : <CancelOutlinedIcon />,
      color: isPassed ? 'success' : ('error' as const),
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
                {automatedStatus.passed ? (
                  <CheckCircleOutlineIcon
                    sx={{ color: 'success.main', fontSize: 20 }}
                  />
                ) : (
                  <CancelOutlinedIcon
                    sx={{ color: 'error.main', fontSize: 20 }}
                  />
                )}
                <Chip
                  label={automatedStatus.label}
                  size="small"
                  color={automatedStatus.passed ? 'success' : 'error'}
                  variant="outlined"
                />
                <Typography variant="caption" color="text.secondary">
                  ({automatedStatus.count} metrics)
                </Typography>
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
                        {React.cloneElement(display.icon, {
                          sx: { color: `${display.color}.main`, fontSize: 20 },
                        })}
                        <Chip
                          label={lastReview.status.name}
                          size="small"
                          color={display.color}
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
                          <Chip
                            icon={display.icon}
                            label={review.status.name}
                            size="small"
                            color={display.color}
                            variant="outlined"
                          />
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
                        <Chip
                          icon={<GavelIcon sx={{ fontSize: 14 }} />}
                          label={`${review.target.type} review`}
                          size="small"
                          variant="outlined"
                          color="default"
                        />
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
              Use the "Confirm Review" or "Overrule Judgement" actions to add a
              review.
            </Typography>
          </Paper>
        )}
      </Box>

      {/* Review Summary */}
      {test.test_reviews?.metadata && (
        <>
          <Divider sx={{ my: 3 }} />
          <Box>
            <Typography variant="h6" fontWeight={600} gutterBottom>
              Summary
            </Typography>
            <Paper
              variant="outlined"
              sx={{
                p: 2,
                backgroundColor: theme.palette.background.default,
              }}
            >
              <Stack spacing={1}>
                <Typography variant="body2">
                  <strong>Total Reviews:</strong>{' '}
                  {test.test_reviews.metadata.total_reviews}
                </Typography>
                <Typography variant="body2">
                  <strong>Last Updated:</strong>{' '}
                  {formatDate(test.test_reviews.metadata.last_updated_at)}
                </Typography>
                <Typography variant="body2">
                  <strong>Last Reviewer:</strong>{' '}
                  {test.test_reviews.metadata.last_updated_by.name}
                </Typography>
                {test.test_reviews.metadata.summary && (
                  <Typography variant="body2">
                    <strong>Summary:</strong>{' '}
                    {test.test_reviews.metadata.summary}
                  </Typography>
                )}
              </Stack>
            </Paper>
          </Box>
        </>
      )}
    </Box>
  );
}
