'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { BasePieChart, BaseChartsGrid } from '@/components/common/BaseCharts';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Box, CircularProgress, Typography, Alert, Card, CardContent, useTheme } from '@mui/material';
import { useChartColors } from '@/components/common/BaseCharts';
import { pieChartUtils } from '@/components/common/BasePieChart';
import { TestResultsStats, TestRunSummaryItem } from '@/utils/api-client/interfaces/test-results';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import styles from '@/styles/BaseLineChart.module.css';

// Fallback mock data in case the API fails
const fallbackData = [
  { name: 'Loading...', value: 100 },
];

// Dynamic configuration for charts
const DEFAULT_TOP = 5;
const DEFAULT_MONTHS = 6;

// Interface for chart data items with better type safety
interface ChartDataItem {
  name: string;
  value: number;
  fullName?: string;
  percentage?: string;
}

interface TestRunDetailChartsProps {
  testRunId: string;
  sessionToken: string;
}

export default function TestRunDetailCharts({ testRunId, sessionToken }: TestRunDetailChartsProps) {
  const [testRunStats, setTestRunStats] = useState<TestResultsStats | null>(null);
  const [testRunDetail, setTestRunDetail] = useState<TestRunDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Get theme-based colors
  const theme = useTheme();
  const { palettes } = useChartColors();

  // Transform test runs data similar to LatestTestRunsChart
  const transformTestRunsData = useCallback((testRunSummary?: TestRunSummaryItem[]) => {
    if (!Array.isArray(testRunSummary) || testRunSummary.length === 0) {
      return [];
    }
    
    // Create a copy of the array to avoid mutating the original
    const runs = [...testRunSummary];
    
    // Sort by started_at (most recent first), take latest 5, then reverse to show chronologically
    const sortedRuns = runs
      .sort((a, b) => {
        const dateA = a.started_at ? new Date(a.started_at).getTime() : 0;
        const dateB = b.started_at ? new Date(b.started_at).getTime() : 0;
        return dateB - dateA; // Most recent first
      })
      .slice(0, 5) // Take only the 5 most recent
      .reverse(); // Reverse to show chronologically (oldest to newest for chart)

    return sortedRuns.map((item, index) => {
      // Use the name field from the test run data
      const runName = item.name || `Run ${item.id.slice(0, 8)}`;
      
      // Format the date for display - try both started_at and created_at
      const formatDate = (item: any) => {
        const dateString = item.started_at || item.created_at;
        
        if (!dateString) return 'Unknown date';
        
        try {
          const date = new Date(dateString);
          if (isNaN(date.getTime())) return 'Invalid date';
          
          return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
          });
        } catch (error) {
          console.error('Date formatting error:', error);
          return 'Date error';
        }
      };

      return {
        name: runName,
        pass_rate: item.overall?.pass_rate != null ? Math.round(item.overall.pass_rate * 10) / 10 : 0,
        total: item.overall?.total || 0,
        passed: item.overall?.passed || 0,
        failed: item.overall?.failed || 0,
        test_run_id: item.id,
        isHighlighted: testRunDetail ? item.id === testRunDetail.id : false,
        started_at: item.started_at,
        created_at: item.created_at,
        formatted_date: formatDate(item)
      };
    });
  }, [testRunDetail]);

  // Generate category data for pie chart
  const generateCategoryData = useCallback((): ChartDataItem[] => {
    if (!testRunStats?.category_pass_rates) {
      return fallbackData;
    }

    const categoryBreakdown: Record<string, number> = {};
    let total = 0;

    Object.entries(testRunStats.category_pass_rates).forEach(([category, stats]) => {
      categoryBreakdown[category] = stats.total;
      total += stats.total;
    });

    return pieChartUtils.generateDimensionData(
      categoryBreakdown,
      total,
      DEFAULT_TOP,
      fallbackData
    );
  }, [testRunStats]);

  // Generate topic data for pie chart
  const generateTopicData = useCallback((): ChartDataItem[] => {
    if (!testRunStats?.topic_pass_rates) {
      return fallbackData;
    }

    const topicBreakdown: Record<string, number> = {};
    let total = 0;

    Object.entries(testRunStats.topic_pass_rates).forEach(([topic, stats]) => {
      topicBreakdown[topic] = stats.total;
      total += stats.total;
    });

    return pieChartUtils.generateDimensionData(
      topicBreakdown,
      total,
      DEFAULT_TOP,
      fallbackData
    );
  }, [testRunStats]);

  // Generate pass/fail data for current test run using overall stats
  const generatePassFailData = useCallback((): ChartDataItem[] => {
    if (!testRunStats?.overall_pass_rates) {
      return fallbackData;
    }

    const overall = testRunStats.overall_pass_rates;
    const passedTests = overall.passed || 0;
    const failedTests = overall.failed || 0;
    const total = overall.total || 0;

    if (total === 0) {
      return [{ name: 'No Tests', value: 1, fullName: 'No Tests', percentage: '100%' }];
    }

    const passedPercentage = ((passedTests / total) * 100).toFixed(1);
    const failedPercentage = ((failedTests / total) * 100).toFixed(1);

    return [
      {
        name: 'Pass',
        value: passedTests,
        fullName: 'Passed Tests',
        percentage: `${passedPercentage}%`
      },
      {
        name: 'Fail',
        value: failedTests,
        fullName: 'Failed Tests',
        percentage: `${failedPercentage}%`
      }
    ].filter(item => item.value > 0); // Only show non-zero values
  }, [testRunStats]);

  useEffect(() => {
    const fetchTestRunData = async () => {
      if (!testRunId) return;

      try {
        setIsLoading(true);
        const clientFactory = new ApiClientFactory(sessionToken);
        const testRunsClient = clientFactory.getTestRunsClient();
        const testResultsClient = clientFactory.getTestResultsClient();

        // First, get the test run details to access the test set
        const runDetail = await testRunsClient.getTestRun(testRunId);
        setTestRunDetail(runDetail);

        if (!runDetail.test_configuration?.test_set?.id) {
          throw new Error('Test run does not have an associated test set');
        }

        const testSetId = runDetail.test_configuration.test_set.id;

        // Get comprehensive stats for the test set to show pass rates across different runs
        const testSetStats = await testResultsClient.getComprehensiveTestResultsStats({
          test_set_ids: [testSetId],
          mode: 'test_runs', // Get test run comparison data
          months: DEFAULT_MONTHS
        });

        // Get specific test run stats for pass/fail data
        const currentRunOverallStats = await testResultsClient.getComprehensiveTestResultsStats({
          test_run_id: testRunId,
          mode: 'overall', // Get overall pass/fail stats for this run
          months: DEFAULT_MONTHS
        });

        // Get category breakdown for current test run
        const currentRunCategoryStats = await testResultsClient.getComprehensiveTestResultsStats({
          test_run_id: testRunId,
          mode: 'category', // Get category breakdown for this run
          months: DEFAULT_MONTHS
        });

        // Get topic breakdown for current test run
        const currentRunTopicStats = await testResultsClient.getComprehensiveTestResultsStats({
          test_run_id: testRunId,
          mode: 'topic', // Get topic breakdown for this run
          months: DEFAULT_MONTHS
        });

        // Combine both stats - use test set stats for runs comparison, current run stats for pass/fail
        const combinedStats = {
          ...testSetStats,
          overall_pass_rates: currentRunOverallStats.overall_pass_rates,
          category_pass_rates: currentRunCategoryStats.category_pass_rates,
          topic_pass_rates: currentRunTopicStats.topic_pass_rates
        };

        setTestRunStats(combinedStats);
        setError(null);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load test run statistics';
        setError(errorMessage);
        console.error('Error fetching test run stats:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTestRunData();
  }, [testRunId, sessionToken]);

  // Calculate chart data
  const testRunsData = useMemo(() => {
    const data = transformTestRunsData(testRunStats?.test_run_summary);
    return data.map(item => ({
      ...item,
      pass_rate: isNaN(item.pass_rate) ? 0 : Math.max(0, Math.min(100, item.pass_rate)), // Ensure 0-100 range
      total: isNaN(item.total) ? 0 : Math.max(0, item.total),
      passed: isNaN(item.passed) ? 0 : Math.max(0, item.passed),
      failed: isNaN(item.failed) ? 0 : Math.max(0, item.failed)
    }));
  }, [testRunStats?.test_run_summary, transformTestRunsData]);
  
  const categoryData = useMemo(() => generateCategoryData(), [generateCategoryData]);
  const topicData = useMemo(() => generateTopicData(), [generateTopicData]);
  const passFailData = useMemo(() => generatePassFailData(), [generatePassFailData]);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error">
          {error}
        </Alert>
      </Box>
    );
  }

  return (
    <BaseChartsGrid>
      {/* Pass Rates Scatter Plot */}
      <Card className={styles.card}>
        <CardContent className={styles.cardContent}>
          <Typography variant="subtitle1" className={styles.title}>
            Last 5 Runs for Test Set
          </Typography>
          <Box className={styles.chartContainer}>
            {testRunsData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={testRunsData}
                  margin={{ top: 5, right: 5, bottom: 25, left: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="name"
                    type="category"
                    tick={false}
                    axisLine={{ strokeWidth: 1 }}
                    tickLine={false}
                    interval={0}
                    padding={{ left: 20, right: 20 }}
                  />
                  <YAxis
                    domain={[0, 100]}
                    tickCount={6}
                    tick={{ fontSize: parseInt(theme.typography.chartTick.fontSize) }}
                    axisLine={{ strokeWidth: 1 }}
                    tickLine={{ strokeWidth: 1 }}
                    tickFormatter={(value: number) => `${value}%`}
                    width={35}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      fontSize: theme.typography.chartTick.fontSize, 
                      backgroundColor: theme.palette.background.paper, 
                      border: `1px solid ${theme.palette.divider}`, 
                      borderRadius: '4px',
                      color: theme.palette.text.primary
                    }}
                    content={({ active, payload, label }) => {
                      if (active && payload && payload.length > 0) {
                        const data = payload[0].payload;
                        return (
                          <div style={{ 
                            padding: '8px', 
                            backgroundColor: theme.palette.background.paper, 
                            border: `1px solid ${theme.palette.divider}`, 
                            borderRadius: '4px',
                            fontSize: theme.typography.chartTick.fontSize,
                            color: theme.palette.text.primary
                          }}>
                            <div style={{ fontWeight: 'bold', marginBottom: '4px', color: theme.palette.text.primary }}>{data.name}</div>
                            <div style={{ marginBottom: '2px', color: theme.palette.text.secondary }}>{data.formatted_date}</div>
                            <div style={{ marginBottom: '2px', color: theme.palette.text.primary }}>Pass Rate: {data.pass_rate}%</div>
                            <div style={{ color: theme.palette.text.primary }}>Tests: {data.passed}/{data.total} passed</div>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Legend 
                  payload={testRunsData.length > 0 ? testRunsData.map((run, index) => ({
                    value: run.name,
                    type: 'circle',
                    color: palettes.line[index % palettes.line.length]
                  })) : []}
                  wrapperStyle={{ fontSize: theme.typography.chartTick.fontSize, marginTop: '0px', paddingTop: '0px' }}
                  iconSize={8}
                  height={20}
                  layout="horizontal"
                  align="center"
                  verticalAlign="bottom"
                />
                  <Line
                    type="monotone"
                    dataKey="pass_rate"
                    name="Pass Rate"
                    stroke="transparent"
                    strokeWidth={0}
                    dot={(props: any) => {
                      const { cx, cy, payload, index } = props;
                      const color = palettes.line[index % palettes.line.length];
                      return (
                        <circle
                          key={`dot-${payload?.test_run_id || index}`}
                          cx={cx}
                          cy={cy}
                          r={3}
                          fill={color}
                          stroke={color}
                          strokeWidth={1}
                          opacity={0.8}
                        />
                      );
                    }}
                    activeDot={(props: any) => {
                      const { cx, cy, index } = props;
                      const color = palettes.line[index % palettes.line.length];
                      return (
                        <circle
                          cx={cx}
                          cy={cy}
                          r={5}
                          fill={color}
                          stroke={color}
                          strokeWidth={2}
                          opacity={1}
                        />
                      );
                    }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                <Typography variant="body2" color="text.secondary">
                  No test runs data available for this test set
                </Typography>
              </Box>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Pass Rate for Test Run */}
      <BasePieChart
        title="Pass Rate for Test Run"
        data={passFailData}
        useThemeColors={true}
        colorPalette="pie"
        height={180}
        showPercentage={true}
        tooltipProps={{
          contentStyle: { 
            fontSize: theme.typography.chartTick.fontSize,
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: '4px',
            color: theme.palette.text.primary
          },
          formatter: (value: number, name: string, props: any) => {
            const item = props.payload;
            return [`${value} tests (${item.percentage})`, item.fullName || name];
          }
        }}
      />

      {/* Tests by Category */}
      <BasePieChart
        title="Tests by Category"
        data={categoryData}
        useThemeColors={true}
        colorPalette="pie"
        height={180}
        showPercentage={true}
        tooltipProps={{
          contentStyle: { 
            fontSize: theme.typography.chartTick.fontSize,
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: '4px',
            color: theme.palette.text.primary
          },
          formatter: (value: number, name: string, props: any) => {
            const item = props.payload;
            return [`${value} (${item.percentage})`, item.fullName || name];
          }
        }}
      />

      {/* Tests by Topic */}
      <BasePieChart
        title="Tests by Topic"
        data={topicData}
        useThemeColors={true}
        colorPalette="pie"
        height={180}
        showPercentage={true}
        tooltipProps={{
          contentStyle: { 
            fontSize: theme.typography.chartTick.fontSize,
            backgroundColor: theme.palette.background.paper,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: '4px',
            color: theme.palette.text.primary
          },
          formatter: (value: number, name: string, props: any) => {
            const item = props.payload;
            return [`${value} (${item.percentage})`, item.fullName || name];
          }
        }}
      />
    </BaseChartsGrid>
  );
} 