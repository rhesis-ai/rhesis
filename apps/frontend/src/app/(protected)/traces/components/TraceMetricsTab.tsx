'use client';

import { useMemo, useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TableContainer,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Chip,
  Stack,
  Tooltip,
  ToggleButtonGroup,
  ToggleButton,
  IconButton,
  useTheme,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import RateReviewIcon from '@mui/icons-material/RateReview';
import { alpha } from '@mui/material/styles';
import {
  SpanNode,
  TraceMetricsStatus,
  TraceReview,
  TRACE_REVIEW_TARGET_TYPES,
} from '@/utils/api-client/interfaces/telemetry';
import StatusChip from '@/components/common/StatusChip';
import { TEST_RESULT_STATUS_NAMES } from '@/utils/test-result-status';

interface MetricOverride {
  original_value: boolean;
  review_id: string;
  overridden_by: string;
  overridden_at: string;
}

interface MetricEntry {
  name: string;
  is_successful?: boolean;
  score?: number;
  reason?: string;
  backend?: string;
  class_name?: string;
  threshold?: number;
  duration_ms?: number;
  description?: string;
  override?: MetricOverride;
}

type FilterStatus = 'all' | 'passed' | 'failed';

interface TraceMetricsTabProps {
  selectedSpan: SpanNode | null;
  isConversationTrace: boolean;
  onReviewMetric?: (metricName: string) => void;
  onReviewTrace?: () => void;
  onReviewTurn?: (turnNumber: number, turnSuccess: boolean) => void;
  traceMetricsStatus?: TraceMetricsStatus | null;
  selectedTurnNumber?: number | null;
}

function MetricsTable({
  metrics,
  executionTime,
  filterStatus,
  onReviewMetric,
  metricReviewMap = new Map(),
}: {
  metrics: Record<string, MetricEntry>;
  executionTime?: number;
  filterStatus: FilterStatus;
  onReviewMetric?: (metricName: string) => void;
  metricReviewMap?: Map<string, TraceReview>;
}) {
  const theme = useTheme();
  const allEntries = Object.entries(metrics);

  const entries = allEntries.filter(([, m]) => {
    if (filterStatus === 'passed') return m.is_successful;
    if (filterStatus === 'failed') return !m.is_successful;
    return true;
  });

  if (allEntries.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
        No metrics recorded.
      </Typography>
    );
  }

  return (
    <Box>
      {executionTime !== undefined && (
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Chip
            label={`${executionTime.toFixed(0)}ms`}
            size="small"
            variant="outlined"
          />
        </Stack>
      )}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell width={onReviewMetric ? '12%' : '12%'}>
                Status
              </TableCell>
              <TableCell width={onReviewMetric ? '23%' : '25%'}>
                Metric
              </TableCell>
              <TableCell width="10%" align="right">
                Score
              </TableCell>
              <TableCell width={onReviewMetric ? '49%' : '53%'}>
                Reason
              </TableCell>
              {onReviewMetric && <TableCell width="6%" align="right" />}
            </TableRow>
          </TableHead>
          <TableBody>
            {entries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={onReviewMetric ? 5 : 4} align="center">
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ py: 2 }}
                  >
                    No {filterStatus === 'passed' ? 'passed' : 'failed'} metrics
                    found
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              entries.map(([name, metric]) => {
                const metricReview = metricReviewMap.get(name);
                const isOverruled = !!metric.override;
                const isConfirmed = !!metricReview && !isOverruled;

                return (
                  <TableRow
                    key={name}
                    sx={{
                      '&:hover': {
                        backgroundColor: theme.palette.action.hover,
                      },
                      ...(isOverruled
                        ? {
                            borderLeft: `${theme.spacing(0.375)} solid ${theme.palette.warning.main}`,
                          }
                        : isConfirmed
                          ? {
                              borderLeft: `${theme.spacing(0.375)} solid ${theme.palette.success.light}`,
                            }
                          : {}),
                    }}
                  >
                    <TableCell>
                      <Tooltip
                        title={
                          isOverruled
                            ? `Reviewed by ${metricReview?.user?.name}: status changed to ${metricReview?.status?.name}`
                            : isConfirmed
                              ? `Confirmed by ${metricReview?.user?.name}`
                              : ''
                        }
                        disableHoverListener={!metricReview}
                        arrow
                      >
                        <StatusChip
                          status={metric.is_successful ? TEST_RESULT_STATUS_NAMES.PASSED : TEST_RESULT_STATUS_NAMES.FAILED}
                          label={metric.is_successful ? TEST_RESULT_STATUS_NAMES.PASSED : TEST_RESULT_STATUS_NAMES.FAILED}
                          size="small"
                          variant="filled"
                          sx={{ minWidth: theme.spacing(10) }}
                        />
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <Tooltip
                        title={metric.description || ''}
                        arrow
                        placement="top"
                        enterDelay={300}
                        disableHoverListener={!metric.description}
                      >
                        <Typography variant="body2" fontWeight={500}>
                          {name}
                        </Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell align="right">
                      <Typography
                        variant="body2"
                        sx={{
                          fontFamily:
                            theme.typography.fontFamilyCode ?? 'monospace',
                        }}
                      >
                        {metric.score !== undefined
                          ? typeof metric.score === 'number'
                            ? metric.score.toFixed(2)
                            : metric.score
                          : '—'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {metric.reason ? (
                        <Typography
                          variant="caption"
                          sx={{ wordBreak: 'break-word' }}
                        >
                          {metric.reason}
                        </Typography>
                      ) : (
                        <Typography
                          variant="caption"
                          color="text.disabled"
                          fontStyle="italic"
                        >
                          No reason provided
                        </Typography>
                      )}
                    </TableCell>
                    {onReviewMetric && (
                      <TableCell align="right">
                        <Tooltip title="Review this metric">
                          <IconButton
                            size="small"
                            onClick={() => onReviewMetric(name)}
                            sx={{
                              padding: 0.5,
                              color: theme.palette.text.secondary,
                              '&:hover': {
                                color: theme.palette.primary.main,
                                backgroundColor: alpha(
                                  theme.palette.primary.main,
                                  theme.palette.action.hoverOpacity
                                ),
                              },
                            }}
                          >
                            <RateReviewIcon
                              sx={{ fontSize: theme.spacing(2) }}
                            />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    )}
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

export default function TraceMetricsTab({
  selectedSpan,
  isConversationTrace,
  onReviewMetric,
  onReviewTrace,
  onReviewTurn,
  traceMetricsStatus,
  selectedTurnNumber = null,
}: TraceMetricsTabProps) {
  const theme = useTheme();
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');

  const traceMetrics = selectedSpan?.trace_metrics as
    | Record<string, unknown>
    | undefined;

  const turnMetrics = useMemo(() => {
    if (!traceMetrics?.turn_metrics) return null;
    return traceMetrics.turn_metrics as {
      execution_time?: number;
      metrics?: Record<string, MetricEntry>;
    };
  }, [traceMetrics]);

  const conversationMetrics = useMemo(() => {
    if (!traceMetrics?.conversation_metrics) return null;
    return traceMetrics.conversation_metrics as {
      execution_time?: number;
      metrics?: Record<string, MetricEntry>;
    };
  }, [traceMetrics]);

  const summary = useMemo(() => {
    const allMetrics: Record<string, MetricEntry> = {
      ...(turnMetrics?.metrics || {}),
      ...(conversationMetrics?.metrics || {}),
    };
    const entries = Object.values(allMetrics);
    const total = entries.length;
    const passed = entries.filter(m => m.is_successful).length;
    const passRate = total > 0 ? (passed / total) * 100 : 0;
    return { total, passed, failed: total - passed, passRate };
  }, [turnMetrics, conversationMetrics]);

  const metricReviewMap = useMemo(() => {
    const map = new Map<string, TraceReview>();
    const reviews = selectedSpan?.trace_reviews?.reviews;
    if (!reviews) return map;
    for (const review of reviews) {
      if (
        review.target?.type === TRACE_REVIEW_TARGET_TYPES.METRIC &&
        review.target.reference
      ) {
        const existing = map.get(review.target.reference);
        if (
          !existing ||
          (review.updated_at || '') > (existing.updated_at || '')
        ) {
          map.set(review.target.reference, review);
        }
      }
    }
    return map;
  }, [selectedSpan?.trace_reviews]);

  const automatedTurnSuccess = useMemo(() => {
    const metrics = turnMetrics?.metrics;
    if (!metrics || Object.keys(metrics).length === 0) return undefined;
    return Object.values(metrics).every(m => m.is_successful);
  }, [turnMetrics]);

  const turnOverrides = useMemo(() => {
    const overrides = traceMetrics?.turn_overrides as
      | Record<string, { success?: boolean; override?: MetricOverride }>
      | undefined;
    if (!overrides)
      return {} as Record<
        number,
        { success: boolean; override: MetricOverride }
      >;
    const result: Record<
      number,
      { success: boolean; override: MetricOverride }
    > = {};
    for (const [key, data] of Object.entries(overrides)) {
      const num = parseInt(key, 10);
      if (
        !isNaN(num) &&
        data?.override &&
        typeof data.success === 'boolean'
      ) {
        result[num] = { success: data.success, override: data.override };
      }
    }
    return result;
  }, [traceMetrics]);

  const turnReviewMap = useMemo(() => {
    const map = new Map<number, TraceReview>();
    const reviews = selectedSpan?.trace_reviews?.reviews;
    if (!reviews) return map;
    for (const review of reviews) {
      if (
        review.target?.type === TRACE_REVIEW_TARGET_TYPES.TURN &&
        review.target.reference
      ) {
        const turnNum = parseInt(
          review.target.reference.replace(/\D/g, ''),
          10
        );
        if (!isNaN(turnNum)) {
          const existing = map.get(turnNum);
          if (
            !existing ||
            (review.updated_at || '') > (existing.updated_at || '')
          ) {
            map.set(turnNum, review);
          }
        }
      }
    }
    return map;
  }, [selectedSpan?.trace_reviews]);

  if (!traceMetrics || (!turnMetrics && !conversationMetrics)) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="text.secondary">
          No trace metrics available for this span.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2, overflow: 'auto' }}>
      <Stack spacing={3}>
        {/* Header with title and filter */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Typography variant="h6" fontWeight={600}>
            Metrics Overview
          </Typography>
          <ToggleButtonGroup
            value={filterStatus}
            exclusive
            onChange={(_, val) => val && setFilterStatus(val)}
            size="small"
            aria-label="metric status filter"
          >
            <ToggleButton value="all" aria-label="all metrics">
              All
            </ToggleButton>
            <ToggleButton value="passed" aria-label="passed metrics">
              Passed
            </ToggleButton>
            <ToggleButton value="failed" aria-label="failed metrics">
              Failed
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Summary Cards */}
        <Grid container spacing={2}>
          {/* Overall Trace Status */}
          {traceMetricsStatus && (
            <Grid size={{ xs: 12, md: 4 }}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardContent
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    height: '100%',
                    '&:last-child': { pb: theme.spacing(2) },
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      gutterBottom
                    >
                      Trace Status
                    </Typography>
                    {onReviewTrace && (
                      <Tooltip title="Review overall trace">
                        <IconButton
                          size="small"
                          onClick={onReviewTrace}
                          sx={{
                            color: theme.palette.text.secondary,
                            '&:hover': {
                              color: theme.palette.primary.main,
                              backgroundColor: alpha(
                                theme.palette.primary.main,
                                theme.palette.action.hoverOpacity
                              ),
                            },
                          }}
                        >
                          <RateReviewIcon
                            sx={{ fontSize: theme.spacing(2.5) }}
                          />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Box>
                  <StatusChip
                    status={traceMetricsStatus}
                    label={traceMetricsStatus}
                    size="small"
                    variant="filled"
                  />
                  <Typography variant="caption" color="text.secondary">
                    {summary.passed}/{summary.total} metrics passed
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          )}

          {/* Overall Performance */}
          <Grid size={{ xs: 12, md: 4 }}>
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardContent>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  gutterBottom
                >
                  Overall Performance
                </Typography>
                <Typography variant="h5" fontWeight={600}>
                  {summary.passRate.toFixed(1)}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {summary.passed} of {summary.total} metrics passed
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          {/* Passed / Failed */}
          <Grid size={{ xs: 12, md: 4 }}>
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardContent>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  gutterBottom
                >
                  Results
                </Typography>
                <Stack direction="row" spacing={3} alignItems="baseline">
                  <Box>
                    <Typography
                      variant="h5"
                      fontWeight={600}
                      color="success.main"
                    >
                      {summary.passed}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      passed
                    </Typography>
                  </Box>
                  <Box>
                    <Typography
                      variant="h5"
                      fontWeight={600}
                      color="error.main"
                    >
                      {summary.failed}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      failed
                    </Typography>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Turn Metrics Section */}
        {turnMetrics && turnMetrics.metrics && (
          <Card variant="outlined">
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  mb: 1,
                }}
              >
                <Box>
                  <Typography
                    variant="subtitle1"
                    gutterBottom
                    fontWeight={600}
                  >
                    Turn Metrics
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mb: 2 }}
                  >
                    Per-turn evaluation results for this span.
                  </Typography>
                </Box>
                {isConversationTrace && selectedTurnNumber != null && (() => {
                  const override = turnOverrides[selectedTurnNumber];
                  const turnSuccess = override
                    ? override.success
                    : (automatedTurnSuccess ?? false);
                  const review = turnReviewMap.get(selectedTurnNumber);
                  const isOverruled = !!override;
                  const isConfirmed = !!review && !isOverruled;

                  return (
                    <Stack
                      direction="row"
                      spacing={0.75}
                      alignItems="center"
                      sx={{ flexShrink: 0, ml: 2 }}
                    >
                      <Tooltip
                        title={
                          isOverruled
                            ? `Reviewed by ${review?.user?.name}: status changed to ${review?.status?.name}`
                            : isConfirmed
                              ? `Confirmed by ${review?.user?.name}`
                              : ''
                        }
                        disableHoverListener={
                          !isOverruled && !isConfirmed
                        }
                        arrow
                      >
                        <Chip
                          label={`Turn ${selectedTurnNumber}`}
                          size="small"
                          color={turnSuccess ? 'success' : 'error'}
                          variant="outlined"
                          sx={{
                            ...(isOverruled
                              ? {
                                  borderColor:
                                    theme.palette.warning.main,
                                  borderWidth: theme.spacing(0.25),
                                }
                              : isConfirmed
                                ? {
                                    borderColor:
                                      theme.palette.success.light,
                                    borderWidth: theme.spacing(0.25),
                                  }
                                : {}),
                          }}
                        />
                      </Tooltip>
                      <StatusChip
                        status={turnSuccess ? TEST_RESULT_STATUS_NAMES.PASSED : TEST_RESULT_STATUS_NAMES.FAILED}
                        label={turnSuccess ? 'Passed' : 'Failed'}
                        size="small"
                        variant="filled"
                      />
                      {onReviewTurn && (
                        <Tooltip
                          title={`Review Turn ${selectedTurnNumber}`}
                        >
                          <IconButton
                            size="small"
                            onClick={() =>
                              onReviewTurn(
                                selectedTurnNumber,
                                turnSuccess
                              )
                            }
                            sx={{
                              padding: theme.spacing(0.25),
                              color: theme.palette.text.secondary,
                              '&:hover': {
                                color: theme.palette.primary.main,
                                backgroundColor: alpha(
                                  theme.palette.primary.main,
                                  theme.palette.action.hoverOpacity
                                ),
                              },
                            }}
                          >
                            <RateReviewIcon
                              sx={{
                                fontSize: theme.spacing(2),
                              }}
                            />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Stack>
                  );
                })()}
              </Box>
              <MetricsTable
                metrics={turnMetrics.metrics}
                executionTime={turnMetrics.execution_time}
                filterStatus={filterStatus}
                onReviewMetric={onReviewMetric}
                metricReviewMap={metricReviewMap}
              />
            </CardContent>
          </Card>
        )}

        {/* Conversation Metrics Section */}
        {isConversationTrace &&
          conversationMetrics &&
          conversationMetrics.metrics && (
            <Card variant="outlined">
              <CardContent>
                <Typography variant="subtitle1" gutterBottom fontWeight={600}>
                  Conversation Metrics
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 2 }}
                >
                  Full-conversation evaluation results (shared across all
                  turns).
                </Typography>
              <MetricsTable
                metrics={conversationMetrics.metrics}
                executionTime={conversationMetrics.execution_time}
                filterStatus={filterStatus}
                onReviewMetric={onReviewMetric}
                metricReviewMap={metricReviewMap}
              />
              </CardContent>
            </Card>
          )}
      </Stack>
    </Box>
  );
}
