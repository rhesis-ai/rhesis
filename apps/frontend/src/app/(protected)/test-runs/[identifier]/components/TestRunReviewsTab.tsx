'use client';

import React, { useMemo } from 'react';
import {
  Avatar,
  Box,
  Chip,
  CircularProgress,
  Paper,
  Typography,
} from '@mui/material';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import { formatDistanceToNow } from 'date-fns';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { isPassedStatusName } from '@/utils/test-result-status';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import type {
  Review,
  TestResultDetail,
} from '@/utils/api-client/interfaces/test-results';

interface TestRunReviewsTabProps {
  testResults: TestResultDetail[];
  loading?: boolean;
  /** Opens the result drawer on its Reviews tab, where reviews are written. */
  onViewTestResult?: (testResultId: string) => void;
}

interface RunReview {
  review: Review;
  testResultId: string;
  testLabel: string;
}

function relativeTime(dateString: string): string {
  try {
    return formatDistanceToNow(new Date(dateString), {
      addSuffix: true,
    }).toUpperCase();
  } catch {
    return 'N/A';
  }
}

/** Mirrors the labelling in TestDetailReviewsTab so a review reads the same in both places. */
function statusLabel(statusName: string): { passed: boolean; label: string } {
  const name = statusName.toLowerCase();
  if (name === 'fail') return { passed: false, label: 'Failed' };
  if (name === 'pass') return { passed: true, label: 'Passed' };
  return { passed: isPassedStatusName(statusName), label: statusName };
}

/**
 * Every human review recorded across a test run.
 *
 * Built from the test results the page already loads rather than a new endpoint:
 * each result carries its own `test_reviews.reviews`, so the run-level view is a
 * flatten and a sort. Writing and editing reviews stays in the result drawer,
 * which this links into.
 */
export default function TestRunReviewsTab({
  testResults,
  loading = false,
  onViewTestResult,
}: TestRunReviewsTabProps) {
  const reviews = useMemo<RunReview[]>(() => {
    const flattened = testResults.flatMap(result =>
      (result.test_reviews?.reviews ?? []).map(review => ({
        review,
        testResultId: String(result.id),
        testLabel:
          result.test?.prompt?.content?.slice(0, 80) ??
          `Test ${String(result.id).slice(0, 8)}`,
      }))
    );
    return flattened.sort(
      (a, b) =>
        new Date(b.review.updated_at).getTime() -
        new Date(a.review.updated_at).getTime()
    );
  }, [testResults]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (reviews.length === 0) {
    return (
      <EntityEmptyState
        icon={RateReviewOutlinedIcon}
        title="No reviews yet"
        description="Reviews are recorded against individual tests from the Tests tab. Any you add will be listed here."
      />
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {reviews.map(({ review, testResultId, testLabel }) => {
        const display = statusLabel(review.status.name);
        return (
          <Paper
            key={review.review_id}
            onClick={
              onViewTestResult
                ? () => onViewTestResult(testResultId)
                : undefined
            }
            sx={{
              p: 2.5,
              borderRadius: BORDER_RADIUS.md,
              border: theme => `1px solid ${theme.palette.greyscale.border}`,
              boxShadow: 'none',
              cursor: onViewTestResult ? 'pointer' : 'default',
              '&:hover': onViewTestResult
                ? { borderColor: 'primary.main' }
                : undefined,
            }}
          >
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                mb: 1.5,
                gap: 1,
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
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
                  {relativeTime(review.updated_at)}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {review.resolved && (
                  <Chip size="small" label="Resolved" variant="outlined" />
                )}
                <Chip
                  size="small"
                  label={display.label}
                  color={display.passed ? 'success' : 'error'}
                  variant="outlined"
                />
              </Box>
            </Box>

            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mb: 0.5 }}
            >
              {testLabel}
            </Typography>

            {review.comments && (
              <Typography variant="body2">{review.comments}</Typography>
            )}
          </Paper>
        );
      })}
    </Box>
  );
}
