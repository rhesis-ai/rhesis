'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  Stack,
  Chip,
  useTheme,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import BaseDrawer from '@/components/common/BaseDrawer';
import {
  TestResultDetail,
  REVIEW_TARGET_TYPES,
  REVIEW_TARGET_LABELS,
} from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status } from '@/utils/api-client/interfaces/status';
import StatusChip from '@/components/common/StatusChip';
import { findStatusByCategory } from '@/utils/test-result-status';
import MentionTextInput, {
  MentionOption,
  inferReviewTarget,
  InferredTarget,
} from '@/components/common/MentionTextInput';

interface ReviewJudgementDrawerProps {
  open: boolean;
  onClose: () => void;
  test: TestResultDetail | null;
  sessionToken: string;
  onSave: (testId: string) => Promise<void>;
  initialComment?: string;
  initialStatus?: 'passed' | 'failed';
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
}


export default function ReviewJudgementDrawer({
  open,
  onClose,
  test,
  sessionToken,
  onSave,
  initialComment,
  initialStatus,
  mentionableMetrics = [],
  mentionableTurns = [],
}: ReviewJudgementDrawerProps) {
  const theme = useTheme();
  const [newStatus, setNewStatus] = useState<'passed' | 'failed'>('passed');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [loadingStatuses, setLoadingStatuses] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Infer target from comment text
  const inferredTarget: InferredTarget = useMemo(
    () => inferReviewTarget(reason),
    [reason]
  );

  const targetLabel = useMemo(
    () => REVIEW_TARGET_LABELS[inferredTarget.type] ?? inferredTarget.type,
    [inferredTarget]
  );

  // Calculate automated status of the targeted item
  const getOriginalStatus = useCallback((): 'passed' | 'failed' => {
    if (!test) return 'failed';

    if (
      inferredTarget.type === REVIEW_TARGET_TYPES.METRIC &&
      inferredTarget.reference
    ) {
      const metrics = test.test_metrics?.metrics || {};
      const metric = Object.entries(metrics).find(
        ([name]) => name === inferredTarget.reference
      );
      return metric?.[1]?.is_successful ? 'passed' : 'failed';
    }

    if (
      inferredTarget.type === REVIEW_TARGET_TYPES.TURN &&
      inferredTarget.reference
    ) {
      const turns = test.test_output?.conversation_summary || [];
      const turnNum = parseInt(
        inferredTarget.reference.replace(/\D/g, ''),
        10
      );
      const turn = turns.find(
        (t: { turn: number }) => t.turn === turnNum
      );
      return turn?.success ? 'passed' : 'failed';
    }

    const metrics = test.test_metrics?.metrics || {};
    const metricValues = Object.values(metrics);
    const totalMetrics = metricValues.length;
    const passedMetrics = metricValues.filter(m => m.is_successful).length;
    return totalMetrics > 0 && passedMetrics === totalMetrics
      ? 'passed'
      : 'failed';
  }, [test, inferredTarget]);

  const originalStatus = getOriginalStatus();

  // Fetch statuses for TestResult entity type
  useEffect(() => {
    const fetchStatuses = async () => {
      if (!sessionToken || statuses.length > 0) return;

      try {
        setLoadingStatuses(true);
        const clientFactory = new ApiClientFactory(sessionToken);
        const statusClient = clientFactory.getStatusClient();
        const fetchedStatuses = await statusClient.getStatuses({
          entity_type: 'TestResult',
        });
        setStatuses(fetchedStatuses);
      } catch (_err) {
        setError('Failed to load status options');
      } finally {
        setLoadingStatuses(false);
      }
    };

    fetchStatuses();
  }, [sessionToken, statuses.length]);

  // Reset form when drawer opens or test changes
  useEffect(() => {
    if (open && test) {
      const metrics = test.test_metrics?.metrics || {};
      const metricValues = Object.values(metrics);
      const allPassed =
        metricValues.length > 0 &&
        metricValues.every(m => m.is_successful);
      const defaultOriginal = allPassed ? 'passed' : 'failed';
      setNewStatus(
        initialStatus ?? (defaultOriginal === 'passed' ? 'failed' : 'passed')
      );
      setReason(initialComment ?? '');
      setError('');
    }
  }, [open, test, initialComment, initialStatus]);

  const handleStatusChange = (
    _event: React.MouseEvent<HTMLElement>,
    value: 'passed' | 'failed' | null
  ) => {
    if (value !== null) {
      setNewStatus(value);
      setError('');
    }
  };

  const handleSave = async () => {
    // Validation
    if (!reason.trim()) {
      setError('Please provide a reason for the review.');
      return;
    }

    if (reason.trim().length < 10) {
      setError('Reason must be at least 10 characters long.');
      return;
    }

    if (!test || !sessionToken) return;

    // For test_result targets without an existing review, prevent matching original
    // For metric/turn targets, always allow (they're specific overrides)
    if (inferredTarget.type === REVIEW_TARGET_TYPES.TEST_RESULT) {
      const hasExistingReview = !!test.last_review;
      if (newStatus === originalStatus && !hasExistingReview) {
        setError(
          'New status must be different from the automated result. '
          + 'Use "Confirm Review" to agree with the automated result.'
        );
        return;
      }
    }

    // Find the status ID for the new status using centralized utility
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
        inferredTarget
      );

      await onSave(test.id);
      onClose();
    } catch (_err) {
      setError('Failed to save review. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    setReason('');
    setError('');
    onClose();
  };

  if (!test) return null;

  const metrics = test.test_metrics?.metrics || {};
  const metricValues = Object.values(metrics);
  const totalMetrics = metricValues.length;
  const passedMetrics = metricValues.filter(m => m.is_successful).length;

  return (
    <BaseDrawer
      open={open}
      onClose={handleCancel}
      title="Provide Test Review"
      titleIcon={<RateReviewOutlinedIcon />}
      onSave={handleSave}
      anchor="right"
      saveButtonText={submitting ? 'Saving...' : 'Submit Review'}
      error={error}
      width={theme.spacing(75)}
      loading={submitting || loadingStatuses}
    >
      <Stack spacing={3}>
        {/* Review Target Indicator */}
        <Box>
          <Typography variant="body2" fontWeight={600} gutterBottom>
            Review Target
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            <Chip
              icon={<TrackChangesIcon />}
              label={targetLabel}
              size="small"
              color={
                inferredTarget.type === REVIEW_TARGET_TYPES.METRIC
                  ? 'secondary'
                  : inferredTarget.type === REVIEW_TARGET_TYPES.TURN
                    ? 'info'
                    : 'default'
              }
              variant="outlined"
            />
          </Box>
        </Box>

        {/* Automated Status of Target */}
        <Box>
          <Typography variant="body2" fontWeight={600} gutterBottom>
            Current Automated Status
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            <StatusChip
              passed={originalStatus === 'passed'}
              label={originalStatus === 'passed' ? 'Passed' : 'Failed'}
              size="small"
              variant="filled"
            />
            {inferredTarget.type === REVIEW_TARGET_TYPES.TEST_RESULT && (
              <Typography variant="body2" color="text.secondary">
                {passedMetrics}/{totalMetrics} metrics passed
              </Typography>
            )}
            {inferredTarget.type === REVIEW_TARGET_TYPES.METRIC &&
              inferredTarget.reference && (
                <Typography variant="body2" color="text.secondary">
                  Score:{' '}
                  {metrics[inferredTarget.reference]?.score ?? 'N/A'}
                </Typography>
              )}
          </Box>
        </Box>

        {/* New Status Selection */}
        <Box>
          <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
            New Status *
          </Typography>
          <ToggleButtonGroup
            value={newStatus}
            exclusive
            onChange={handleStatusChange}
            aria-label="test status"
            size="small"
            fullWidth
          >
            <ToggleButton
              value="passed"
              aria-label="passed"
              sx={{
                '&.Mui-selected': {
                  backgroundColor: theme.palette.success.main,
                  color: theme.palette.success.contrastText,
                  '& .MuiSvgIcon-root': { color: 'inherit' },
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
              aria-label="failed"
              sx={{
                '&.Mui-selected': {
                  backgroundColor: theme.palette.error.main,
                  color: theme.palette.error.contrastText,
                  '& .MuiSvgIcon-root': { color: 'inherit' },
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

        {/* Review Comments */}
        <MentionTextInput
          label="Review Comments *"
          value={reason}
          onChange={(val) => {
            setReason(val);
            setError('');
          }}
          placeholder="Explain your review decision... Type @ to mention"
          mentionableMetrics={mentionableMetrics}
          mentionableTurns={mentionableTurns}
          error={!!error}
          helperText={
            error || `${reason.length} characters (minimum 10 required)`
          }
          minRows={4}
        />

      </Stack>
    </BaseDrawer>
  );
}
