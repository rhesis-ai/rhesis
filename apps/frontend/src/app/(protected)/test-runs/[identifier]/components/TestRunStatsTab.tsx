'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Chip,
  CircularProgress,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TableSortLabel,
  Tooltip,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import RateReviewIcon from '@mui/icons-material/RateReview';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  CategoryPassRates,
  TestResultDetail,
  TestResultsStats,
  TopicPassRates,
} from '@/utils/api-client/interfaces/test-results';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { BehaviorWithMetrics } from '../hooks/useTestRunDetailData';
import TestRunHeader from './TestRunHeader';
import TestRunTags from './TestRunTags';
import {
  BehaviorStat,
  computeReviewSummary,
  getReviewBand,
  metricHasHumanCorrection,
  MetricStat,
} from './test-run-summary-utils';

interface TestRunStatsTabProps {
  testRun: TestRunDetail;
  testRunId: string;
  testResults: TestResultDetail[];
  sessionToken: string;
  loading?: boolean;
  onRefresh?: () => void;
  behaviors?: BehaviorWithMetrics[];
  onViewBehavior?: (behaviorId: string) => void;
  onViewMetric?: (metricName: string) => void;
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
      <Typography
        variant="subtitle1"
        fontWeight={600}
        sx={{ mb: 2, color: theme => theme.palette.greyscale.title }}
      >
        {title}
      </Typography>
      {children}
    </Paper>
  );
}

function BandChip({ passRate }: { passRate: number }) {
  const band = getReviewBand(passRate);
  return (
    <Chip
      label={band.label}
      size="small"
      color={band.colorKey}
      sx={{ fontWeight: 500 }}
    />
  );
}

type BehaviorSortField = 'name' | 'total' | 'passRate';

