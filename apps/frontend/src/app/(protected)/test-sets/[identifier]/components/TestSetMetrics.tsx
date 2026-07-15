'use client';

import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Chip,
  CircularProgress,
  Alert,
  Link as MuiLink,
  IconButton,
  Tooltip,
  Button,
} from '@mui/material';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import NumbersIcon from '@mui/icons-material/Numbers';
import CategoryIcon from '@mui/icons-material/Category';
import BugReportIcon from '@mui/icons-material/BugReport';
import HandymanIcon from '@mui/icons-material/Handyman';
import StorageIcon from '@mui/icons-material/Storage';
import CloseIcon from '@mui/icons-material/Close';
import AddIcon from '@mui/icons-material/Add';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSetMetric } from '@/utils/api-client/interfaces/test-set';
import { useNotifications } from '@/components/common/NotificationContext';
import SelectMetricsDialog from '@/components/common/SelectMetricsDialog';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import type { UUID } from 'crypto';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { testSetKeys } from '@/constants/query-keys';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface TestSetMetricsProps {
  testSetId: string;
  sessionToken: string;
}

const getBackendIcon = (backendType?: string) => {
  if (!backendType) return <StorageIcon fontSize="small" />;

  switch (backendType.toLowerCase()) {
    case 'deepeval':
    case 'ragas':
      return <HandymanIcon fontSize="small" />;
    case 'garak':
      return <BugReportIcon fontSize="small" />;
    default:
      return <StorageIcon fontSize="small" />;
  }
};

const getScoreTypeIcon = (scoreType?: string) => {
  if (!scoreType) return <NumbersIcon fontSize="small" />;

  switch (scoreType.toLowerCase()) {
    case 'numeric':
      return <NumbersIcon fontSize="small" />;
    case 'categorical':
      return <CategoryIcon fontSize="small" />;
    default:
      return <NumbersIcon fontSize="small" />;
  }
};

