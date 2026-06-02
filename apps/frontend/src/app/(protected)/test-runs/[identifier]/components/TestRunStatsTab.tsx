'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Box, CircularProgress, Grid, Paper, Typography } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { BasePieChart } from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestRunStatsAll } from '@/utils/api-client/interfaces/test-run-stats';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import TestRunHeader from './TestRunHeader';
import TestRunTags from './TestRunTags';

interface TestRunStatsTabProps {
  testRun: TestRunDetail;
  testRunId: string;
  testResults: TestResultDetail[];
  sessionToken: string;
  loading?: boolean;
  onRefresh?: () => void;
}

function ChartCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        height: '100%',
        minHeight: 280,
        borderRadius: 2,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Typography
        variant="subtitle1"
        fontWeight={600}
        sx={{ mb: 2, color: theme => theme.palette.greyscale.title }}
      >
        {title}
      </Typography>
      <Box sx={{ flex: 1, minHeight: 200 }}>{children}</Box>
    </Paper>
  );
}

export default function TestRunStatsTab({
  testRun,
  testRunId,
  testResults,
  sessionToken,
  loading = false,
  onRefresh,
}: TestRunStatsTabProps) {
  const isMounted = useRef(false);
  const [stats, setStats] = useState<TestRunStatsAll | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    isMounted.current = true;

    const fetchStats = async () => {
      if (!sessionToken) return;
      try {
        setIsLoading(true);
        setHasError(false);
        const client = new ApiClientFactory(sessionToken).getTestRunsClient();
        const data = (await client.getTestRunStats({
          mode: 'all',
          test_run_ids: [testRunId],
          top: 10,
          months: 6,
        })) as TestRunStatsAll;
        if (isMounted.current) {
          setStats(data);
          setIsLoading(false);
        }
      } catch {
        if (isMounted.current) {
          setHasError(true);
          setIsLoading(false);
        }
      }
    };

    void fetchStats();
    return () => {
      isMounted.current = false;
    };
  }, [sessionToken, testRunId]);

  const resultData = stats?.result_distribution
    ? [
        {
          name: 'Passed',
          value: stats.result_distribution.passed,
          fullName: 'Passed',
        },
        {
          name: 'Failed',
          value: stats.result_distribution.failed,
          fullName: 'Failed',
        },
        {
          name: 'Pending',
          value: stats.result_distribution.pending,
          fullName: 'Pending',
        },
      ].filter(item => item.value > 0)
    : [];

  const statusData =
    stats?.status_distribution?.map(item => ({
      name: item.status,
      value: item.count,
      fullName: item.status,
    })) ?? [];

  const behaviorData = React.useMemo(() => {
    const counts = new Map<string, number>();
    testResults.forEach(result => {
      const behaviorName =
        result.test?.behavior?.name ||
        (result.test as { behavior?: { name?: string } })?.behavior?.name;
      if (!behaviorName) return;
      counts.set(behaviorName, (counts.get(behaviorName) ?? 0) + 1);
    });
    return Array.from(counts.entries()).map(([name, value]) => ({
      name,
      value,
      fullName: name,
    }));
  }, [testResults]);

  const metricData = React.useMemo(() => {
    const counts = new Map<string, { pass: number; fail: number }>();
    testResults.forEach(result => {
      const metrics = result.test_metrics?.metrics ?? {};
      Object.entries(metrics).forEach(([name, m]) => {
        const entry = counts.get(name) ?? { pass: 0, fail: 0 };
        if (m.is_successful) entry.pass += 1;
        else entry.fail += 1;
        counts.set(name, entry);
      });
    });
    return Array.from(counts.entries()).map(([name, { pass, fail }]) => ({
      name,
      value: pass + fail,
      fullName: `${name} (${pass} pass / ${fail} fail)`,
    }));
  }, [testResults]);

  return (
    <Box>
      <TestRunHeader
        testRun={testRun}
        testResults={testResults}
        loading={loading}
        onRefresh={onRefresh}
      />

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress />
        </Box>
      ) : hasError ? (
        <Paper sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
          <InfoOutlinedIcon color="info" />
          <Typography color="text.secondary">
            Could not load run statistics. Summary cards above still reflect
            current results.
          </Typography>
        </Paper>
      ) : (
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <ChartCard title="Pass / Fail">
              <BasePieChart
                title=""
                data={
                  resultData.length > 0
                    ? resultData
                    : [{ name: 'No data', value: 1, fullName: 'No data' }]
                }
                useThemeColors
                colorPalette="pie"
              />
            </ChartCard>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <ChartCard title="Status breakdown">
              <BasePieChart
                title=""
                data={
                  statusData.length > 0
                    ? statusData
                    : [{ name: 'No data', value: 1, fullName: 'No data' }]
                }
                useThemeColors
                colorPalette="pie"
              />
            </ChartCard>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <ChartCard title="By behavior">
              <BasePieChart
                title=""
                data={
                  behaviorData.length > 0
                    ? behaviorData
                    : [{ name: 'No data', value: 1, fullName: 'No data' }]
                }
                useThemeColors
                colorPalette="pie"
              />
            </ChartCard>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <ChartCard title="By metric">
              <BasePieChart
                title=""
                data={
                  metricData.length > 0
                    ? metricData
                    : [{ name: 'No data', value: 1, fullName: 'No data' }]
                }
                useThemeColors
                colorPalette="pie"
              />
            </ChartCard>
          </Grid>
          {stats?.overall_summary && (
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <ChartCard title="Overall pass rate">
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    height: '100%',
                    px: 2,
                  }}
                >
                  <Typography variant="h3" fontWeight={700}>
                    {stats.overall_summary.pass_rate.toFixed(1)}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {stats.overall_summary.total_runs} run(s) in scope
                  </Typography>
                </Box>
              </ChartCard>
            </Grid>
          )}
          {stats?.timeline && stats.timeline.length > 0 && (
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <ChartCard title="Timeline">
                <Box sx={{ px: 1 }}>
                  {stats.timeline.slice(0, 5).map(point => (
                    <Box
                      key={point.date}
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        py: 0.75,
                        borderBottom: 1,
                        borderColor: 'divider',
                      }}
                    >
                      <Typography variant="body2">{point.date}</Typography>
                      <Typography variant="body2" fontWeight={600}>
                        {point.total_runs} runs
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </ChartCard>
            </Grid>
          )}
        </Grid>
      )}

      <TestRunTags sessionToken={sessionToken} testRun={testRun} />
    </Box>
  );
}
