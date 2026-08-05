'use client';

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
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
import { useSession } from 'next-auth/react';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import type {
  InsightsQueryResponse,
  InsightsRow,
} from '@/utils/api-client/interfaces/insights';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { BehaviorWithMetrics } from '../hooks/useTestRunDetailData';
import TestRunHeader from './TestRunHeader';
import TestRunTags from './TestRunTags';
import {
  BehaviorStat,
  buildBehaviorCorrectionTooltip,
  computeReviewSummary,
  countBehaviorHumanCorrections,
  getResultReviews,
  getReviewBand,
  metricHasHumanReview,
  metricShowsHumanCorrection,
  MetricStat,
} from './test-run-summary-utils';
import { rowToPassFailStats } from '@/app/(protected)/insights/utils/behavior-insights-utils';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface TestRunStatsTabProps {
  testRun: TestRunDetail;
  testRunId: string;
  testResults: TestResultDetail[];
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

function CorrectedChip({
  title,
  label = 'corrected',
}: {
  title: string;
  label?: 'corrected' | 'reviewed';
}) {
  return (
    <Tooltip title={title} placement="top" arrow>
      <Chip
        size="small"
        variant="outlined"
        icon={<RateReviewIcon sx={{ '&&': { fontSize: 16 } }} />}
        label={label}
        sx={{
          flexShrink: 0,
          borderColor: theme => theme.palette.primary.dark,
          color: theme => theme.palette.primary.dark,
          '& .MuiChip-icon': {
            color: theme => theme.palette.primary.dark,
          },
        }}
      />
    </Tooltip>
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
                    {stat.hasHumanCorrection && (
                      <CorrectedChip
                        title={
                          stat.humanCorrectionTooltip ??
                          `${stat.humanCorrectionCount ?? 1} corrected by human review`
                        }
                      />
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
                    {stat.hasHumanCorrection && (
                      <CorrectedChip
                        title={`Automated: ${stat.automatedPassed ?? 0} passed, ${stat.automatedFailed ?? 0} failed. After human review: ${stat.passed} passed, ${stat.failed} failed.`}
                      />
                    )}
                    {!stat.hasHumanCorrection && stat.hasMetricReview && (
                      <CorrectedChip
                        label="reviewed"
                        title="This metric has a human review that confirmed the automated result."
                      />
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
  onViewMetric,
}: {
  stats: MetricStat[];
  onViewMetric?: (metricName: string) => void;
}) {
  return (
    <SectionCard title="Metric Performance">
      <MetricTable stats={stats} onViewMetric={onViewMetric} />
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
  categories,
  topics,
  isLoading,
}: {
  categories: DimensionItem[];
  topics: DimensionItem[];
  isLoading: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  const hasData = categories.length > 0 || topics.length > 0;

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
            {categories.length > 0 && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography
                  variant="subtitle2"
                  fontWeight={600}
                  sx={{ mb: 1.5 }}
                >
                  Categories
                </Typography>
                <DimensionList items={categories} />
              </Grid>
            )}
            {topics.length > 0 && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography
                  variant="subtitle2"
                  fontWeight={600}
                  sx={{ mb: 1.5 }}
                >
                  Topics
                </Typography>
                <DimensionList items={topics} />
              </Grid>
            )}
          </Grid>
        )}
      </AccordionDetails>
    </Accordion>
  );
}

function namedDimensionItems(
  rows: InsightsRow[],
  nameKey: string
): DimensionItem[] {
  return rows
    .flatMap(row => {
      const name = row[nameKey];
      if (typeof name !== 'string' || !name) return [];
      return [{ name, ...rowToPassFailStats(row) }];
    })
    .sort((a, b) => a.pass_rate - b.pass_rate);
}

export default function TestRunStatsTab({
  testRun,
  testRunId,
  testResults,
  loading = false,
  onRefresh,
  behaviors,
  onViewBehavior,
  onViewMetric,
}: TestRunStatsTabProps) {
  const { status } = useSession();
  const isMounted = useRef(false);
  const [insights, setInsights] = useState<InsightsQueryResponse | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const reviewRevision = useMemo(
    () =>
      testResults.reduce(
        (count, result) => count + getResultReviews(result).length,
        0
      ),
    [testResults]
  );

  const fetchStats = useCallback(async () => {
    if (!isAuthenticated(status)) {
      setStatsLoading(false);
      return;
    }
    try {
      setStatsLoading(true);
      const client = new ApiClientFactory().getInsightsClient();
      const filters = { test_run_ids: [testRunId] };
      const measures = ['passed', 'failed', 'pass_rate'];
      const results = await client.getInsightsQuery({
        summary: {
          entity: 'test_result',
          group_by: [],
          measures,
          filters,
        },
        behaviors: {
          entity: 'test_result',
          group_by: ['behavior'],
          measures,
          filters,
        },
        categories: {
          entity: 'test_result',
          group_by: ['category'],
          measures,
          filters,
        },
        topics: {
          entity: 'test_result',
          group_by: ['topic'],
          measures,
          filters,
        },
        metrics: {
          entity: 'metric',
          group_by: ['metric_name'],
          measures: [
            ...measures,
            'automated_passed',
            'automated_failed',
            'human_review_count',
          ],
          filters,
        },
      });
      if (isMounted.current) {
        setInsights(results);
        setStatsLoading(false);
      }
    } catch {
      if (isMounted.current) {
        setStatsLoading(false);
      }
    }
  }, [testRunId, status]);

  useEffect(() => {
    isMounted.current = true;
    void fetchStats();
    return () => {
      isMounted.current = false;
    };
  }, [fetchStats]);

  const lastReviewRevision = useRef(reviewRevision);
  useEffect(() => {
    if (lastReviewRevision.current === reviewRevision) return;
    lastReviewRevision.current = reviewRevision;
    void fetchStats();
  }, [fetchStats, reviewRevision]);

  const isDataLoading = statsLoading || loading;

  const overallStats = useMemo(() => {
    const row = insights?.summary?.rows[0];
    return row ? rowToPassFailStats(row) : undefined;
  }, [insights]);

  const categoryItems = useMemo(
    () => namedDimensionItems(insights?.categories?.rows ?? [], 'category'),
    [insights]
  );

  const topicItems = useMemo(
    () => namedDimensionItems(insights?.topics?.rows ?? [], 'topic'),
    [insights]
  );

  const behaviorStats = useMemo((): BehaviorStat[] => {
    if (!insights?.behaviors || loading) return [];
    return (insights.behaviors.rows ?? []).flatMap(row => {
      const name = row.behavior;
      if (typeof name !== 'string' || !name) return [];
      const s = rowToPassFailStats(row);
      const humanCorrectionCount = countBehaviorHumanCorrections(
        name,
        testResults
      );
      return [
        {
          name,
          total: s.total,
          passed: s.passed,
          failed: s.failed,
          passRate: s.pass_rate,
          hasHumanCorrection: humanCorrectionCount > 0,
          humanCorrectionCount,
          humanCorrectionTooltip: buildBehaviorCorrectionTooltip(
            name,
            testResults
          ),
        },
      ];
    });
  }, [insights, testResults, loading]);

  const metricStats = useMemo((): MetricStat[] => {
    if (!insights?.metrics || loading) return [];
    return (insights.metrics.rows ?? []).flatMap(row => {
      const name = row.metric_name;
      if (typeof name !== 'string' || !name) return [];
      const s = rowToPassFailStats(row);
      const humanReviewCount = Number(row.human_review_count ?? 0);
      return [
        {
          name,
          total: s.total,
          passed: s.passed,
          failed: s.failed,
          failRate: s.total > 0 ? ((s.total - s.passed) / s.total) * 100 : 0,
          automatedPassed: Number(row.automated_passed ?? 0),
          automatedFailed: Number(row.automated_failed ?? 0),
          humanReviewCount,
          hasHumanCorrection: metricShowsHumanCorrection(
            name,
            testResults,
            humanReviewCount
          ),
          hasMetricReview: metricHasHumanReview(name, testResults),
        },
      ];
    });
  }, [insights, testResults, loading]);

  const reviewSummary = useMemo(
    () => (loading ? undefined : computeReviewSummary(testResults)),
    [testResults, loading]
  );

  const hasInsights = behaviorStats.length > 0 || metricStats.length > 0;

  return (
    <Box>
      <TestRunHeader
        testRun={testRun}
        testResults={testResults}
        overallStats={overallStats}
        reviewSummary={reviewSummary}
        loading={isDataLoading}
        onRefresh={onRefresh}
      />

      <Stack spacing={3} sx={{ mt: 3 }}>
        {isDataLoading ? (
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
              categories={categoryItems}
              topics={topicItems}
              isLoading={false}
            />
          </>
        )}
      </Stack>

      <TestRunTags testRun={testRun} />
    </Box>
  );
}
