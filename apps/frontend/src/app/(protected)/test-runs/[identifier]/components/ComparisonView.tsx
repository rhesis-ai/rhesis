'use client';

import React, { useState, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  AlertTitle,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  LinearProgress,
  Chip,
  Grid,
  Paper,
  useTheme,
  TextField,
  InputAdornment,
  ButtonGroup,
  alpha,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SearchIcon from '@mui/icons-material/Search';
import RemoveIcon from '@mui/icons-material/Remove';
import ListIcon from '@mui/icons-material/List';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

interface ComparisonViewProps {
  currentTestRun: {
    id: string;
    name?: string;
    created_at: string;
  };
  currentTestResults: TestResultDetail[];
  availableTestRuns: Array<{
    id: string;
    name?: string;
    created_at: string;
    pass_rate?: number;
  }>;
  onClose: () => void;
  onLoadBaseline: (testRunId: string) => Promise<TestResultDetail[]>;
  prompts: Record<string, { content: string; name?: string }>;
  behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
}

interface ComparisonTest {
  id: string;
  baseline?: TestResultDetail;
  current: TestResultDetail;
}

export default function ComparisonView({
  currentTestRun,
  currentTestResults,
  availableTestRuns,
  onClose,
  onLoadBaseline,
  prompts,
  behaviors,
}: ComparisonViewProps) {
  const theme = useTheme();
  const [selectedBaselineId, setSelectedBaselineId] = useState<string>(
    availableTestRuns[0]?.id || ''
  );
  const [baselineTestResults, setBaselineTestResults] = useState<
    TestResultDetail[] | null
  >(null);
  const [loading, setLoading] = useState(false);
  const [selectedTestId, setSelectedTestId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'improved' | 'regressed' | 'unchanged'
  >('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Load baseline data when selection changes
  React.useEffect(() => {
    if (selectedBaselineId) {
      setLoading(true);
      onLoadBaseline(selectedBaselineId)
        .then(setBaselineTestResults)
        .catch(error => {
          console.error('Error loading baseline:', error);
          setBaselineTestResults([]);
        })
        .finally(() => setLoading(false));
    }
  }, [selectedBaselineId, onLoadBaseline]);

  const baselineRun = availableTestRuns.find(r => r.id === selectedBaselineId);

  // Helper to check if test passed
  const isTestPassed = (test: TestResultDetail) => {
    const metrics = test.test_metrics?.metrics || {};
    const metricValues = Object.values(metrics);
    const totalMetrics = metricValues.length;
    const passedMetrics = metricValues.filter(m => m.is_successful).length;
    return totalMetrics > 0 && passedMetrics === totalMetrics;
  };

  // Calculate baseline pass rate from test results
  const baselinePassRate = useMemo(() => {
    if (!baselineTestResults || baselineTestResults.length === 0)
      return undefined;
    const passed = baselineTestResults.filter(isTestPassed).length;
    return (passed / baselineTestResults.length) * 100;
  }, [baselineTestResults]);

  // Helper to get pass rate
  const getPassRate = (test: TestResultDetail) => {
    const metrics = test.test_metrics?.metrics || {};
    const metricValues = Object.values(metrics);
    const totalMetrics = metricValues.length;
    if (totalMetrics === 0) return 0;
    const passedMetrics = metricValues.filter(m => m.is_successful).length;
    return (passedMetrics / totalMetrics) * 100;
  };

  // Create all comparison data (unfiltered for statistics)
  const allComparisonTests: ComparisonTest[] = useMemo(() => {
    if (!baselineTestResults) return [];

    // Match tests by prompt_id or by order
    return currentTestResults.map((current, index) => {
      const baseline =
        baselineTestResults.find(b => b.prompt_id === current.prompt_id) ||
        baselineTestResults[index];

      return {
        id: current.id,
        baseline,
        current,
      };
    });
  }, [currentTestResults, baselineTestResults]);

  // Create filtered comparison data for display
  const comparisonTests: ComparisonTest[] = useMemo(() => {
    // Apply filters
    return allComparisonTests.filter(test => {
      // Status filter
      if (statusFilter !== 'all') {
        const baselinePassed = test.baseline
          ? isTestPassed(test.baseline)
          : null;
        const currentPassed = isTestPassed(test.current);
        const isImproved =
          baselinePassed !== null && currentPassed && !baselinePassed;
        const isRegressed =
          baselinePassed !== null && !currentPassed && baselinePassed;
        const isUnchanged = !isImproved && !isRegressed;

        if (statusFilter === 'improved' && !isImproved) return false;
        if (statusFilter === 'regressed' && !isRegressed) return false;
        if (statusFilter === 'unchanged' && !isUnchanged) return false;
      }

      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const promptContent =
          test.current.prompt_id && prompts[test.current.prompt_id]
            ? prompts[test.current.prompt_id].content.toLowerCase()
            : '';
        const responseContent =
          test.current.test_output?.output?.toLowerCase() || '';
        return promptContent.includes(query) || responseContent.includes(query);
      }

      return true;
    });
  }, [allComparisonTests, statusFilter, searchQuery, prompts]);

  // Calculate statistics (from all tests, not filtered)
  const stats = useMemo(() => {
    if (!baselineTestResults)
      return { improved: 0, regressed: 0, unchanged: 0 };

    let improved = 0;
    let regressed = 0;
    let unchanged = 0;

    allComparisonTests.forEach(test => {
      if (!test.baseline) return;

      const baselinePassed = isTestPassed(test.baseline);
      const currentPassed = isTestPassed(test.current);

      if (currentPassed && !baselinePassed) improved++;
      else if (!currentPassed && baselinePassed) regressed++;
      else unchanged++;
    });

    return { improved, regressed, unchanged };
  }, [allComparisonTests, baselineTestResults]);

  const selectedTest = allComparisonTests.find(t => t.id === selectedTestId);

  // Calculate current run pass rate
  const currentPassRate = useMemo(() => {
    const passed = currentTestResults.filter(isTestPassed).length;
    return Math.round((passed / currentTestResults.length) * 100);
  }, [currentTestResults]);

  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return 'N/A';
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const getPromptSnippet = (
    test: TestResultDetail,
    maxLength: number = 80
  ): string => {
    const promptId = test.prompt_id;
    if (!promptId || !prompts[promptId]) {
      return `Test #${test.id.slice(0, 8)}`;
    }

    const promptContent = prompts[promptId].content;
    if (promptContent.length <= maxLength) {
      return promptContent;
    }

    return promptContent.slice(0, maxLength).trim() + '...';
  };

  if (loading && !baselineTestResults) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography>Loading comparison data...</Typography>
        <LinearProgress sx={{ mt: 2 }} />
      </Box>
    );
  }

  return (
    <Box sx={{ pb: 4 }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 4,
        }}
      >
        <Typography variant="h4">Run Comparison</Typography>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </Box>

      {/* Comparison Headers */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {/* Baseline Run */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography
                variant="overline"
                color="text.secondary"
                display="block"
                sx={{ mb: 1 }}
              >
                Baseline Run
              </Typography>
              <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                <InputLabel>Select baseline run</InputLabel>
                <Select
                  value={selectedBaselineId}
                  onChange={e => setSelectedBaselineId(e.target.value)}
                  label="Select baseline run"
                >
                  {availableTestRuns.map(run => (
                    <MenuItem key={run.id} value={run.id}>
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          width: '100%',
                        }}
                      >
                        <span>{run.name || `Run #${run.id.slice(0, 8)}`}</span>
                        <Typography variant="caption" color="text.secondary">
                          {formatDate(run.created_at)}
                        </Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              {baselineRun && (
                <>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    display="block"
                  >
                    {formatDate(baselineRun.created_at)}
                  </Typography>
                  {baselinePassRate !== undefined && (
                    <Box
                      sx={{
                        mt: 1,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                      }}
                    >
                      <Typography variant="caption" color="text.secondary">
                        Pass rate:
                      </Typography>
                      <Chip
                        label={`${Math.round(baselinePassRate)}%`}
                        size="small"
                      />
                    </Box>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Current Run */}
        <Grid item xs={12} md={6}>
          <Card
            sx={{
              bgcolor: theme.palette.background.light2,
              border: `2px solid ${theme.palette.primary.main}`,
              height: '100%',
            }}
          >
            <CardContent sx={{ p: 3 }}>
              <Typography
                variant="overline"
                color="text.secondary"
                display="block"
                sx={{ mb: 1 }}
              >
                Current Run
              </Typography>
              <Typography variant="subtitle2" gutterBottom>
                {currentTestRun.name || `Run #${currentTestRun.id.slice(0, 8)}`}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                display="block"
                sx={{ mb: 2 }}
              >
                {formatDate(currentTestRun.created_at)}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Pass rate:
                </Typography>
                <Typography variant="body2" fontWeight={600}>
                  {currentPassRate}%
                </Typography>
                {baselinePassRate !== undefined && (
                  <Typography
                    variant="caption"
                    sx={{
                      color:
                        currentPassRate > baselinePassRate
                          ? theme.palette.success.main
                          : currentPassRate < baselinePassRate
                            ? theme.palette.error.main
                            : theme.palette.text.secondary,
                      fontWeight: 500,
                    }}
                  >
                    ({currentPassRate > baselinePassRate ? '+' : ''}
                    {(currentPassRate - baselinePassRate).toFixed(1)}%)
                  </Typography>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filter Bar */}
      {baselineTestResults && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            gap: 2,
            mb: 3,
            alignItems: { xs: 'stretch', sm: 'center' },
          }}
        >
          {/* Search */}
          <TextField
            size="small"
            placeholder="Search tests..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ minWidth: { xs: '100%', sm: 250 } }}
          />

          {/* Status Filter Buttons */}
          <ButtonGroup size="small" variant="outlined">
            <Button
              onClick={() => setStatusFilter('all')}
              variant={statusFilter === 'all' ? 'contained' : 'outlined'}
              startIcon={<ListIcon fontSize="small" />}
            >
              All
            </Button>
            <Button
              onClick={() => setStatusFilter('improved')}
              variant={statusFilter === 'improved' ? 'contained' : 'outlined'}
              startIcon={<TrendingUpIcon fontSize="small" />}
              sx={{
                ...(statusFilter === 'improved' && {
                  bgcolor: theme.palette.success.main,
                  color: 'white',
                  '&:hover': {
                    bgcolor: theme.palette.success.dark,
                  },
                }),
              }}
            >
              Improved
            </Button>
            <Button
              onClick={() => setStatusFilter('regressed')}
              variant={statusFilter === 'regressed' ? 'contained' : 'outlined'}
              startIcon={<TrendingDownIcon fontSize="small" />}
              sx={{
                ...(statusFilter === 'regressed' && {
                  bgcolor: theme.palette.error.main,
                  color: 'white',
                  '&:hover': {
                    bgcolor: theme.palette.error.dark,
                  },
                }),
              }}
            >
              Regressed
            </Button>
            <Button
              onClick={() => setStatusFilter('unchanged')}
              variant={statusFilter === 'unchanged' ? 'contained' : 'outlined'}
              startIcon={<RemoveIcon fontSize="small" />}
            >
              Unchanged
            </Button>
          </ButtonGroup>

          {/* Results count */}
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ display: 'flex', alignItems: 'center' }}
          >
            {comparisonTests.length} test
            {comparisonTests.length !== 1 ? 's' : ''}
          </Typography>
        </Box>
      )}

      {/* Statistics */}
      {baselineTestResults && (
        <Paper
          variant="outlined"
          sx={{
            p: 2.5,
            mb: 4,
            display: 'flex',
            gap: 4,
            flexWrap: 'wrap',
            alignItems: 'center',
            bgcolor: theme.palette.background.default,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <TrendingUpIcon
              fontSize="small"
              sx={{ color: theme.palette.success.main }}
            />
            <Box>
              <Typography variant="h6" component="span" sx={{ mr: 0.5 }}>
                {stats.improved}
              </Typography>
              <Typography
                variant="body2"
                component="span"
                color="text.secondary"
              >
                improved
              </Typography>
            </Box>
          </Box>

          {stats.regressed > 0 && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <TrendingDownIcon
                fontSize="small"
                sx={{ color: theme.palette.error.main }}
              />
              <Box>
                <Typography variant="h6" component="span" sx={{ mr: 0.5 }}>
                  {stats.regressed}
                </Typography>
                <Typography
                  variant="body2"
                  component="span"
                  color="text.secondary"
                >
                  regressed
                </Typography>
              </Box>
            </Box>
          )}

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box
              sx={{
                width: 20,
                height: 20,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Box
                sx={{
                  width: 16,
                  height: 2,
                  bgcolor: theme.palette.text.secondary,
                  borderRadius: theme.shape.borderRadius / 4,
                }}
              />
            </Box>
            <Box>
              <Typography variant="h6" component="span" sx={{ mr: 0.5 }}>
                {stats.unchanged}
              </Typography>
              <Typography
                variant="body2"
                component="span"
                color="text.secondary"
              >
                unchanged
              </Typography>
            </Box>
          </Box>
        </Paper>
      )}

      {/* Test-by-Test Comparison */}
      {baselineTestResults && (
        <Card>
          <CardContent sx={{ p: 3 }}>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 3,
              }}
            >
              <Typography variant="h6">Test-by-Test Comparison</Typography>
              <Typography variant="caption" color="text.secondary">
                Click any test to view details
              </Typography>
            </Box>
            <Box
              sx={{
                maxHeight: '70vh',
                overflow: 'auto',
              }}
            >
              {comparisonTests.map((test, index) => {
                const baselinePassed = test.baseline
                  ? isTestPassed(test.baseline)
                  : null;
                const currentPassed = isTestPassed(test.current);
                const isImproved =
                  baselinePassed !== null && currentPassed && !baselinePassed;
                const isRegressed =
                  baselinePassed !== null && !currentPassed && baselinePassed;

                const baselineMetrics =
                  test.baseline?.test_metrics?.metrics || {};
                const currentMetrics = test.current.test_metrics?.metrics || {};
                const baselinePassedCount = Object.values(
                  baselineMetrics
                ).filter(m => m.is_successful).length;
                const baselineTotalCount =
                  Object.values(baselineMetrics).length;
                const currentPassedCount = Object.values(currentMetrics).filter(
                  m => m.is_successful
                ).length;
                const currentTotalCount = Object.values(currentMetrics).length;

                return (
                  <Paper
                    key={test.id}
                    variant="outlined"
                    sx={{
                      mb: 2,
                      cursor: 'pointer',
                      transition: 'all 0.2s ease-in-out',
                      '&:hover': {
                        boxShadow: theme.shadows[2],
                        borderColor: theme.palette.primary.main,
                        bgcolor: theme.palette.background.light1,
                      },
                    }}
                    onClick={() => setSelectedTestId(test.id)}
                  >
                    <Grid container spacing={0}>
                      {/* Baseline */}
                      <Grid
                        item
                        xs={12}
                        md={6}
                        sx={{
                          p: 3,
                          borderRight: { md: 1 },
                          borderColor: 'divider',
                          bgcolor: isImproved
                            ? `${theme.palette.background.default}`
                            : isRegressed
                              ? `${theme.palette.background.default}`
                              : 'transparent',
                        }}
                      >
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 1,
                          }}
                        >
                          {baselinePassed !== null && (
                            <>
                              {baselinePassed ? (
                                <CheckCircleIcon
                                  fontSize="small"
                                  sx={{ color: theme.palette.success.main }}
                                />
                              ) : (
                                <CancelIcon
                                  fontSize="small"
                                  sx={{ color: theme.palette.error.main }}
                                />
                              )}
                            </>
                          )}
                          <Box sx={{ flex: 1 }}>
                            <Typography variant="subtitle2" gutterBottom>
                              {getPromptSnippet(test.current)}
                            </Typography>
                            <Typography variant="caption" display="block">
                              {baselinePassed !== null
                                ? baselinePassed
                                  ? 'Passed'
                                  : 'Failed'
                                : 'No data'}{' '}
                              {baselinePassed !== null &&
                                `(${baselinePassedCount}/${baselineTotalCount})`}
                            </Typography>
                            {test.baseline && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                Score: {getPassRate(test.baseline).toFixed(0)}%
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      </Grid>

                      {/* Current */}
                      <Grid
                        item
                        xs={12}
                        md={6}
                        sx={{
                          p: 3,
                          bgcolor: isImproved
                            ? theme.palette.mode === 'light'
                              ? alpha(theme.palette.success.main, 0.08)
                              : theme.palette.background.light3
                            : isRegressed
                              ? theme.palette.mode === 'light'
                                ? alpha(theme.palette.error.main, 0.08)
                                : theme.palette.background.light3
                              : 'transparent',
                        }}
                      >
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 1,
                          }}
                        >
                          {currentPassed ? (
                            <CheckCircleIcon
                              fontSize="small"
                              sx={{ color: theme.palette.success.main }}
                            />
                          ) : (
                            <CancelIcon
                              fontSize="small"
                              sx={{ color: theme.palette.error.main }}
                            />
                          )}
                          <Box sx={{ flex: 1 }}>
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                mb: 0.5,
                              }}
                            >
                              <Typography variant="subtitle2">
                                {getPromptSnippet(test.current)}
                              </Typography>
                              {isImproved && (
                                <TrendingUpIcon
                                  fontSize="small"
                                  sx={{ color: theme.palette.success.main }}
                                />
                              )}
                              {isRegressed && (
                                <TrendingDownIcon
                                  fontSize="small"
                                  sx={{ color: theme.palette.error.main }}
                                />
                              )}
                            </Box>
                            <Typography variant="caption" display="block">
                              {currentPassed ? 'Passed' : 'Failed'} (
                              {currentPassedCount}/{currentTotalCount})
                            </Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                            >
                              Score: {getPassRate(test.current).toFixed(0)}%
                            </Typography>
                          </Box>
                        </Box>
                      </Grid>
                    </Grid>
                  </Paper>
                );
              })}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Detailed Comparison Dialog */}
      <Dialog
        open={selectedTestId !== null}
        onClose={() => setSelectedTestId(null)}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: {
            height: '90vh',
          },
        }}
      >
        <DialogTitle>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <Typography variant="h6">
              Test #
              {comparisonTests.findIndex(t => t.id === selectedTestId) + 1} -
              Detailed Comparison
            </Typography>
            <IconButton onClick={() => setSelectedTestId(null)} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {selectedTest && (
            <Grid container spacing={3} sx={{ height: '100%' }}>
              {/* Baseline Column */}
              <Grid
                item
                xs={12}
                md={6}
                sx={{
                  p: 3,
                  borderRight: { md: 1 },
                  borderColor: 'divider',
                }}
              >
                <Box sx={{ mb: 4 }}>
                  <Typography
                    variant="overline"
                    color="text.secondary"
                    display="block"
                    gutterBottom
                  >
                    Baseline Run
                  </Typography>
                  {selectedTest.baseline ? (
                    <>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        display="block"
                      >
                        {baselineRun && formatDate(baselineRun.created_at)}
                      </Typography>
                      <Chip
                        label={
                          isTestPassed(selectedTest.baseline)
                            ? `Passed (${
                                Object.values(
                                  selectedTest.baseline.test_metrics?.metrics ||
                                    {}
                                ).filter(m => m.is_successful).length
                              }/${
                                Object.values(
                                  selectedTest.baseline.test_metrics?.metrics ||
                                    {}
                                ).length
                              })`
                            : `Failed (${
                                Object.values(
                                  selectedTest.baseline.test_metrics?.metrics ||
                                    {}
                                ).filter(m => m.is_successful).length
                              }/${
                                Object.values(
                                  selectedTest.baseline.test_metrics?.metrics ||
                                    {}
                                ).length
                              })`
                        }
                        color={
                          isTestPassed(selectedTest.baseline)
                            ? 'success'
                            : 'error'
                        }
                        size="small"
                        sx={{ mt: 1 }}
                      />
                    </>
                  ) : (
                    <Alert severity="info" sx={{ mt: 1 }}>
                      <Typography variant="caption">
                        No baseline data for this test
                      </Typography>
                    </Alert>
                  )}
                </Box>

                {selectedTest.baseline ? (
                  <Box
                    sx={{
                      maxHeight: 'calc(90vh - 200px)',
                      overflow: 'auto',
                      pr: 2,
                    }}
                  >
                    {/* Prompt */}
                    <Box sx={{ mb: 3 }}>
                      <Typography
                        variant="overline"
                        color="text.secondary"
                        display="block"
                        gutterBottom
                      >
                        Prompt
                      </Typography>
                      <Paper
                        variant="outlined"
                        sx={{
                          p: 2.5,
                          bgcolor: theme.palette.background.light1,
                        }}
                      >
                        <Typography variant="body2">
                          {selectedTest.baseline.prompt_id &&
                          prompts[selectedTest.baseline.prompt_id]
                            ? prompts[selectedTest.baseline.prompt_id].content
                            : 'No prompt available'}
                        </Typography>
                      </Paper>
                    </Box>

                    {/* Response */}
                    <Box sx={{ mb: 3 }}>
                      <Typography
                        variant="overline"
                        color="text.secondary"
                        display="block"
                        gutterBottom
                      >
                        Response
                      </Typography>
                      <Paper
                        variant="outlined"
                        sx={{
                          p: 2.5,
                          bgcolor: theme.palette.background.light1,
                        }}
                      >
                        <Typography variant="body2">
                          {selectedTest.baseline.test_output?.output ||
                            'No response available'}
                        </Typography>
                      </Paper>
                    </Box>

                    {/* Metrics */}
                    <Typography variant="h6" sx={{ mb: 3 }}>
                      Metrics Breakdown
                    </Typography>
                    {behaviors.map(behavior => {
                      const behaviorMetrics = behavior.metrics
                        .map(metric => ({
                          ...metric,
                          baselineResult:
                            selectedTest.baseline?.test_metrics?.metrics?.[
                              metric.name
                            ],
                          currentResult:
                            selectedTest.current?.test_metrics?.metrics?.[
                              metric.name
                            ],
                        }))
                        .filter(m => m.baselineResult || m.currentResult);

                      if (behaviorMetrics.length === 0) return null;

                      const baselinePassedCount = behaviorMetrics.filter(
                        m => m.baselineResult?.is_successful
                      ).length;
                      const currentPassedCount = behaviorMetrics.filter(
                        m => m.currentResult?.is_successful
                      ).length;
                      const hasChanges =
                        baselinePassedCount !== currentPassedCount;

                      return (
                        <Accordion
                          key={behavior.id}
                          sx={{
                            mb: 2,
                            '&:before': { display: 'none' },
                            boxShadow: 'none',
                            border: 1,
                            borderColor: 'divider',
                          }}
                          defaultExpanded={hasChanges}
                        >
                          <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            sx={{ py: 2 }}
                          >
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                width: '100%',
                              }}
                            >
                              <Typography variant="body2">
                                {behavior.name}
                              </Typography>
                              <Chip
                                label={`${baselinePassedCount}/${behaviorMetrics.length}`}
                                size="small"
                                color={
                                  baselinePassedCount === behaviorMetrics.length
                                    ? 'success'
                                    : 'error'
                                }
                              />
                            </Box>
                          </AccordionSummary>
                          <AccordionDetails sx={{ p: 3 }}>
                            <Box
                              sx={{
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 3,
                              }}
                            >
                              {behaviorMetrics.map(metric => {
                                const scoreDiff =
                                  metric.currentResult?.score != null &&
                                  metric.baselineResult?.score != null
                                    ? Number(metric.currentResult.score) -
                                      Number(metric.baselineResult.score)
                                    : null;
                                const hasScoreChange =
                                  scoreDiff !== null &&
                                  Math.abs(scoreDiff) > 0.01;

                                return (
                                  <Paper
                                    key={metric.name}
                                    variant="outlined"
                                    sx={{ p: 3 }}
                                  >
                                    <Box
                                      sx={{
                                        display: 'flex',
                                        alignItems: 'flex-start',
                                        gap: 1,
                                      }}
                                    >
                                      {metric.baselineResult?.is_successful ? (
                                        <CheckCircleIcon
                                          fontSize="small"
                                          sx={{
                                            color: theme.palette.success.main,
                                          }}
                                        />
                                      ) : (
                                        <CancelIcon
                                          fontSize="small"
                                          sx={{
                                            color: theme.palette.error.main,
                                          }}
                                        />
                                      )}
                                      <Box sx={{ flex: 1 }}>
                                        <Typography
                                          variant="subtitle2"
                                          gutterBottom
                                        >
                                          {metric.name}
                                        </Typography>
                                        {metric.baselineResult?.score !=
                                          null && (
                                          <Box sx={{ mb: 1 }}>
                                            <Box
                                              sx={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                mb: 0.5,
                                              }}
                                            >
                                              <Typography variant="caption">
                                                Score:{' '}
                                                {Number(
                                                  metric.baselineResult.score
                                                ).toFixed(2)}
                                                {hasScoreChange && (
                                                  <Typography
                                                    component="span"
                                                    variant="caption"
                                                    sx={{
                                                      ml: 0.5,
                                                      color:
                                                        scoreDiff! > 0
                                                          ? theme.palette
                                                              .success.main
                                                          : theme.palette.error
                                                              .main,
                                                      fontWeight: 500,
                                                    }}
                                                  >
                                                    ({scoreDiff! > 0 ? '+' : ''}
                                                    {scoreDiff!.toFixed(2)})
                                                  </Typography>
                                                )}
                                              </Typography>
                                              {metric.baselineResult
                                                .threshold != null && (
                                                <Typography
                                                  variant="caption"
                                                  color="text.secondary"
                                                >
                                                  Threshold: ≥
                                                  {Number(
                                                    metric.baselineResult
                                                      .threshold
                                                  ).toFixed(2)}
                                                </Typography>
                                              )}
                                            </Box>
                                            <LinearProgress
                                              variant="determinate"
                                              value={
                                                Number(
                                                  metric.baselineResult.score
                                                ) * 100
                                              }
                                              color={
                                                metric.baselineResult
                                                  .is_successful
                                                  ? 'success'
                                                  : 'error'
                                              }
                                              sx={{
                                                height: 8,
                                                borderRadius:
                                                  theme.shape.borderRadius / 4,
                                                bgcolor:
                                                  theme.palette.background
                                                    .light2,
                                              }}
                                            />
                                          </Box>
                                        )}
                                        {metric.baselineResult?.reason && (
                                          <Typography
                                            variant="caption"
                                            color="text.secondary"
                                          >
                                            {metric.baselineResult.reason}
                                          </Typography>
                                        )}
                                      </Box>
                                    </Box>
                                  </Paper>
                                );
                              })}
                            </Box>
                          </AccordionDetails>
                        </Accordion>
                      );
                    })}
                  </Box>
                ) : (
                  <Box sx={{ p: 2 }}>
                    <Alert severity="info">
                      No baseline data available for comparison
                    </Alert>
                  </Box>
                )}
              </Grid>

              {/* Current Column */}
              <Grid item xs={12} md={6} sx={{ p: 3 }}>
                <Box sx={{ mb: 4 }}>
                  <Typography
                    variant="overline"
                    color="text.secondary"
                    display="block"
                    gutterBottom
                  >
                    Current Run
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    display="block"
                  >
                    {formatDate(currentTestRun.created_at)}
                  </Typography>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      mt: 1,
                    }}
                  >
                    <Chip
                      label={
                        isTestPassed(selectedTest.current)
                          ? `Passed (${
                              Object.values(
                                selectedTest.current.test_metrics?.metrics || {}
                              ).filter(m => m.is_successful).length
                            }/${
                              Object.values(
                                selectedTest.current.test_metrics?.metrics || {}
                              ).length
                            })`
                          : `Failed (${
                              Object.values(
                                selectedTest.current.test_metrics?.metrics || {}
                              ).filter(m => m.is_successful).length
                            }/${
                              Object.values(
                                selectedTest.current.test_metrics?.metrics || {}
                              ).length
                            })`
                      }
                      color={
                        isTestPassed(selectedTest.current) ? 'success' : 'error'
                      }
                      size="small"
                    />
                    {selectedTest.baseline && (
                      <>
                        {isTestPassed(selectedTest.current) &&
                          !isTestPassed(selectedTest.baseline) && (
                            <TrendingUpIcon
                              fontSize="small"
                              sx={{ color: theme.palette.success.main }}
                            />
                          )}
                        {!isTestPassed(selectedTest.current) &&
                          isTestPassed(selectedTest.baseline) && (
                            <TrendingDownIcon
                              fontSize="small"
                              sx={{ color: theme.palette.error.main }}
                            />
                          )}
                      </>
                    )}
                  </Box>
                </Box>

                <Box
                  sx={{
                    maxHeight: 'calc(90vh - 200px)',
                    overflow: 'auto',
                    pr: 2,
                  }}
                >
                  {/* Prompt */}
                  <Box sx={{ mb: 3 }}>
                    <Typography
                      variant="overline"
                      color="text.secondary"
                      display="block"
                      gutterBottom
                    >
                      Prompt
                    </Typography>
                    <Paper
                      variant="outlined"
                      sx={{ p: 2.5, bgcolor: theme.palette.background.light1 }}
                    >
                      <Typography variant="body2">
                        {selectedTest.current.prompt_id &&
                        prompts[selectedTest.current.prompt_id]
                          ? prompts[selectedTest.current.prompt_id].content
                          : 'No prompt available'}
                      </Typography>
                    </Paper>
                  </Box>

                  {/* Response */}
                  <Box sx={{ mb: 3 }}>
                    <Typography
                      variant="overline"
                      color="text.secondary"
                      display="block"
                      gutterBottom
                    >
                      Response
                    </Typography>
                    <Paper
                      variant="outlined"
                      sx={{ p: 2.5, bgcolor: theme.palette.background.light1 }}
                    >
                      <Typography variant="body2">
                        {selectedTest.current.test_output?.output ||
                          'No response available'}
                      </Typography>
                    </Paper>
                  </Box>

                  {/* Metrics */}
                  <Typography variant="h6" sx={{ mb: 3 }}>
                    Metrics Breakdown
                  </Typography>
                  {behaviors.map(behavior => {
                    const behaviorMetrics = behavior.metrics
                      .map(metric => ({
                        ...metric,
                        currentResult:
                          selectedTest.current?.test_metrics?.metrics?.[
                            metric.name
                          ],
                        baselineResult:
                          selectedTest.baseline?.test_metrics?.metrics?.[
                            metric.name
                          ],
                      }))
                      .filter(m => m.currentResult || m.baselineResult);

                    if (behaviorMetrics.length === 0) return null;

                    const currentPassedCount = behaviorMetrics.filter(
                      m => m.currentResult?.is_successful
                    ).length;
                    const baselinePassedCount = behaviorMetrics.filter(
                      m => m.baselineResult?.is_successful
                    ).length;
                    const hasChanges =
                      currentPassedCount !== baselinePassedCount;

                    return (
                      <Accordion
                        key={behavior.id}
                        sx={{
                          mb: 2,
                          '&:before': { display: 'none' },
                          boxShadow: 'none',
                          border: 1,
                          borderColor: 'divider',
                        }}
                        defaultExpanded={hasChanges}
                      >
                        <AccordionSummary
                          expandIcon={<ExpandMoreIcon />}
                          sx={{ py: 2 }}
                        >
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                              width: '100%',
                            }}
                          >
                            <Typography variant="body2">
                              {behavior.name}
                            </Typography>
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.5,
                              }}
                            >
                              <Chip
                                label={`${currentPassedCount}/${behaviorMetrics.length}`}
                                size="small"
                                color={
                                  currentPassedCount === behaviorMetrics.length
                                    ? 'success'
                                    : 'error'
                                }
                              />
                              {hasChanges && (
                                <>
                                  {currentPassedCount > baselinePassedCount ? (
                                    <TrendingUpIcon
                                      fontSize="small"
                                      sx={{ color: theme.palette.success.main }}
                                    />
                                  ) : (
                                    <TrendingDownIcon
                                      fontSize="small"
                                      sx={{ color: theme.palette.error.main }}
                                    />
                                  )}
                                </>
                              )}
                            </Box>
                          </Box>
                        </AccordionSummary>
                        <AccordionDetails sx={{ p: 3 }}>
                          <Box
                            sx={{
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 3,
                            }}
                          >
                            {behaviorMetrics.map(metric => {
                              const scoreDiff =
                                metric.currentResult?.score != null &&
                                metric.baselineResult?.score != null
                                  ? Number(metric.currentResult.score) -
                                    Number(metric.baselineResult.score)
                                  : null;
                              const hasScoreChange =
                                scoreDiff !== null &&
                                Math.abs(scoreDiff) > 0.01;
                              const statusChanged =
                                metric.baselineResult &&
                                metric.currentResult &&
                                metric.baselineResult.is_successful !==
                                  metric.currentResult.is_successful;

                              return (
                                <Paper
                                  key={metric.name}
                                  variant="outlined"
                                  sx={{
                                    p: 3,
                                    bgcolor: statusChanged
                                      ? metric.currentResult?.is_successful
                                        ? theme.palette.mode === 'light'
                                          ? alpha(
                                              theme.palette.success.main,
                                              0.08
                                            )
                                          : theme.palette.background.light3
                                        : theme.palette.mode === 'light'
                                          ? alpha(
                                              theme.palette.error.main,
                                              0.08
                                            )
                                          : theme.palette.background.light3
                                      : 'transparent',
                                  }}
                                >
                                  <Box
                                    sx={{
                                      display: 'flex',
                                      alignItems: 'flex-start',
                                      gap: 1,
                                    }}
                                  >
                                    {metric.currentResult?.is_successful ? (
                                      <CheckCircleIcon
                                        fontSize="small"
                                        sx={{
                                          color: theme.palette.success.main,
                                        }}
                                      />
                                    ) : (
                                      <CancelIcon
                                        fontSize="small"
                                        sx={{ color: theme.palette.error.main }}
                                      />
                                    )}
                                    <Box sx={{ flex: 1 }}>
                                      <Box
                                        sx={{
                                          display: 'flex',
                                          alignItems: 'center',
                                          gap: 1,
                                          mb: 1,
                                        }}
                                      >
                                        <Typography variant="subtitle2">
                                          {metric.name}
                                        </Typography>
                                        {statusChanged && (
                                          <>
                                            {metric.currentResult
                                              ?.is_successful ? (
                                              <TrendingUpIcon
                                                fontSize="small"
                                                sx={{
                                                  color:
                                                    theme.palette.success.main,
                                                }}
                                              />
                                            ) : (
                                              <TrendingDownIcon
                                                fontSize="small"
                                                sx={{
                                                  color:
                                                    theme.palette.error.main,
                                                }}
                                              />
                                            )}
                                          </>
                                        )}
                                      </Box>
                                      {metric.currentResult?.score != null && (
                                        <Box sx={{ mb: 1 }}>
                                          <Box
                                            sx={{
                                              display: 'flex',
                                              justifyContent: 'space-between',
                                              mb: 0.5,
                                            }}
                                          >
                                            <Typography variant="caption">
                                              Score:{' '}
                                              {Number(
                                                metric.currentResult.score
                                              ).toFixed(2)}
                                              {hasScoreChange && (
                                                <Typography
                                                  component="span"
                                                  variant="caption"
                                                  sx={{
                                                    ml: 0.5,
                                                    color:
                                                      scoreDiff! > 0
                                                        ? theme.palette.success
                                                            .main
                                                        : theme.palette.error
                                                            .main,
                                                    fontWeight: 500,
                                                  }}
                                                >
                                                  ({scoreDiff! > 0 ? '+' : ''}
                                                  {scoreDiff!.toFixed(2)})
                                                </Typography>
                                              )}
                                            </Typography>
                                            {metric.currentResult.threshold !=
                                              null && (
                                              <Typography
                                                variant="caption"
                                                color="text.secondary"
                                              >
                                                Threshold: ≥
                                                {Number(
                                                  metric.currentResult.threshold
                                                ).toFixed(2)}
                                              </Typography>
                                            )}
                                          </Box>
                                          <LinearProgress
                                            variant="determinate"
                                            value={
                                              Number(
                                                metric.currentResult.score
                                              ) * 100
                                            }
                                            color={
                                              metric.currentResult.is_successful
                                                ? 'success'
                                                : 'error'
                                            }
                                            sx={{
                                              height: 8,
                                              borderRadius:
                                                theme.shape.borderRadius / 4,
                                              bgcolor:
                                                theme.palette.background.light2,
                                            }}
                                          />
                                        </Box>
                                      )}
                                      {metric.currentResult?.reason && (
                                        <Typography
                                          variant="caption"
                                          color="text.secondary"
                                        >
                                          {metric.currentResult.reason}
                                        </Typography>
                                      )}
                                    </Box>
                                  </Box>
                                </Paper>
                              );
                            })}
                          </Box>
                        </AccordionDetails>
                      </Accordion>
                    );
                  })}
                </Box>
              </Grid>
            </Grid>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
}
