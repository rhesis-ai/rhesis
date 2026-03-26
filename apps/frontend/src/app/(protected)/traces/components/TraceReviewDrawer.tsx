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
  SpanNode,
  TRACE_REVIEW_TARGET_TYPES,
  TRACE_REVIEW_TARGET_LABELS,
  TraceReviewTargetType,
} from '@/utils/api-client/interfaces/telemetry';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status } from '@/utils/api-client/interfaces/status';
import StatusChip from '@/components/common/StatusChip';
import { findStatusByCategory } from '@/utils/test-result-status';
import MentionTextInput, {
  MentionOption,
  inferReviewTarget,
  InferredTarget,
} from '@/components/common/MentionTextInput';

interface TraceReviewDrawerProps {
  open: boolean;
  onClose: () => void;
  selectedSpan: SpanNode | null;
  sessionToken: string;
  onSave: () => Promise<void>;
  initialComment?: string;
  initialStatus?: 'passed' | 'failed';
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
}

interface MetricEntry {
  is_successful?: boolean;
  score?: number;
}

function getAllTraceMetrics(
  traceMetrics: Record<string, unknown> | null | undefined
): Record<string, MetricEntry> {
  if (!traceMetrics) return {};
  const result: Record<string, MetricEntry> = {};
  for (const section of ['turn_metrics', 'conversation_metrics']) {
    const sectionData = traceMetrics[section] as
      | Record<string, unknown>
      | undefined;
    const metrics = (sectionData?.metrics ?? {}) as Record<string, MetricEntry>;
    Object.assign(result, metrics);
  }
  return result;
}