export default function TestSetMetrics({
  testSetId,
  sessionToken,
}: TestSetMetricsProps) {
  const { status } = useSession();
  const [isRemoving, setIsRemoving] = useState<string | null>(null);
  const [metricsDialogOpen, setMetricsDialogOpen] = useState(false);
  const canEditTestSet = useCan(Capability.TestSet.UPDATE);

  const notifications = useNotifications();
  const queryClient = useQueryClient();

  const metricsQueryKey = [
    ...testSetKeys.detail(testSetId),
    'metrics',
  ] as const;

  const {
    data: metrics = [],
    isLoading: loading,
    error: fetchError,
  } = useQuery({
    queryKey: metricsQueryKey,
    queryFn: () =>
      new ApiClientFactory(sessionToken)
        .getTestSetsClient()
        .getTestSetMetrics(testSetId),
    enabled: isAuthenticated(status),
  });

  const error = fetchError
    ? fetchError instanceof Error
      ? fetchError.message
      : 'Failed to load metrics'
    : null;

  const handleAddMetric = async (metricId: UUID) => {
    try {
      await new ApiClientFactory(sessionToken)
        .getTestSetsClient()
        .addMetricToTestSet(testSetId, metricId as string);
      queryClient.invalidateQueries({ queryKey: metricsQueryKey });
      notifications.show('Metric added to test set successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (err: unknown) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to add metric to test set',
        { severity: 'error', autoHideDuration: 4000 }
      );
    }
  };

  const handleRemoveMetric = async (metricId: string) => {
    try {
      setIsRemoving(metricId);
      await new ApiClientFactory(sessionToken)
        .getTestSetsClient()
        .removeMetricFromTestSet(testSetId, metricId);
      queryClient.invalidateQueries({ queryKey: metricsQueryKey });
      notifications.show('Metric removed from test set successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    } catch (err: unknown) {
      notifications.show(
        err instanceof Error
          ? err.message
          : 'Failed to remove metric from test set',
        { severity: 'error', autoHideDuration: 4000 }
      );
    } finally {
      setIsRemoving(null);
    }
  };

  const excludeMetricIds = metrics.map(m => m.id as UUID);

  const addMetricButton = canEditTestSet ? (
    <Button
      size="small"
      startIcon={<AddIcon />}
      onClick={() => setMetricsDialogOpen(true)}
    >
      Add Metric
    </Button>
  ) : null;

  const metricsDialog = canEditTestSet ? (
    <SelectMetricsDialog
      open={metricsDialogOpen}
      onClose={() => setMetricsDialogOpen(false)}
      onSelect={handleAddMetric}
      sessionToken={sessionToken}
      excludeMetricIds={excludeMetricIds}
      title="Add Metric to Test Set"
      subtitle="Select a metric to add to this test set"
    />
  ) : null;

  if (loading) {
    return (
      <Box sx={{ mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 1,
          }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
            Test Set Metrics
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 2 }}>
          <CircularProgress size={20} />
          <Typography variant="body2" color="text.secondary">
            Loading metrics...
          </Typography>
        </Box>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 1,
          }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
            Test Set Metrics
          </Typography>
          {addMetricButton}
        </Box>
        <Alert severity="error" sx={{ mt: 1 }}>
          {error}
        </Alert>
        {metricsDialog}
      </Box>
    );
  }

  // No metrics associated - show default message with add button
  if (metrics.length === 0) {
    return (
      <Box sx={{ mb: 3 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 1,
          }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
            Test Set Metrics
          </Typography>
          {addMetricButton}
        </Box>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 1,
            p: 2,
            bgcolor: 'action.hover',
            borderRadius: theme => theme.shape.borderRadius * 0.25,
          }}
        >
          <InfoOutlinedIcon
            color="info"
            fontSize="small"
            sx={{ mt: 0.25, flexShrink: 0 }}
          />
          <Typography variant="body2" color="text.secondary">
            No test set metrics configured. When executing this test set,
            metrics configured on each test&apos;s behavior will be used for
            evaluation.
          </Typography>
        </Box>
        {metricsDialog}
      </Box>
    );
  }

  // Display associated metrics
  return (
    <Box sx={{ mb: 3 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 1,
        }}
      >
        <Typography variant="subtitle1" sx={{ fontWeight: 'medium' }}>
          Test Set Metrics
        </Typography>
        {addMetricButton}
      </Box>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 1.5,
        }}
      >
        {metrics.map(metric => (
          <Box
            key={metric.id as string}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 1,
              p: 2,
              border: 1,
              borderColor: 'divider',
              borderRadius: theme => theme.shape.borderRadius * 0.25,
              backgroundColor: 'background.paper',
              position: 'relative',
              '&:hover': {
                bgcolor: 'action.hover',
              },
            }}
          >
            {/* Remove button */}
            {canEditTestSet && (
              <Tooltip title="Remove metric from test set">
                <IconButton
                  size="small"
                  onClick={() => handleRemoveMetric(metric.id as string)}
                  disabled={isRemoving === metric.id}
                  sx={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    padding: 0.5,
                  }}
                >
                  {isRemoving === metric.id ? (
                    <CircularProgress size={16} />
                  ) : (
                    <CloseIcon fontSize="small" />
                  )}
                </IconButton>
              </Tooltip>
            )}

            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                pr: 4, // Make room for remove button
              }}
            >
              <AutoGraphIcon
                fontSize="small"
                color="primary"
                sx={{ flexShrink: 0 }}
              />
              <MuiLink
                component={Link}
                href={`/metrics/${metric.id}`}
                underline="hover"
                sx={{
                  fontWeight: 'medium',
                  color: 'text.primary',
                  '&:hover': {
                    color: 'primary.main',
                  },
                }}
              >
                {metric.name}
              </MuiLink>
            </Box>
            {metric.description && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{
                  pl: 3.5,
                  pr: 4,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                }}
              >
                {metric.description}
              </Typography>
            )}
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', pl: 3.5 }}>
              {metric.backend_type?.type_value && (
                <Chip
                  size="small"
                  icon={getBackendIcon(metric.backend_type.type_value)}
                  label={
                    metric.backend_type.type_value.charAt(0).toUpperCase() +
                    metric.backend_type.type_value.slice(1).toLowerCase()
                  }
                  variant="outlined"
                />
              )}
              {metric.score_type && (
                <Chip
                  size="small"
                  icon={getScoreTypeIcon(metric.score_type)}
                  label={
                    metric.score_type.charAt(0).toUpperCase() +
                    metric.score_type.slice(1).toLowerCase()
                  }
                  variant="outlined"
                />
              )}
              {metric.threshold !== undefined && metric.threshold !== null && (
                <Chip
                  size="small"
                  label={`Threshold: ${metric.threshold_operator || '>='} ${metric.threshold}`}
                  variant="outlined"
                />
              )}
            </Box>
          </Box>
        ))}
      </Box>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block', mt: 1.5 }}
      >
        These metrics will be used for evaluation when executing this test set,
        overriding any behavior-level metric configurations.
      </Typography>

      {metricsDialog}
    </Box>
  );
}
