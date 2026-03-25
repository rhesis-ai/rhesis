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
  useTheme,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { SpanNode } from '@/utils/api-client/interfaces/telemetry';
import StatusChip from '@/components/common/StatusChip';

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
}

type FilterStatus = 'all' | 'passed' | 'failed';

interface TraceMetricsTabProps {
  selectedSpan: SpanNode | null;
  isConversationTrace: boolean;
}

function MetricsTable({
  metrics,
  executionTime,
  filterStatus,
}: {
  metrics: Record<string, MetricEntry>;
  executionTime?: number;
  filterStatus: FilterStatus;
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
              <TableCell width="12%">Status</TableCell>
              <TableCell width="25%">Metric</TableCell>
              <TableCell width="10%" align="right">
                Score
              </TableCell>
              <TableCell width="53%">Reason</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {entries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center">
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
              entries.map(([name, metric]) => (
                <TableRow
                  key={name}
                  sx={{
                    '&:hover': {
                      backgroundColor: theme.palette.action.hover,
                    },
                  }}
                >
                  <TableCell>
                    <StatusChip
                      status={metric.is_successful ? 'Pass' : 'Fail'}
                      label={metric.is_successful ? 'Pass' : 'Fail'}
                      size="small"
                      variant="filled"
                      sx={{ minWidth: theme.spacing(10) }}
                    />
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
                </TableRow>
              ))
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
}: TraceMetricsTabProps) {
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

        {/* Summary Card */}
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Card>
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
          <Grid size={{ xs: 6, md: 4 }}>
            <Card>
              <CardContent>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  gutterBottom
                >
                  Passed
                </Typography>
                <Typography
                  variant="h5"
                  fontWeight={600}
                  color="success.main"
                >
                  {summary.passed}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  metrics successful
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, md: 4 }}>
            <Card>
              <CardContent>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  gutterBottom
                >
                  Failed
                </Typography>
                <Typography variant="h5" fontWeight={600} color="error.main">
                  {summary.failed}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  metrics failed
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Turn Metrics Section */}
        {turnMetrics && turnMetrics.metrics && (
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" gutterBottom fontWeight={600}>
                Turn Metrics
              </Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mb: 2 }}
              >
                Per-turn evaluation results for this span.
              </Typography>
              <MetricsTable
                metrics={turnMetrics.metrics}
                executionTime={turnMetrics.execution_time}
                filterStatus={filterStatus}
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
                />
              </CardContent>
            </Card>
          )}
      </Stack>
    </Box>
  );
}
