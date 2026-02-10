'use client';

/* eslint-disable react/no-array-index-key -- Metrics display lists */

import React, { useMemo, useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  ToggleButtonGroup,
  ToggleButton,
  useTheme,
  LinearProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
  Collapse,
  IconButton,
  TableContainer,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  Tooltip,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import StatusChip from '@/components/common/StatusChip';
import {
  MetricsSource,
  getMetricsSourceLabel,
} from '@/utils/api-client/interfaces/test-configuration';

interface TestDetailMetricsTabProps {
  test: TestResultDetail;
  behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
  /** Source of metrics used in this test run */
  metricsSource?: MetricsSource | string;
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
  metricsSource,
}: TestDetailMetricsTabProps) {
  const theme = useTheme();
  const [filterStatus, setFilterStatus] = useState<'all' | 'passed' | 'failed'>(
    'all'
  );
  const [reasonExpanded, setReasonExpanded] = useState(false);
  const [criteriaExpanded, setCriteriaExpanded] = useState(false);

  // Determine if this is a multi-turn test by checking for Goal Achievement/Evaluation metric
  // Support flexible matching: any metric containing "goal" + ("achievement" OR "evaluation")
  const goalAchievementMetric = useMemo(() => {
    const testMetrics = test.test_metrics?.metrics || {};
    return Object.entries(testMetrics).find(([metricName]) => {
      const lowerName = metricName.toLowerCase();
      return (
        lowerName.includes('goal') &&
        (lowerName.includes('achievement') || lowerName.includes('evaluation'))
      );
    })?.[1];
  }, [test]);
  const isMultiTurn = !!goalAchievementMetric;

  const metricsData = useMemo(() => {
    const testMetrics = test.test_metrics?.metrics || {};
    const allMetrics: Array<{
      name: string;
      description?: string;
      passed: boolean;
      fullMetricData: any;
      behaviorName: string;
    }> = [];

    // Check if we have behavior definitions
    const hasBehaviors = Boolean(behaviors && behaviors.length > 0);

    // Determine if we should use behavior-based grouping
    // Only use behavior grouping when:
    // 1. metricsSource is 'behavior' (or not set)
    // 2. We have behaviors defined
    // 3. It's not a multi-turn test
    const useBehaviorGrouping =
      (metricsSource === MetricsSource.BEHAVIOR || !metricsSource) &&
      hasBehaviors &&
      !isMultiTurn;

    if (useBehaviorGrouping) {
      // Handle behavior-based metrics (single-turn tests with behavior source)
      behaviors.forEach(behavior => {
        behavior.metrics.forEach(metric => {
          const metricResult = testMetrics[metric.name];
          if (metricResult) {
            allMetrics.push({
              name: metric.name,
              description: metric.description,
              passed: metricResult.is_successful,
              fullMetricData: metricResult,
              behaviorName: behavior.name,
            });
          }
        });
      });
    }

    // Handle direct metrics:
    // - When metricsSource is test_set or execution_time
    // - When multi-turn tests
    // - When no behaviors are defined
    // - When behavior grouping didn't find any metrics
    if (!useBehaviorGrouping || allMetrics.length === 0) {
      // Use appropriate category name based on metrics source or test type
      let categoryName: string;
      if (metricsSource && metricsSource !== MetricsSource.BEHAVIOR) {
        // test_set or execution_time
        categoryName = getMetricsSourceLabel(metricsSource);
      } else if (isMultiTurn) {
        categoryName = 'Multi-Turn Test';
      } else if (metricsSource === MetricsSource.BEHAVIOR && hasBehaviors) {
        // Fallback for behavior source when behavior metrics didn't match
        categoryName = 'Behavior Metrics';
      } else {
        categoryName = 'Metrics'; // Generic fallback
      }

      Object.entries(testMetrics).forEach(
        ([metricName, metricResult]: [string, any]) => {
          // Skip if already added via behaviors
          const alreadyAdded = allMetrics.some(m => m.name === metricName);
          if (
            !alreadyAdded &&
            metricResult &&
            typeof metricResult === 'object' &&
            'is_successful' in metricResult
          ) {
            allMetrics.push({
              name: metricName,
              description: metricResult.description || undefined,
              passed: metricResult.is_successful,
              fullMetricData: metricResult,
              behaviorName: categoryName,
            });
          }
        }
      );
    }

    return allMetrics;
  }, [test, behaviors, metricsSource, isMultiTurn]);

  // Filter metrics based on selected status
  const filteredMetrics = useMemo(() => {
    if (filterStatus === 'all') return metricsData;
    return metricsData.filter(m =>
      filterStatus === 'passed' ? m.passed : !m.passed
    );
  }, [metricsData, filterStatus]);

  // Calculate summary statistics based on filtered metrics
  const summary: MetricSummary = useMemo(() => {
    const total = filteredMetrics.length;
    const passed = filteredMetrics.filter(m => m.passed).length;
    const failed = total - passed;
    const passRate = total > 0 ? (passed / total) * 100 : 0;

    return { total, passed, failed, passRate };
  }, [filteredMetrics]);

  // Find best and worst performing behaviors based on filtered metrics
  const behaviorStats = useMemo(() => {
    const stats = new Map<string, { passed: number; total: number }>();

    // Group metrics by behavior name (works for both behavior-based and direct metrics)
    const behaviorNames = [
      ...new Set(filteredMetrics.map(m => m.behaviorName)),
    ];

    behaviorNames.forEach(behaviorName => {
      const behaviorMetrics = filteredMetrics.filter(
        m => m.behaviorName === behaviorName
      );
      const passed = behaviorMetrics.filter(m => m.passed).length;
      const total = behaviorMetrics.length;

      if (total > 0) {
        stats.set(behaviorName, { passed, total });
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
  }, [filteredMetrics]);

  // Extract Goal Achievement/Evaluation metric data if it exists
  const goalAchievementData = useMemo(() => {
    const testMetrics = test.test_metrics?.metrics || {};
    // Support flexible matching: any metric containing "goal" + ("achievement" OR "evaluation")
    const goalMetricEntry = Object.entries(testMetrics).find(([metricName]) => {
      const lowerName = metricName.toLowerCase();
      return (
        lowerName.includes('goal') &&
        (lowerName.includes('achievement') || lowerName.includes('evaluation'))
      );
    });
    const goalMetric = goalMetricEntry?.[1] as any;

    if (!goalMetric) return null;

    // Criteria evaluations are in test_output.goal_evaluation, not in the metric itself
    const goalEvaluation = test.test_output?.goal_evaluation as any;

    return {
      criteriaMet: goalMetric.criteria_met || 0,
      criteriaTotal: goalMetric.criteria_total || 0,
      confidence: goalMetric.confidence || 0,
      isSuccessful: goalMetric.is_successful || false,
      criteriaEvaluations: goalEvaluation?.criteria_evaluations || [],
      reason: goalMetric.reason || '',
    };
  }, [test]);

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
      {/* Filter Toggle - Only for Single-turn tests */}
      <Box
        sx={{
          mb: 3,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="h6" fontWeight={600}>
          Metrics Overview
        </Typography>
        {!isMultiTurn && (
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
        )}
      </Box>
      {/* Summary Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid
          size={{
            xs: 12,
            md: behaviorStats.hasMultipleBehaviors ? 4 : 6,
          }}
        >
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
            <Grid
              size={{
                xs: 12,
                md: 4,
              }}
            >
              <Card>
                <CardContent>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    gutterBottom
                  >
                    {metricsSource === MetricsSource.BEHAVIOR || !metricsSource
                      ? 'Best Behavior'
                      : 'Best Performing'}
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

            <Grid
              size={{
                xs: 12,
                md: 4,
              }}
            >
              <Card>
                <CardContent>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    gutterBottom
                  >
                    {metricsSource === MetricsSource.BEHAVIOR || !metricsSource
                      ? 'Worst Behavior'
                      : 'Worst Performing'}
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
          <Grid
            size={{
              xs: 12,
              md: 6,
            }}
          >
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {metricsSource === MetricsSource.BEHAVIOR || !metricsSource
                    ? 'Behavior'
                    : 'Metrics Source'}
                </Typography>
                <Typography variant="h6" fontWeight={600} noWrap>
                  {metricsSource === MetricsSource.BEHAVIOR || !metricsSource
                    ? behaviorStats.best?.name || 'N/A'
                    : getMetricsSourceLabel(metricsSource)}
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
      {/* Goal Achievement Details */}
      {goalAchievementData && (
        <Card sx={{ mb: 3 }} variant="outlined">
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
              <CheckCircleOutlineIcon
                sx={{
                  color: goalAchievementData.isSuccessful
                    ? 'success.main'
                    : 'error.main',
                  fontSize: 20,
                }}
              />
              <Typography variant="subtitle1" fontWeight={600}>
                Goal Achievement
              </Typography>
              <StatusChip
                passed={goalAchievementData.isSuccessful}
                label={goalAchievementData.isSuccessful ? 'Pass' : 'Fail'}
                size="small"
                variant="filled"
              />
            </Box>

            <Grid container spacing={2}>
              {/* Criteria Progress */}
              <Grid
                size={{
                  xs: 12,
                  md: 6,
                }}
              >
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    fontWeight: 600,
                  }}
                >
                  Criteria Progress
                </Typography>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 2,
                    mt: 1.5,
                    mb: 1,
                  }}
                >
                  <Box sx={{ flexGrow: 1 }}>
                    <LinearProgress
                      variant="determinate"
                      value={
                        goalAchievementData.criteriaTotal > 0
                          ? (goalAchievementData.criteriaMet /
                              goalAchievementData.criteriaTotal) *
                            100
                          : 0
                      }
                      sx={{
                        height: 6,
                        borderRadius: theme.shape.borderRadius,
                        backgroundColor: theme.palette.grey[200],
                        '& .MuiLinearProgress-bar': {
                          backgroundColor: goalAchievementData.isSuccessful
                            ? theme.palette.success.main
                            : theme.palette.error.main,
                        },
                      }}
                    />
                  </Box>
                  <Typography variant="body2" fontWeight={600}>
                    {goalAchievementData.criteriaMet}/
                    {goalAchievementData.criteriaTotal}
                  </Typography>
                </Box>
                <Typography variant="caption" color="text.secondary">
                  {goalAchievementData.criteriaTotal > 0
                    ? `${((goalAchievementData.criteriaMet / goalAchievementData.criteriaTotal) * 100).toFixed(0)}% of criteria met`
                    : 'No criteria'}
                </Typography>
              </Grid>

              {/* Confidence */}
              <Grid
                size={{
                  xs: 12,
                  md: 6,
                }}
              >
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    fontWeight: 600,
                  }}
                >
                  Confidence
                </Typography>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 2,
                    mt: 1.5,
                    mb: 1,
                  }}
                >
                  <Box sx={{ flexGrow: 1 }}>
                    <LinearProgress
                      variant="determinate"
                      value={goalAchievementData.confidence * 100}
                      sx={{
                        height: 6,
                        borderRadius: theme.shape.borderRadius,
                        backgroundColor: theme.palette.grey[200],
                        '& .MuiLinearProgress-bar': {
                          backgroundColor:
                            goalAchievementData.confidence === 1
                              ? theme.palette.success.main
                              : goalAchievementData.confidence >= 0.7
                                ? theme.palette.warning.main
                                : theme.palette.error.main,
                        },
                      }}
                    />
                  </Box>
                  <Typography variant="body2" fontWeight={600}>
                    {(goalAchievementData.confidence * 100).toFixed(0)}%
                  </Typography>
                </Box>
                <Typography variant="caption" color="text.secondary">
                  {goalAchievementData.confidence === 1
                    ? 'High confidence'
                    : goalAchievementData.confidence >= 0.7
                      ? 'Medium confidence'
                      : 'Low confidence'}
                </Typography>
              </Grid>

              {/* Criteria Breakdown */}
              {goalAchievementData.criteriaEvaluations &&
                goalAchievementData.criteriaEvaluations.length > 0 && (
                  <Grid size={12}>
                    <Divider sx={{ my: 2 }} />
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                      }}
                      onClick={() => setCriteriaExpanded(!criteriaExpanded)}
                    >
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        fontWeight={600}
                      >
                        Criteria Breakdown (
                        {goalAchievementData.criteriaEvaluations.length})
                      </Typography>
                      <IconButton
                        size="small"
                        sx={{
                          transform: criteriaExpanded
                            ? 'rotate(180deg)'
                            : 'rotate(0deg)',
                          transition: theme.transitions.create('transform', {
                            duration: theme.transitions.duration.shortest,
                          }),
                        }}
                      >
                        <ExpandMoreIcon />
                      </IconButton>
                    </Box>
                    <Collapse
                      in={criteriaExpanded}
                      timeout="auto"
                      unmountOnExit
                    >
                      <List dense disablePadding sx={{ mt: 2 }}>
                        {goalAchievementData.criteriaEvaluations.map(
                          (criterion: any, index: number) => (
                            <ListItem
                              key={index}
                              disablePadding
                              sx={{
                                py: 0.75,
                                display: 'flex',
                                alignItems: 'flex-start',
                              }}
                            >
                              <Box
                                sx={{
                                  width: 6,
                                  height: 6,
                                  borderRadius: theme.shape.circular,
                                  backgroundColor: criterion.met
                                    ? 'success.main'
                                    : 'error.main',
                                  mt: 0.75,
                                  mr: 1.5,
                                  flexShrink: 0,
                                }}
                              />
                              <ListItemText
                                primary={
                                  <Typography
                                    variant="body2"
                                    color="text.primary"
                                  >
                                    {criterion.criterion}
                                  </Typography>
                                }
                                sx={{ m: 0 }}
                              />
                            </ListItem>
                          )
                        )}
                      </List>
                    </Collapse>
                  </Grid>
                )}

              {/* Collapsible Reason */}
              {goalAchievementData.reason && (
                <Grid size={12}>
                  <Divider sx={{ my: 1 }} />
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                    }}
                    onClick={() => setReasonExpanded(!reasonExpanded)}
                  >
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      fontWeight={600}
                    >
                      Detailed Reasoning
                    </Typography>
                    <IconButton
                      size="small"
                      sx={{
                        transform: reasonExpanded
                          ? 'rotate(180deg)'
                          : 'rotate(0deg)',
                        transition: theme.transitions.create('transform', {
                          duration: theme.transitions.duration.shortest,
                        }),
                      }}
                    >
                      <ExpandMoreIcon />
                    </IconButton>
                  </Box>
                  <Collapse in={reasonExpanded} timeout="auto" unmountOnExit>
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        {goalAchievementData.reason}
                      </Typography>
                    </Box>
                  </Collapse>
                </Grid>
              )}
            </Grid>
          </CardContent>
        </Card>
      )}
      {/* Metrics Details Table - Only for Single-turn tests */}
      {!isMultiTurn && (
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell width="15%">Status</TableCell>
                <TableCell width="30%">Metric</TableCell>
                <TableCell width="55%">Reason</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredMetrics.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} align="center">
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
                      <StatusChip
                        passed={metric.passed}
                        label={metric.passed ? 'Pass' : 'Fail'}
                        size="small"
                        variant="filled"
                        sx={{ minWidth: 80 }}
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
      )}
    </Box>
  );
}
