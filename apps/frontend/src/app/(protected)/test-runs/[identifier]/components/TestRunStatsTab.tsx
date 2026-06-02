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
  useTheme,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TestResultDetail,
  TestResultsStats,
} from '@/utils/api-client/interfaces/test-results';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { BehaviorWithMetrics } from '../hooks/useTestRunDetailData';
import TestRunHeader from './TestRunHeader';
import TestRunTags from './TestRunTags';
import {
  aggregateBehaviorStats,
  aggregateMetricStats,
  BehaviorStat,
  getReviewBand,
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
  const theme = useTheme();

  const chartData = useMemo(
    () => [...stats].sort((a, b) => a.passRate - b.passRate),
    [stats]
  );

  const chartHeight = Math.max(200, chartData.length * 52 + 40);

  const getBandColor = (passRate: number) =>
    theme.palette[getReviewBand(passRate).colorKey].main;

  return (
    <SectionCard title="Behavior Performance">
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          layout="vertical"
          data={chartData}
          margin={{ top: 4, right: 48, bottom: 8, left: 4 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            horizontal={false}
            stroke={theme.palette.divider}
          />
          <XAxis
            type="number"
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{
              fontSize: 12,
              fill: theme.palette.text.secondary as string,
            }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={160}
            tick={{
              fontSize: 12,
              fill: theme.palette.text.secondary as string,
            }}
            tickFormatter={(name: string) =>
              name.length > 22 ? `${name.slice(0, 19)}\u2026` : name
            }
          />
          <RechartsTooltip
            cursor={{ fill: theme.palette.action.hover }}
            formatter={(value: number) => [`${value.toFixed(1)}%`, 'Pass Rate']}
            labelStyle={{ fontWeight: 600 }}
          />
          <Bar dataKey="passRate" radius={[0, 4, 4, 0]} maxBarSize={30}>
            {chartData.map(entry => (
              <Cell key={entry.name} fill={getBandColor(entry.passRate)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <Box sx={{ mt: 3 }}>
        <BehaviorTable
          stats={stats}
          behaviors={behaviors}
          onViewBehavior={onViewBehavior}
        />
      </Box>
    </SectionCard>
  );
}

type MetricSortField = 'name' | 'total' | 'failRate';

function MetricTable({
  stats,
  onViewMetric,
}: {
  stats: MetricStat[];
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
  onViewMetric,
}: {
  stats: MetricStat[];
  onViewMetric?: (metricName: string) => void;
}) {
  const theme = useTheme();

  const chartData = useMemo(
    () => [...stats].sort((a, b) => b.failRate - a.failRate),
    [stats]
  );

  const chartHeight = Math.max(200, chartData.length * 52 + 40);

  const getBandColor = (failRate: number) =>
    theme.palette[getReviewBand(100 - failRate).colorKey].main;

  return (
    <SectionCard title="Metric Performance">
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          layout="vertical"
          data={chartData}
          margin={{ top: 4, right: 48, bottom: 8, left: 4 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            horizontal={false}
            stroke={theme.palette.divider}
          />
          <XAxis
            type="number"
            domain={[0, 100]}
            tickFormatter={(v: number) => `${v}%`}
            tick={{
              fontSize: 12,
              fill: theme.palette.text.secondary as string,
            }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={160}
            tick={{
              fontSize: 12,
              fill: theme.palette.text.secondary as string,
            }}
            tickFormatter={(name: string) =>
              name.length > 22 ? `${name.slice(0, 19)}\u2026` : name
            }
          />
          <RechartsTooltip
            cursor={{ fill: theme.palette.action.hover }}
            formatter={(value: number) => [`${value.toFixed(1)}%`, 'Fail Rate']}
            labelStyle={{ fontWeight: 600 }}
          />
          <Bar dataKey="failRate" radius={[0, 4, 4, 0]} maxBarSize={30}>
            {chartData.map(entry => (
              <Cell key={entry.name} fill={getBandColor(entry.failRate)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <Box sx={{ mt: 3 }}>
        <MetricTable stats={stats} onViewMetric={onViewMetric} />
      </Box>
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
  testRunId,
  sessionToken,
}: {
  testRunId: string;
  sessionToken: string;
}) {
  const isMounted = useRef(false);
  const [data, setData] = useState<TestResultsStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    isMounted.current = true;

    const fetchData = async () => {
      if (!sessionToken) return;
      try {
        setIsLoading(true);
        const client = new ApiClientFactory(
          sessionToken
        ).getTestResultsClient();
        const result = await client.getComprehensiveTestResultsStats({
          test_run_ids: [testRunId],
          mode: 'all',
        });
        if (isMounted.current) {
          setData(result);
          setIsLoading(false);
        }
      } catch {
        if (isMounted.current) {
          setIsLoading(false);
        }
      }
    };

    void fetchData();
    return () => {
      isMounted.current = false;
    };
  }, [testRunId, sessionToken]);

  const categoryStats = useMemo((): DimensionItem[] => {
    if (!data?.category_pass_rates) return [];
    return Object.entries(data.category_pass_rates)
      .map(([name, s]) => ({ name, ...s }))
      .sort((a, b) => a.pass_rate - b.pass_rate);
  }, [data]);

  const topicStats = useMemo((): DimensionItem[] => {
    if (!data?.topic_pass_rates) return [];
    return Object.entries(data.topic_pass_rates)
      .map(([name, s]) => ({ name, ...s }))
      .sort((a, b) => a.pass_rate - b.pass_rate);
  }, [data]);

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
  const behaviorStats = useMemo(
    () => aggregateBehaviorStats(testResults),
    [testResults]
  );

  const metricStats = useMemo(
    () => aggregateMetricStats(testResults),
    [testResults]
  );

  const hasInsights = behaviorStats.length > 0 || metricStats.length > 0;

  return (
    <Box>
      <TestRunHeader
        testRun={testRun}
        testResults={testResults}
        loading={loading}
        onRefresh={onRefresh}
      />

      <Stack spacing={3} sx={{ mt: 3 }}>
        {loading && testResults.length === 0 ? (
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
                onViewMetric={onViewMetric}
              />
            )}
            <MoreBreakdownsSection
              testRunId={testRunId}
              sessionToken={sessionToken}
            />
          </>
        )}
      </Stack>

      <TestRunTags sessionToken={sessionToken} testRun={testRun} />
    </Box>
  );
}