function BehaviorTable({
  stats,
  behaviors,
  onViewBehavior,
}: {
  stats: BehaviorStat[];
  behaviors?: BehaviorWithMetrics[];
  onViewBehavior?: (behaviorId: string) => void;
}) {
  const [sortField, setSortField] = useState<BehaviorSortField>('passRate');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const handleSort = (field: BehaviorSortField) => {
    if (field === sortField) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const sorted = useMemo(() => {
    return [...stats].sort((a, b) => {
      const mul = sortDir === 'asc' ? 1 : -1;
      if (sortField === 'name') return mul * a.name.localeCompare(b.name);
      if (sortField === 'total') return mul * (a.total - b.total);
      return mul * (a.passRate - b.passRate);
    });
  }, [stats, sortField, sortDir]);

  return (
    <Box sx={{ overflowX: 'auto' }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ whiteSpace: 'nowrap' }}>
              <TableSortLabel
                active={sortField === 'name'}
                direction={sortField === 'name' ? sortDir : 'asc'}
                onClick={() => handleSort('name')}
              >
                Behavior
              </TableSortLabel>
            </TableCell>
            <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
              <TableSortLabel
                active={sortField === 'total'}
                direction={sortField === 'total' ? sortDir : 'asc'}
                onClick={() => handleSort('total')}
              >
                Tests
              </TableSortLabel>
            </TableCell>
            <TableCell align="right">Passed</TableCell>
            <TableCell align="right">Failed</TableCell>
            <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
              <TableSortLabel
                active={sortField === 'passRate'}
                direction={sortField === 'passRate' ? sortDir : 'asc'}
                onClick={() => handleSort('passRate')}
              >
                Pass Rate
              </TableSortLabel>
            </TableCell>
            <TableCell>Status</TableCell>
            {onViewBehavior && <TableCell />}
          </TableRow>
        </TableHead>
        <TableBody>
          {sorted.map(stat => {
            const behavior = behaviors?.find(b => b.name === stat.name);
            const canDrilldown =
              stat.failed > 0 && !!onViewBehavior && !!behavior;
            return (
              <TableRow
                key={stat.name}
                hover={canDrilldown}
                sx={{ cursor: canDrilldown ? 'pointer' : 'default' }}
                onClick={
                  canDrilldown ? () => onViewBehavior!(behavior!.id) : undefined
                }
              >
                <TableCell sx={{ maxWidth: 300 }}>
                  <Tooltip title={stat.name} placement="top" arrow>
                    <Typography
                      variant="body2"
                      noWrap
                      sx={{ maxWidth: 280, display: 'block' }}
                    >
                      {stat.name}
                    </Typography>
                  </Tooltip>
                </TableCell>
                <TableCell align="right">{stat.total}</TableCell>
                <TableCell
                  align="right"
                  sx={{ color: theme => theme.palette.success.main }}
                >
                  {stat.passed}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{
                    color: theme =>
                      stat.failed > 0
                        ? theme.palette.error.main
                        : 'text.secondary',
                    fontWeight: stat.failed > 0 ? 600 : 400,
                  }}
                >
                  {stat.failed}
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600 }}>
                  {stat.passRate.toFixed(1)}%
                </TableCell>
                <TableCell>
                  <BandChip passRate={stat.passRate} />
                </TableCell>
                {onViewBehavior && (
                  <TableCell sx={{ width: 32, p: 0.5 }}>
                    {canDrilldown && (
                      <Tooltip title="View failures in Test Cases">
                        <OpenInNewIcon
                          fontSize="small"
                          sx={{
                            color: 'text.secondary',
                            verticalAlign: 'middle',
                          }}
                        />
                      </Tooltip>
                    )}
                  </TableCell>
                )}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Box>
  );
}

function BehaviorPerformanceSection({
  stats,
  behaviors,
  onViewBehavior,
}: {
  stats: BehaviorStat[];
  behaviors?: BehaviorWithMetrics[];
  onViewBehavior?: (behaviorId: string) => void;
}) {
  return (
    <SectionCard title="Behavior Performance">
      <BehaviorTable
        stats={stats}
        behaviors={behaviors}
        onViewBehavior={onViewBehavior}
      />
    </SectionCard>
  );
}

type MetricSortField = 'name' | 'total' | 'failRate';

function MetricTable({
  stats,
  testResults,
  onViewMetric,
}: {
  stats: MetricStat[];
  testResults: TestResultDetail[];
  onViewMetric?: (metricName: string) => void;
}) {
  const [sortField, setSortField] = useState<MetricSortField>('failRate');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const handleSort = (field: MetricSortField) => {
    if (field === sortField) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir(field === 'failRate' ? 'desc' : 'asc');
    }
  };

  const sorted = useMemo(() => {
    return [...stats].sort((a, b) => {
      const mul = sortDir === 'asc' ? 1 : -1;
      if (sortField === 'name') return mul * a.name.localeCompare(b.name);
      if (sortField === 'total') return mul * (a.total - b.total);
      return mul * (a.failRate - b.failRate);
    });
  }, [stats, sortField, sortDir]);

  return (
    <Box sx={{ overflowX: 'auto' }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ whiteSpace: 'nowrap' }}>
              <TableSortLabel
                active={sortField === 'name'}
                direction={sortField === 'name' ? sortDir : 'asc'}
                onClick={() => handleSort('name')}
              >
                Metric
              </TableSortLabel>
            </TableCell>
            <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
              <TableSortLabel
                active={sortField === 'total'}
                direction={sortField === 'total' ? sortDir : 'asc'}
                onClick={() => handleSort('total')}
              >
                Total
              </TableSortLabel>
            </TableCell>
            <TableCell align="right">Passed</TableCell>
            <TableCell align="right">Failed</TableCell>
            <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
              <TableSortLabel
                active={sortField === 'failRate'}
                direction={sortField === 'failRate' ? sortDir : 'desc'}
                onClick={() => handleSort('failRate')}
              >
                Fail Rate
              </TableSortLabel>
            </TableCell>
            <TableCell>Status</TableCell>
            {onViewMetric && <TableCell />}
          </TableRow>
        </TableHead>
        <TableBody>
          {sorted.map(stat => {
            const passRate = 100 - stat.failRate;
            const canDrilldown = stat.failed > 0 && !!onViewMetric;
            return (
              <TableRow
                key={stat.name}
                hover={canDrilldown}
                sx={{ cursor: canDrilldown ? 'pointer' : 'default' }}
                onClick={
                  canDrilldown ? () => onViewMetric!(stat.name) : undefined
                }
              >
                <TableCell sx={{ maxWidth: 360 }}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      minWidth: 0,
                    }}
                  >
                    <Tooltip title={stat.name} placement="top" arrow>
                      <Typography
                        variant="body2"
                        noWrap
                        sx={{ maxWidth: 200, display: 'block' }}
                      >
                        {stat.name}
                      </Typography>
                    </Tooltip>
                    {metricHasHumanCorrection(stat.name, testResults) && (
                      <Tooltip
                        title={`Automated: ${stat.automatedPassed ?? 0} passed, ${stat.automatedFailed ?? 0} failed. After human review: ${stat.passed} passed, ${stat.failed} failed.`}
                        placement="top"
                        arrow
                      >
                        <Chip
                          size="small"
                          variant="outlined"
                          color="info"
                          icon={
                            <RateReviewIcon sx={{ '&&': { fontSize: 16 } }} />
                          }
                          label="corrected"
                          sx={{ flexShrink: 0 }}
                        />
                      </Tooltip>
                    )}
                  </Box>
                </TableCell>
                <TableCell align="right">{stat.total}</TableCell>
                <TableCell
                  align="right"
                  sx={{ color: theme => theme.palette.success.main }}
                >
                  {stat.passed}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{
                    color: theme =>
                      stat.failed > 0
                        ? theme.palette.error.main
                        : 'text.secondary',
                    fontWeight: stat.failed > 0 ? 600 : 400,
                  }}
                >
                  {stat.failed}
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600 }}>
                  {stat.failRate.toFixed(1)}%
                </TableCell>
                <TableCell>
                  <BandChip passRate={passRate} />
                </TableCell>
                {onViewMetric && (
                  <TableCell sx={{ width: 32, p: 0.5 }}>
                    {canDrilldown && (
                      <Tooltip title="View failures in Test Cases">
                        <OpenInNewIcon
                          fontSize="small"
                          sx={{
                            color: 'text.secondary',
                            verticalAlign: 'middle',
                          }}
                        />
                      </Tooltip>
                    )}
                  </TableCell>
                )}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Box>
  );
}

