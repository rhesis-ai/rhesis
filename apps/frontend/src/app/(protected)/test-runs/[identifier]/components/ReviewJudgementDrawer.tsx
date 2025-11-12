'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Alert,
  Stack,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status } from '@/utils/api-client/interfaces/status';
import StatusChip from '@/components/common/StatusChip';
import { findStatusByCategory } from '@/utils/testResultStatus';

interface ReviewJudgementDrawerProps {
  open: boolean;
  onClose: () => void;
  test: TestResultDetail | null;
  currentUserName: string;
  sessionToken: string;
  onSave: (testId: string, reviewData: ReviewData) => Promise<void>;
}

export interface ReviewData {
  originalStatus: 'passed' | 'failed';
  newStatus: 'passed' | 'failed';
  reason: string;
  overruledBy: string;
  overruledAt: string;
}

export default function ReviewJudgementDrawer({
  open,
  onClose,
  test,
  currentUserName,
  sessionToken,
  onSave,
}: ReviewJudgementDrawerProps) {
  const [newStatus, setNewStatus] = useState<'passed' | 'failed'>('passed');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [loadingStatuses, setLoadingStatuses] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Calculate original test status
  const getOriginalStatus = (): 'passed' | 'failed' => {
    if (!test) return 'failed';
    const metrics = test.test_metrics?.metrics || {};
    const metricValues = Object.values(metrics);
    const totalMetrics = metricValues.length;
    const passedMetrics = metricValues.filter(m => m.is_successful).length;
    return totalMetrics > 0 && passedMetrics === totalMetrics
      ? 'passed'
      : 'failed';
  };

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
      } catch (err) {
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
      const original = getOriginalStatus();
      // Default to opposite of original status
      setNewStatus(original === 'passed' ? 'failed' : 'passed');
      setReason('');
      setError('');
    }
  }, [open, test]);

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

    // Only prevent matching original status if there's NO existing review
    // If there's already a review, allow changing back to original (updating the review)
    const hasExistingReview = !!test.last_review;
    if (newStatus === originalStatus && !hasExistingReview) {
      setError(
        'New status must be different from the automated result. Use "Confirm Review" to agree with the automated result.'
      );
      return;
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
        { type: 'test', reference: null }
      );

      // Create review data for parent component
      const reviewData: ReviewData = {
        originalStatus,
        newStatus,
        reason: reason.trim(),
        overruledBy: currentUserName,
        overruledAt: new Date().toISOString(),
      };

      await onSave(test.id, reviewData);
      onClose();
    } catch (err) {
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
      saveButtonText={submitting ? 'Saving...' : 'Submit Review'}
      error={error}
      width={600}
      loading={submitting || loadingStatuses}
    >
      <Stack spacing={3}>
        {/* Info Alert */}
        <Alert
          severity="info"
          sx={{
            bgcolor: theme => `${theme.palette.info.main}0A`,
            border: 1,
            borderColor: 'info.light',
          }}
        >
          <Typography variant="body2">
            You are about to provide a manual review for this test result. This
            action will be recorded and attributed to you.
          </Typography>
        </Alert>

        {/* Original Status Section */}
        <Box>
          <Typography variant="body2" fontWeight={600} gutterBottom>
            Original Status
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            <StatusChip
              passed={originalStatus === 'passed'}
              label={originalStatus === 'passed' ? 'Passed' : 'Failed'}
              size="small"
              variant="filled"
            />
            <Typography variant="body2" color="text.secondary">
              {passedMetrics}/{totalMetrics} metrics passed
            </Typography>
          </Box>
        </Box>

        {/* New Status Selection */}
        <Box>
          <Typography variant="body2" fontWeight={600} gutterBottom>
            New Status *
          </Typography>
          <ToggleButtonGroup
            value={newStatus}
            exclusive
            onChange={handleStatusChange}
            aria-label="test status"
            fullWidth
            sx={{ mt: 1 }}
          >
            <ToggleButton
              value="passed"
              aria-label="passed"
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'success.main',
                  color: 'success.contrastText',
                  '&:hover': {
                    backgroundColor: 'success.dark',
                  },
                },
              }}
            >
              <CheckCircleOutlineIcon sx={{ mr: 1, fontSize: 20 }} />
              Pass
            </ToggleButton>
            <ToggleButton
              value="failed"
              aria-label="failed"
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'error.main',
                  color: 'error.contrastText',
                  '&:hover': {
                    backgroundColor: 'error.dark',
                  },
                },
              }}
            >
              <CancelOutlinedIcon sx={{ mr: 1, fontSize: 20 }} />
              Fail
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Reason Field */}
        <Box>
          <Typography variant="body2" fontWeight={600} gutterBottom>
            Review Comments *
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={4}
            placeholder="Provide your reasoning for this review..."
            value={reason}
            onChange={e => {
              setReason(e.target.value);
              setError('');
            }}
            helperText={`${reason.length} characters (minimum 10 required)`}
            sx={{ mt: 1 }}
          />
        </Box>

        {/* Attribution Info */}
        <Box
          sx={{
            p: 2,
            bgcolor: 'action.hover',
            borderRadius: theme => theme.shape.borderRadius,
            border: 1,
            borderColor: 'divider',
          }}
        >
          <Typography variant="body2" fontWeight={600} gutterBottom>
            Attribution
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
            Reviewed by: <strong>{currentUserName}</strong>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Date: <strong>{new Date().toLocaleString()}</strong>
          </Typography>
        </Box>
      </Stack>
    </BaseDrawer>
  );
}
