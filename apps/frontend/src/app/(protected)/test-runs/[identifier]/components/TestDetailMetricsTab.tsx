'use client';

import React, { useMemo, useState } from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Grid,
  Card,
  CardContent,
  ToggleButtonGroup,
  ToggleButton,
  Tooltip,
  useTheme,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

interface TestDetailMetricsTabProps {
  test: TestResultDetail;
  behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
}

interface MetricSummary {
  total: number;
  passed: number;
  failed: number;
  passRate: number;
}

export default function TestDetailMetricsTab({
  test,
  behaviors,
}: TestDetailMetricsTabProps) {
  const theme = useTheme();
  const [filterStatus, setFilterStatus] = useState<'all' | 'passed' | 'failed'>(
    'all'
  );

  const metricsData = useMemo(() => {
    const testMetrics = test.test_metrics?.metrics || {};
    const allMetrics: Array<{
      name: string;
      description?: string;
      passed: boolean;
      fullMetricData: any;
      behaviorName: string;
    }> = [];

    behaviors.forEach(behavior => {
      behavior.metrics.forEach(metric => {
        const metricResult = testMetrics[metric.name];
        if (metricResult) {
          allMetrics.push({
            name: metric.name,
            description: metric.description,
            passed: metricResult.is_successful,
            fullMetricData: metricResult, // Store the full data
            behaviorName: behavior.name,
          });
        }
      });
    });

    return allMetrics;
  }, [test, behaviors]);

  // Filter metrics based on selected status
  const filteredMetrics = useMemo(() => {
    if (filterStatus === 'all') return metricsData;
    return metricsData.filter(m =>
      filterStatus === 'passed' ? m.passed : !m.passed
    );
  }, [metricsData, filterStatus]);

  // Calculate summary statistics
  const summary: MetricSummary = useMemo(() => {
    const total = metricsData.length;
    const passed = metricsData.filter(m => m.passed).length;
    const failed = total - passed;
    const passRate = total > 0 ? (passed / total) * 100 : 0;

    return { total, passed, failed, passRate };
  }, [metricsData]);

  // Find best and worst performing behaviors
  const behaviorStats = useMemo(() => {
    const stats = new Map<string, { passed: number; total: number }>();

    behaviors.forEach(behavior => {
      const behaviorMetrics = metricsData.filter(
        m => m.behaviorName === behavior.name
      );
      const passed = behaviorMetrics.filter(m => m.passed).length;
      const total = behaviorMetrics.length;

      if (total > 0) {
        stats.set(behavior.name, { passed, total });
      }
    });

    const entries = Array.from(stats.entries()).map(
      ([name, { passed, total }]) => ({
        name,
        passed,
        total,
        rate: (passed / total) * 100,
      })
    );

    entries.sort((a, b) => b.rate - a.rate);

    // If only one behavior, don't show best/worst distinction
    const hasMultipleBehaviors = entries.length > 1;

    return {
      best: entries[0],
      worst: hasMultipleBehaviors ? entries[entries.length - 1] : undefined,
      hasMultipleBehaviors,
    };
  }, [metricsData, behaviors]);

  const handleFilterChange = (
    _event: React.MouseEvent<HTMLElement>,
    newFilter: 'all' | 'passed' | 'failed' | null
  ) => {
    if (newFilter !== null) {
      setFilterStatus(newFilter);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Summary Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={behaviorStats.hasMultipleBehaviors ? 4 : 6}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
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

        {behaviorStats.hasMultipleBehaviors ? (
          <>
            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    gutterBottom
                  >
                    Best Behavior
                  </Typography>
                  <Typography variant="h6" fontWeight={600} noWrap>
                    {behaviorStats.best?.name || 'N/A'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {behaviorStats.best
                      ? `${behaviorStats.best.rate.toFixed(0)}% pass rate`
                      : 'No data'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    gutterBottom
                  >
                    Worst Behavior
                  </Typography>
                  <Typography variant="h6" fontWeight={600} noWrap>
                    {behaviorStats.worst?.name || 'N/A'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {behaviorStats.worst
                      ? `${behaviorStats.worst.rate.toFixed(0)}% pass rate`
                      : 'No data'}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </>
        ) : (
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Behavior
                </Typography>
                <Typography variant="h6" fontWeight={600} noWrap>
                  {behaviorStats.best?.name || 'N/A'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {behaviorStats.best
                    ? `${behaviorStats.best.rate.toFixed(0)}% pass rate`
                    : 'No data'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>

      {/* Filter Toggle */}
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="subtitle2" fontWeight={600}>
          Metrics Breakdown
        </Typography>
        <ToggleButtonGroup
          value={filterStatus}
          exclusive
          onChange={handleFilterChange}
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

      {/* Metrics Table */}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell width="12%">Status</TableCell>
              <TableCell width="18%">Behavior</TableCell>
              <TableCell width="25%">Metric</TableCell>
              <TableCell width="45%">Reason</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredMetrics.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center">
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ py: 2 }}
                  >
                    No metrics found
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              filteredMetrics.map((metric, index) => (
                <TableRow
                  key={`${metric.behaviorName}-${metric.name}-${index}`}
                  sx={{
                    '&:hover': {
                      backgroundColor: theme.palette.action.hover,
                    },
                  }}
                >
                  <TableCell>
                    <Chip
                      icon={
                        metric.passed ? (
                          <CheckCircleOutlineIcon />
                        ) : (
                          <CancelOutlinedIcon />
                        )
                      }
                      label={metric.passed ? 'Pass' : 'Fail'}
                      size="small"
                      color={metric.passed ? 'success' : 'error'}
                      sx={{ minWidth: 80 }}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={metric.behaviorName}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Box
                      sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
                    >
                      <Typography variant="body2" fontWeight={500}>
                        {metric.name}
                      </Typography>
                      {metric.description && (
                        <Tooltip
                          title={metric.description}
                          arrow
                          placement="top"
                          enterDelay={300}
                          leaveDelay={0}
                        >
                          <InfoOutlinedIcon
                            sx={{
                              fontSize: 16,
                              color: 'action.active',
                              opacity: 0.6,
                              cursor: 'help',
                              '&:hover': {
                                opacity: 1,
                              },
                            }}
                          />
                        </Tooltip>
                      )}
                    </Box>
                  </TableCell>
                  <TableCell>
                    {metric.fullMetricData.reason ? (
                      <Typography
                        variant="caption"
                        sx={{
                          wordBreak: 'break-word',
                        }}
                      >
                        {metric.fullMetricData.reason}
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