function MetricPerformanceSection({
  stats,
  testResults,
  onViewMetric,
}: {
  stats: MetricStat[];
  testResults: TestResultDetail[];
  onViewMetric?: (metricName: string) => void;
}) {
  return (
    <SectionCard title="Metric Performance">
      <MetricTable
        stats={stats}
        testResults={testResults}
        onViewMetric={onViewMetric}
      />
    </SectionCard>
  );
}

interface DimensionItem {
  name: string;
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
}

function DimensionList({ items }: { items: DimensionItem[] }) {
  return (
    <Stack spacing={0.5}>
      {items.map(item => (
        <Box
          key={item.name}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            py: 0.75,
            borderBottom: 1,
            borderColor: 'divider',
            '&:last-child': { borderBottom: 0 },
          }}
        >
          <Typography
            variant="body2"
            sx={{
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={item.name}
          >
            {item.name}
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ whiteSpace: 'nowrap', minWidth: 48, textAlign: 'right' }}
          >
            {item.total} tests
          </Typography>
          <Typography
            variant="body2"
            fontWeight={600}
            sx={{ whiteSpace: 'nowrap', minWidth: 52, textAlign: 'right' }}
          >
            {item.pass_rate.toFixed(1)}%
          </Typography>
          <Box sx={{ minWidth: 108 }}>
            <BandChip passRate={item.pass_rate} />
          </Box>
        </Box>
      ))}
    </Stack>
  );
}

function MoreBreakdownsSection({
  categoryPassRates,
  topicPassRates,
  isLoading,
}: {
  categoryPassRates?: CategoryPassRates;
  topicPassRates?: TopicPassRates;
  isLoading: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  const categoryStats = useMemo((): DimensionItem[] => {
    if (!categoryPassRates) return [];
    return Object.entries(categoryPassRates)
      .map(([name, s]) => ({ name, ...s }))
      .sort((a, b) => a.pass_rate - b.pass_rate);
  }, [categoryPassRates]);

  const topicStats = useMemo((): DimensionItem[] => {
    if (!topicPassRates) return [];
    return Object.entries(topicPassRates)
      .map(([name, s]) => ({ name, ...s }))
      .sort((a, b) => a.pass_rate - b.pass_rate);
  }, [topicPassRates]);

  const hasData = categoryStats.length > 0 || topicStats.length > 0;

  if (!isLoading && !hasData) return null;

  return (
    <Accordion
      expanded={expanded}
      onChange={(_, exp) => setExpanded(exp)}
      variant="outlined"
      sx={{
        borderRadius: '8px !important',
        '&:before': { display: 'none' },
      }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="subtitle1" fontWeight={600}>
          More Breakdowns
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0 }}>
        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={24} />
          </Box>
        ) : (
          <Grid container spacing={4}>
            {categoryStats.length > 0 && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography
                  variant="subtitle2"
                  fontWeight={600}
                  sx={{ mb: 1.5 }}
                >
                  Categories
                </Typography>
                <DimensionList items={categoryStats} />
              </Grid>
            )}
            {topicStats.length > 0 && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography
                  variant="subtitle2"
                  fontWeight={600}
                  sx={{ mb: 1.5 }}
                >
                  Topics
                </Typography>
                <DimensionList items={topicStats} />
              </Grid>
            )}
          </Grid>
        )}
      </AccordionDetails>
    </Accordion>
  );
}

