'use client';

import { useMemo } from 'react';
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
  useTheme,
} from '@mui/material';
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

interface TraceMetricsTabProps {
  selectedSpan: SpanNode | null;
  isConversationTrace: boolean;
}

function MetricsTable({
  metrics,
  executionTime,
}: {
  metrics: Record<string, MetricEntry>;
  executionTime?: number;
}) {
  const theme = useTheme();
  const entries = Object.entries(metrics);

  if (entries.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
        No metrics recorded.
      </Typography>
    );
  }

  const passedCount = entries.filter(([, m]) => m.is_successful).length;

  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        <Chip
          label={`${passedCount}/${entries.length} passed`}
          size="small"
          color={passedCount === entries.length ? 'success' : 'warning'}
          variant="outlined"
        />
        {executionTime !== undefined && (
          <Chip
            label={`${executionTime.toFixed(0)}ms`}
            size="small"
            variant="outlined"
          />
        )}
      </Stack>
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
            {entries.map(([name, metric]) => (
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
            ))}
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
        {turnMetrics && turnMetrics.metrics && (
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" gutterBottom fontWeight={600}>
                Turn Metrics
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Per-turn evaluation results for this span.
              </Typography>
              <MetricsTable
                metrics={turnMetrics.metrics}
                executionTime={turnMetrics.execution_time}
              />
            </CardContent>
          </Card>
        )}

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
                />
              </CardContent>
            </Card>
          )}
      </Stack>
    </Box>
  );
}
