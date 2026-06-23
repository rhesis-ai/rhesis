'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status } from '@/utils/api-client/interfaces/status';
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
  const [selectedStatusId, setSelectedStatusId] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [loadingStatuses, setLoadingStatuses] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Infer review target from mention syntax in comment text
  const inferredTarget: InferredTarget = useMemo(
    () => inferReviewTarget(reason),
    [reason]
  );

  const passStatus = useMemo(
    () => findStatusByCategory(statuses, 'passed'),
    [statuses]
  );
  const failStatus = useMemo(
    () => findStatusByCategory(statuses, 'failed'),
    [statuses]
  );

  // Fetch statuses for TestResult entity type on mount
  useEffect(() => {
    const fetchStatuses = async () => {
      if (!sessionToken || statuses.length > 0) return;
      try {
        setLoadingStatuses(true);
        const clientFactory = new ApiClientFactory(sessionToken);
        const statusClient = clientFactory.getStatusClient();
        const fetched = await statusClient.getStatuses({
          entity_type: 'TestResult',
        });
        setStatuses(fetched);
      } catch (_err) {
        setError('Failed to load status options');
      } finally {
        setLoadingStatuses(false);
      }
    };
    fetchStatuses();
  }, [sessionToken, statuses.length]);

  // Reset form when drawer opens (intentionally excludes initialComment/initialStatus
  // from deps so parent state resets don't clear a form the user is actively filling)
  useEffect(() => {
    if (!open) return;
    setReason(initialComment ?? '');
    setError('');
    setSelectedStatusId('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Pre-select initial status once statuses are available and nothing is selected yet
  useEffect(() => {
    if (!open || selectedStatusId || statuses.length === 0 || !initialStatus)
      return;
    const matching = findStatusByCategory(statuses, initialStatus);
    if (matching) setSelectedStatusId(String(matching.id));
  }, [open, statuses, initialStatus, selectedStatusId]);

  const handleSave = async () => {
    if (!reason.trim()) {
      setError('Please provide a comment for your review.');
      return;
    }

    if (reason.trim().length < 10) {
      setError('Comment must be at least 10 characters long.');
      return;
    }

    if (!selectedStatusId) {
      setError('Please select a status for this review.');
      return;
    }

    if (!test || !sessionToken) return;

    try {
      setSubmitting(true);
      setError('');

      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();

      await testResultsClient.createReview(
        test.id,
        selectedStatusId,
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

  const isSaveDisabled =
    !selectedStatusId ||
    reason.trim().length < 10 ||
    submitting ||
    loadingStatuses;

  if (!test) return null;

  return (
    <BaseDrawer
      open={open}
      onClose={handleCancel}
      title="Create Review"
      onSave={handleSave}
      anchor="right"
      saveButtonText="Save"
      saveDisabled={isSaveDisabled}
      error={error}
      loading={submitting || loadingStatuses}
    >
      {/* Pass / Fail toggle */}
      <Box>
        <Typography
          variant="body2"
          sx={{ mb: 1, fontWeight: 500, color: 'text.secondary' }}
        >
          New Status
        </Typography>
        <ToggleButtonGroup
          value={selectedStatusId}
          exclusive
          onChange={(_, val) => {
            if (val !== null) {
              setSelectedStatusId(val);
              setError('');
            }
          }}
          fullWidth
          disabled={loadingStatuses}
          sx={{ height: 44 }}
        >
          {passStatus && (
            <ToggleButton
              value={String(passStatus.id)}
              sx={{
                flex: 1,
                gap: 1,
                fontWeight: 500,
                '&.Mui-selected': {
                  bgcolor: 'success.main',
                  color: '#fff',
                  '&:hover': { bgcolor: 'success.dark' },
                  '& .MuiSvgIcon-root': { color: '#fff' },
                },
              }}
            >
              <CheckCircleOutlineIcon sx={{ fontSize: 18 }} />
              Pass
            </ToggleButton>
          )}
          {failStatus && (
            <ToggleButton
              value={String(failStatus.id)}
              sx={{
                flex: 1,
                gap: 1,
                fontWeight: 500,
                '&.Mui-selected': {
                  bgcolor: 'error.main',
                  color: '#fff',
                  '&:hover': { bgcolor: 'error.dark' },
                  '& .MuiSvgIcon-root': { color: '#fff' },
                },
              }}
            >
              <CancelOutlinedIcon sx={{ fontSize: 18 }} />
              Fail
            </ToggleButton>
          )}
        </ToggleButtonGroup>
      </Box>

      {/* Comment field */}
      <MentionTextInput
        label="Comment"
        value={reason}
        onChange={val => {
          setReason(val);
          setError('');
        }}
        placeholder="Explain your review decision... Type @ to mention"
        mentionableMetrics={mentionableMetrics}
        mentionableTurns={mentionableTurns}
        error={!!error && !selectedStatusId}
        helperText="Add a comment to support your review decision"
        minRows={4}
      />
    </BaseDrawer>
  );
}