export default function TestRunStatsTab({
  testRun,
  testRunId,
  testResults,
  sessionToken,
  loading = false,
  onRefresh,
  behaviors,
  onViewBehavior,
  onViewMetric,
}: TestRunStatsTabProps) {
  const isMounted = useRef(false);
  const [stats, setStats] = useState<TestResultsStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  useEffect(() => {
    isMounted.current = true;

    const fetchStats = async () => {
      if (!sessionToken) return setStatsLoading(false);
      try {
        setStatsLoading(true);
        const client = new ApiClientFactory(
          sessionToken
        ).getTestResultsClient();
        const result = await client.getComprehensiveTestResultsStats({
          test_run_ids: [testRunId],
          mode: 'all',
        });
        if (isMounted.current) {
          setStats(result);
          setStatsLoading(false);
        }
      } catch {
        if (isMounted.current) {
          setStatsLoading(false);
        }
      }
    };

    void fetchStats();
    return () => {
      isMounted.current = false;
    };
  }, [testRunId, sessionToken]);

  const behaviorStats = useMemo((): BehaviorStat[] => {
    if (!stats?.behavior_pass_rates) return [];
    return Object.entries(stats.behavior_pass_rates).map(([name, s]) => ({
      name,
      total: s.total,
      passed: s.passed,
      failed: s.failed,
      passRate: s.pass_rate,
    }));
  }, [stats]);

  const metricStats = useMemo((): MetricStat[] => {
    if (!stats?.metric_pass_rates) return [];
    return Object.entries(stats.metric_pass_rates).map(([name, s]) => ({
      name,
      total: s.total,
      passed: s.passed,
      failed: s.failed,
      failRate: s.total > 0 ? ((s.total - s.passed) / s.total) * 100 : 0,
      automatedPassed: s.automated_passed,
      automatedFailed: s.automated_failed,
      humanReviewCount: s.human_review_count,
    }));
  }, [stats]);

  const reviewSummary = useMemo(
    () => computeReviewSummary(testResults),
    [testResults]
  );

  const hasInsights = behaviorStats.length > 0 || metricStats.length > 0;

  return (
    <Box>
      <TestRunHeader
        testRun={testRun}
        testResults={testResults}
        overallStats={stats?.overall_pass_rates}
        reviewSummary={reviewSummary}
        loading={statsLoading}
        onRefresh={onRefresh}
      />

      <Stack spacing={3} sx={{ mt: 3 }}>
        {statsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        ) : !hasInsights ? (
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
            <Typography color="text.secondary">
              No test result data available to summarize.
            </Typography>
          </Paper>
        ) : (
          <>
            {behaviorStats.length > 0 && (
              <BehaviorPerformanceSection
                stats={behaviorStats}
                behaviors={behaviors}
                onViewBehavior={onViewBehavior}
              />
            )}
            {metricStats.length > 0 && (
              <MetricPerformanceSection
                stats={metricStats}
                testResults={testResults}
                onViewMetric={onViewMetric}
              />
            )}
            <MoreBreakdownsSection
              categoryPassRates={stats?.category_pass_rates}
              topicPassRates={stats?.topic_pass_rates}
              isLoading={statsLoading}
            />
          </>
        )}
      </Stack>

      <TestRunTags sessionToken={sessionToken} testRun={testRun} />
    </Box>
  );
}
