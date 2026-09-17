'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
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
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { annotationKeys } from '@/constants/query-keys';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import type { Annotation } from '@/utils/api-client/interfaces/annotation';

interface TestRunAnnotationsTabProps {
  testRunId: string;
  /** Opens the result drawer on its Annotations tab, where annotations are written. */
  onViewTestResult?: (testResultId: string) => void;
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

/** Mirrors the labelling in the annotations panel so a verdict reads the same everywhere. */
function statusLabel(statusName: string): { passed: boolean; label: string } {
  const name = statusName.toLowerCase();
  if (name === 'fail') return { passed: false, label: 'Failed' };
  if (name === 'pass') return { passed: true, label: 'Passed' };
  return { passed: isPassedStatusName(statusName), label: statusName };
}

/**
 * Every annotation recorded across a test run.
 *
 * Scoped server-side by `test_run_id`, which covers the run's test results and
 * the traces it produced. It used to be a flatten over every result the page
 * had loaded, so an annotation on a result outside the current page was
 * invisible, and the tab could not render until all results had arrived.
 * Writing and editing stays in the result drawer, which this links into.
 */
export default function TestRunAnnotationsTab({
  testRunId,
  onViewTestResult,
}: TestRunAnnotationsTabProps) {
  const isAuthenticated = useIsAuthenticated();

  const { data: annotations = [], isLoading } = useQuery({
    queryKey: annotationKeys.list(`test_run:${testRunId}`),
    queryFn: () =>
      new ApiClientFactory()
        .getAnnotationsClient()
        .getAnnotations({
          test_run_id: testRunId,
          sort_by: 'updated_at',
          sort_order: 'desc',
          limit: 100,
        })
        .then(page => page.data),
    enabled: isAuthenticated && !!testRunId,
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (annotations.length === 0) {
    return (
      <EntityEmptyState
        icon={RateReviewOutlinedIcon}
        title="No annotations yet"
        description="Annotations are recorded against individual tests from the Tests tab. Any you add will be listed here."
      />
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {annotations.map((annotation: Annotation) => {
        const display = statusLabel(annotation.status?.name ?? '');
        const label =
          annotation.context?.requirement_name ??
          annotation.context?.span_name ??
          `Test result ${String(annotation.entity_id).slice(0, 8)}`;
        const openable =
          onViewTestResult && annotation.entity_type === 'TestResult';
        return (
          <Paper
            key={annotation.id}
            onClick={
              openable
                ? () => onViewTestResult?.(String(annotation.entity_id))
                : undefined
            }
            sx={{
              p: 2.5,
              borderRadius: BORDER_RADIUS.md,
              border: theme => `1px solid ${theme.palette.greyscale.border}`,
              boxShadow: 'none',
              cursor: openable ? 'pointer' : 'default',
              '&:hover': openable ? { borderColor: 'primary.main' } : undefined,
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
                  sx={theme => ({
                    width: theme.spacing(4),
                    height: theme.spacing(4),
                    fontSize: theme.typography.caption.fontSize,
                    bgcolor: 'primary.main',
                  })}
                >
                  {(annotation.user?.name ?? '').charAt(0).toUpperCase()}
                </Avatar>
                <Typography
                  variant="body2"
                  sx={theme => ({
                    fontWeight: theme.typography.fontWeightBold,
                  })}
                >
                  {annotation.user?.name}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ letterSpacing: 0.5 }}
                >
                  {relativeTime(annotation.updated_at)}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {annotation.resolved && (
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
              {label}
            </Typography>

            {annotation.comments && (
              <Typography variant="body2">{annotation.comments}</Typography>
            )}
          </Paper>
        );
      })}
    </Box>
  );
}