export default function TraceReviewDrawer({
  open,
  onClose,
  selectedSpan,
  sessionToken,
  onSave,
  initialComment,
  initialStatus,
  mentionableMetrics = [],
  mentionableTurns = [],
}: TraceReviewDrawerProps) {
  const theme = useTheme();
  const [newStatus, setNewStatus] = useState<'passed' | 'failed'>('passed');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [loadingStatuses, setLoadingStatuses] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const rawTarget: InferredTarget = useMemo(
    () => inferReviewTarget(reason),
    [reason]
  );

  const traceTarget = useMemo(() => {
    if (rawTarget.type === 'metric') {
      return {
        type: TRACE_REVIEW_TARGET_TYPES.METRIC as TraceReviewTargetType,
        reference: rawTarget.reference,
      };
    }
    if (rawTarget.type === 'turn') {
      return {
        type: TRACE_REVIEW_TARGET_TYPES.TURN as TraceReviewTargetType,
        reference: rawTarget.reference,
      };
    }
    return {
      type: TRACE_REVIEW_TARGET_TYPES.TRACE as TraceReviewTargetType,
      reference: null as string | null,
    };
  }, [rawTarget]);

  const targetLabel = useMemo(
    () =>
      TRACE_REVIEW_TARGET_LABELS[
        rawTarget.type as keyof typeof TRACE_REVIEW_TARGET_LABELS
      ] ?? 'Trace',
    [rawTarget]
  );

  const allMetrics = useMemo(
    () =>
      getAllTraceMetrics(
        selectedSpan?.trace_metrics as Record<string, unknown> | undefined
      ),
    [selectedSpan]
  );

  const getTurnMetricsAutomatedStatus = useCallback((): 'passed' | 'failed' => {
    const traceMetrics = selectedSpan?.trace_metrics as
      | Record<string, unknown>
      | undefined;
    const turnSection = traceMetrics?.turn_metrics as
      | Record<string, unknown>
      | undefined;
    if (!turnSection) return 'failed';

    const metrics = turnSection.metrics as
      | Record<string, { is_successful?: boolean }>
      | undefined;
    if (metrics && Object.keys(metrics).length > 0) {
      return Object.values(metrics).every(m => m?.is_successful)
        ? 'passed'
        : 'failed';
    }
    return 'failed';
  }, [selectedSpan]);

  const getOriginalStatus = useCallback((): 'passed' | 'failed' => {
    if (!selectedSpan) return 'failed';

    if (traceTarget.type === 'turn') {
      return getTurnMetricsAutomatedStatus();
    }

    if (traceTarget.type === 'metric' && traceTarget.reference) {
      const metric = allMetrics[traceTarget.reference];
      return metric?.is_successful ? 'passed' : 'failed';
    }

    const metricValues = Object.values(allMetrics);
    const totalMetrics = metricValues.length;
    const passedMetrics = metricValues.filter(m => m.is_successful).length;
    return totalMetrics > 0 && passedMetrics === totalMetrics
      ? 'passed'
      : 'failed';
  }, [selectedSpan, traceTarget, allMetrics, getTurnMetricsAutomatedStatus]);

  const originalStatus = getOriginalStatus();

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

  useEffect(() => {
    if (open && selectedSpan) {
      const metricValues = Object.values(allMetrics);
      const allPassed =
        metricValues.length > 0 && metricValues.every(m => m.is_successful);
      const defaultOriginal = allPassed ? 'passed' : 'failed';
      setNewStatus(
        initialStatus ?? (defaultOriginal === 'passed' ? 'failed' : 'passed')
      );
      setReason(initialComment ?? '');
      setError('');
    }
  }, [open, selectedSpan, initialComment, initialStatus, allMetrics]);

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
    if (!reason.trim()) {
      setError('Please provide a reason for the review.');
      return;
    }

    if (reason.trim().length < 10) {
      setError('Reason must be at least 10 characters long.');
      return;
    }

    if (!selectedSpan?.id || !sessionToken) return;

    if (traceTarget.type === 'trace' || traceTarget.type === 'turn') {
      const hasExistingReview = !!selectedSpan.last_review;
      if (newStatus === originalStatus && !hasExistingReview) {
        setError(
          'New status must be different from the automated result. ' +
            'Use the Reviews tab to confirm the automated result.'
        );
        return;
      }
    }

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

      const clientFactory = new ApiClientFactory(sessionToken);
      const telemetryClient = clientFactory.getTelemetryClient();

      await telemetryClient.createReview(
        selectedSpan.id,
        targetStatus.id,
        reason.trim(),
        traceTarget
      );

      await onSave();
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

  if (!selectedSpan) return null;

  const metricValues = Object.values(allMetrics);
  const totalMetrics = metricValues.length;
  const passedMetrics = metricValues.filter(m => m.is_successful).length;

  return (
    <BaseDrawer
      open={open}
      onClose={handleCancel}
      title="Provide Trace Review"
      titleIcon={<RateReviewOutlinedIcon />}
      onSave={handleSave}
      anchor="right"
      saveButtonText={submitting ? 'Saving...' : 'Submit Review'}
      error={error}
      width={theme.spacing(75)}
      loading={submitting || loadingStatuses}
    >
      <Stack spacing={3}>
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
                traceTarget.type === 'metric'
                  ? 'secondary'
                  : traceTarget.type === 'turn'
                    ? 'info'
                    : 'default'
              }
              variant="outlined"
            />
          </Box>
        </Box>

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
            {traceTarget.type === 'trace' && (
              <Typography variant="body2" color="text.secondary">
                {passedMetrics}/{totalMetrics} metrics passed
              </Typography>
            )}
            {traceTarget.type === 'metric' && traceTarget.reference && (
              <Typography variant="body2" color="text.secondary">
                Score: {allMetrics[traceTarget.reference]?.score ?? 'N/A'}
              </Typography>
            )}
            {traceTarget.type === 'turn' && (
              <Typography variant="body2" color="text.secondary">
                Based on turn metrics ({passedMetrics}/{totalMetrics} passed)
              </Typography>
            )}
          </Box>
        </Box>

        <Box>
          <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
            New Status *
          </Typography>
          <ToggleButtonGroup
            value={newStatus}
            exclusive
            onChange={handleStatusChange}
            aria-label="trace status"
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
              <CancelOutlinedIcon sx={{ mr: 1, fontSize: 'body2.fontSize' }} />
              Fail
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        <MentionTextInput
          label="Review Comments *"
          value={reason}
          onChange={val => {
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
