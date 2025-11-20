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
import { MetricStatusChip } from '@/components/common/StatusChip';
import ConversationHistory from '@/components/common/ConversationHistory';

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
  testSetType?: string; // e.g., "Multi-turn" or "Single-turn"
  project?: { icon?: string; useCase?: string; name?: string };
  projectName?: string;
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
  testSetType,
  project,
  projectName,
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

  // Determine if this is a multi-turn test
  const isMultiTurn =
    testSetType?.toLowerCase().includes('multi-turn') || false;

  // Load baseline data when selection changes
  React.useEffect(() => {
    if (selectedBaselineId) {
      setLoading(true);
      onLoadBaseline(selectedBaselineId)
        .then(setBaselineTestResults)
        .catch(error => {
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
        // For multi-turn tests, search in goal and evaluation
        if (isMultiTurn) {
          const goalContent =
            test.current.test_output?.test_configuration?.goal?.toLowerCase() ||
            '';
          const evaluationContent =
            test.current.test_output?.goal_evaluation?.reason?.toLowerCase() ||
            '';
          return (
            goalContent.includes(query) || evaluationContent.includes(query)
          );
        }
        // For single-turn tests, search in prompt and response
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
  }, [allComparisonTests, statusFilter, searchQuery, prompts, isMultiTurn]);

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
    // For multi-turn tests, show goal instead of prompt
    if (isMultiTurn) {
      const goal = test.test_output?.test_configuration?.goal;
      if (!goal) {
        return `Test #${test.id.slice(0, 8)}`;
      }
      if (goal.length <= maxLength) {
        return goal;
      }
      return goal.slice(0, maxLength).trim() + '...';
    }

    // For single-turn tests, show prompt
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
      {/* Filter Bar with integrated Close Button */}
      {baselineTestResults && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', sm: 'row' },
            gap: 2,
            mb: 3,
            alignItems: { xs: 'stretch', sm: 'center' },
            justifyContent: 'space-between',
          }}
        >
          {/* Left side: Search and Filters */}
          <Box
            sx={{
              display: 'flex',
              flexDirection: { xs: 'column', sm: 'row' },
              gap: 2,
              alignItems: { xs: 'stretch', sm: 'center' },
              flex: 1,
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
                variant={
                  statusFilter === 'regressed' ? 'contained' : 'outlined'
                }
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
                variant={
                  statusFilter === 'unchanged' ? 'contained' : 'outlined'
                }
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

          {/* Right side: Close Button */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: { xs: 'flex-start', sm: 'flex-end' },
            }}
          >
            <Button
              onClick={onClose}
              variant="outlined"
              size="small"
              startIcon={<CloseIcon />}
            >
              Close Comparison
            </Button>
          </Box>
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

      {/* Comparison Headers - Moved Here */}
      {baselineTestResults && (
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
                          <span>
                            {run.name || `Run #${run.id.slice(0, 8)}`}
                          </span>
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
                  {currentTestRun.name ||
                    `Run #${currentTestRun.id.slice(0, 8)}`}
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
                // Increase height by 50% if there are 5+ tests to display
                maxHeight:
                  comparisonTests.length >= 5 ? 'calc(70vh * 1.5)' : '70vh',
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

                // Get content based on test type
                const contentLabel = isMultiTurn ? 'Goal' : 'Prompt';
                const promptContent = isMultiTurn
                  ? test.current.test_output?.test_configuration?.goal ||
                    'No goal available'
                  : test.current.prompt_id && prompts[test.current.prompt_id]
                    ? prompts[test.current.prompt_id].content
                    : 'No prompt available';

                // Get responses/evaluations based on test type
                const responseLabel = isMultiTurn
                  ? 'Overall Evaluation'
                  : 'Response';
                const baselineResponse = isMultiTurn
                  ? test.baseline?.test_output?.goal_evaluation?.reason ||
                    'No evaluation available'
                  : test.baseline?.test_output?.output ||
                    'No response available';
                const currentResponse = isMultiTurn
                  ? test.current.test_output?.goal_evaluation?.reason ||
                    'No evaluation available'
                  : test.current.test_output?.output || 'No response available';

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
                    <Box>
                      {/* Prompt/Goal Section - Full Width, Inline */}
                      <Box
                        sx={{
                          p: 2,
                          borderBottom: 1,
                          borderColor: 'divider',
                          bgcolor: theme.palette.background.default,
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 1,
                        }}
                      >
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ fontWeight: 600, flexShrink: 0 }}
                        >
                          {contentLabel}:
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{
                            flex: 1,
                            fontWeight: 500,
                          }}
                        >
                          {promptContent}
                        </Typography>
                      </Box>

                      {/* Responses/Evaluations Side by Side */}
                      <Grid container spacing={0}>
                        {/* Baseline Response/Evaluation */}
                        <Grid
                          item
                          xs={12}
                          md={6}
                          sx={{
                            p: 2,
                            borderRight: { md: 1 },
                            borderColor: 'divider',
                            bgcolor: isImproved
                              ? `${theme.palette.background.default}`
                              : isRegressed
                                ? `${theme.palette.background.default}`
                                : 'transparent',
                          }}
                        >
                          {/* Header with Status Inline */}
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                              mb: 1,
                              flexWrap: 'wrap',
                            }}
                          >
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{ fontWeight: 600 }}
                            >
                              Baseline:
                            </Typography>
                            {baselinePassed !== null && (
                              <MetricStatusChip
                                passedCount={baselinePassedCount}
                                totalCount={baselineTotalCount}
                                size="small"
                                variant="filled"
                                sx={{
                                  height: 20,
                                  fontSize: theme =>
                                    theme.typography.caption.fontSize,
                                }}
                              />
                            )}
                            {baselinePassed === null && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                No data
                              </Typography>
                            )}
                          </Box>

                          {/* Response/Evaluation Text */}
                          <Typography
                            variant="body2"
                            sx={{
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                            }}
                          >
                            {baselineResponse}
                          </Typography>
                        </Grid>

                        {/* Current Response/Evaluation */}
                        <Grid
                          item
                          xs={12}
                          md={6}
                          sx={{
                            p: 2,
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
                          {/* Header with Status Inline */}
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                              mb: 1,
                              flexWrap: 'wrap',
                            }}
                          >
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{ fontWeight: 600 }}
                            >
                              Current:
                            </Typography>
                            <MetricStatusChip
                              passedCount={currentPassedCount}
                              totalCount={currentTotalCount}
                              size="small"
                              variant="filled"
                              sx={{
                                height: 20,
                                fontSize: theme =>
                                  theme.typography.caption.fontSize,
                              }}
                            />
                            {isImproved && (
                              <TrendingUpIcon
                                sx={{
                                  fontSize: 16,
                                  color: theme.palette.success.main,
                                }}
                              />
                            )}
                            {isRegressed && (
                              <TrendingDownIcon
                                sx={{
                                  fontSize: 16,
                                  color: theme.palette.error.main,
                                }}
                              />
                            )}
                          </Box>

                          {/* Response/Evaluation Text */}
                          <Typography
                            variant="body2"
                            sx={{
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                            }}
                          >
                            {currentResponse}
                          </Typography>
                        </Grid>
                      </Grid>
                    </Box>
                  </Paper>
                );
              })}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Detailed Comparison Dialog */}
      {/* For multi-turn tests, show side-by-side conversations. For single-turn, show detailed metrics. */}
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
              alignItems: 'flex-start',
              gap: 2,
            }}
          >
            <Typography variant="h6" sx={{ flex: 1, pr: 2 }}>
              Test #
              {comparisonTests.findIndex(t => t.id === selectedTestId) + 1}:{' '}
              {selectedTest
                ? isMultiTurn
                  ? selectedTest.current.test_output?.test_configuration
                      ?.goal || 'No goal available'
                  : selectedTest.current.prompt_id &&
                      prompts[selectedTest.current.prompt_id]
                    ? prompts[selectedTest.current.prompt_id].content
                    : 'No prompt available'
                : ''}
            </Typography>
            <IconButton
              onClick={() => setSelectedTestId(null)}
              size="small"
              sx={{ flexShrink: 0 }}
            >
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {selectedTest && (
            <Box>
              {isMultiTurn ? (
                /* Multi-turn: Show side-by-side conversations */
                <Grid
                  container
                  spacing={0}
                  sx={{ height: 'calc(90vh - 200px)' }}
                >
                  {/* Baseline Conversation Column */}
                  <Grid
                    item
                    xs={12}
                    md={6}
                    sx={{
                      borderRight: { md: 1 },
                      borderColor: 'divider',
                    }}
                  >
                    <Box
                      sx={{
                        height: '100%',
                        overflow: 'auto',
                        display: 'flex',
                        flexDirection: 'column',
                      }}
                    >
                      <Box
                        sx={{
                          p: 2,
                          borderBottom: 1,
                          borderColor: 'divider',
                          bgcolor: theme.palette.background.default,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          flexWrap: 'wrap',
                        }}
                      >
                        <Typography
                          variant="overline"
                          color="text.secondary"
                          sx={{ fontWeight: 600 }}
                        >
                          Baseline Run
                        </Typography>
                        {selectedTest.baseline ? (
                          <MetricStatusChip
                            passedCount={
                              Object.values(
                                selectedTest.baseline.test_metrics?.metrics ||
                                  {}
                              ).filter(m => m.is_successful).length
                            }
                            totalCount={
                              Object.values(
                                selectedTest.baseline.test_metrics?.metrics ||
                                  {}
                              ).length
                            }
                            size="small"
                            variant="filled"
                          />
                        ) : (
                          <Chip label="No data" size="small" color="default" />
                        )}
                      </Box>
                      {selectedTest.baseline?.test_output
                        ?.conversation_summary ? (
                        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
                          <ConversationHistory
                            conversationSummary={
                              selectedTest.baseline.test_output
                                .conversation_summary
                            }
                            goalEvaluation={
                              selectedTest.baseline.test_output.goal_evaluation
                            }
                            project={project}
                            projectName={projectName}
                            hasExistingReview={
                              !!selectedTest.baseline.last_review
                            }
                            reviewMatchesAutomated={
                              selectedTest.baseline.matches_review === true
                            }
                            maxHeight="100%"
                          />
                        </Box>
                      ) : (
                        <Box
                          sx={{
                            flex: 1,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            p: 3,
                          }}
                        >
                          <Typography variant="body2" color="text.secondary">
                            No conversation data available
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </Grid>

                  {/* Current Conversation Column */}
                  <Grid item xs={12} md={6}>
                    <Box
                      sx={{
                        height: '100%',
                        overflow: 'auto',
                        display: 'flex',
                        flexDirection: 'column',
                      }}
                    >
                      <Box
                        sx={{
                          p: 2,
                          borderBottom: 1,
                          borderColor: 'divider',
                          bgcolor: theme.palette.background.default,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          flexWrap: 'wrap',
                        }}
                      >
                        <Typography
                          variant="overline"
                          color="text.secondary"
                          sx={{ fontWeight: 600 }}
                        >
                          Current Run
                        </Typography>
                        <MetricStatusChip
                          passedCount={
                            Object.values(
                              selectedTest.current.test_metrics?.metrics || {}
                            ).filter(m => m.is_successful).length
                          }
                          totalCount={
                            Object.values(
                              selectedTest.current.test_metrics?.metrics || {}
                            ).length
                          }
                          size="small"
                          variant="filled"
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
                      {selectedTest.current.test_output
                        ?.conversation_summary ? (
                        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
                          <ConversationHistory
                            conversationSummary={
                              selectedTest.current.test_output
                                .conversation_summary
                            }
                            goalEvaluation={
                              selectedTest.current.test_output.goal_evaluation
                            }
                            project={project}
                            projectName={projectName}
                            hasExistingReview={
                              !!selectedTest.current.last_review
                            }
                            reviewMatchesAutomated={
                              selectedTest.current.matches_review === true
                            }
                            maxHeight="100%"
                          />
                        </Box>
                      ) : (
                        <Box
                          sx={{
                            flex: 1,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            p: 3,
                          }}
                        >
                          <Typography variant="body2" color="text.secondary">
                            No conversation data available
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </Grid>
                </Grid>
              ) : (
                /* Single-turn: Show detailed metrics comparison */
                <Grid
                  container
                  spacing={0}
                  sx={{ height: 'calc(90vh - 200px)' }}
                >
                  {/* Baseline Column */}
                  <Grid
                    item
                    xs={12}
                    md={6}
                    sx={{
                      borderRight: { md: 1 },
                      borderColor: 'divider',
                    }}
                  >
                    <Box
                      sx={{
                        p: 3,
                        height: '100%',
                        overflow: 'auto',
                      }}
                    >
                      <Box
                        sx={{
                          mb: 3,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          flexWrap: 'wrap',
                        }}
                      >
                        <Typography
                          variant="overline"
                          color="text.secondary"
                          sx={{ fontWeight: 600 }}
                        >
                          Baseline Run
                        </Typography>
                        {selectedTest.baseline ? (
                          <MetricStatusChip
                            passedCount={
                              Object.values(
                                selectedTest.baseline.test_metrics?.metrics ||
                                  {}
                              ).filter(m => m.is_successful).length
                            }
                            totalCount={
                              Object.values(
                                selectedTest.baseline.test_metrics?.metrics ||
                                  {}
                              ).length
                            }
                            size="small"
                            variant="filled"
                          />
                        ) : (
                          <Chip label="No data" size="small" color="default" />
                        )}
                      </Box>

                      {selectedTest.baseline && (
                        <>
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
                          {behaviors.map(behavior => {
                            const behaviorMetrics = behavior.metrics
                              .map(metric => ({
                                ...metric,
                                baselineResult:
                                  selectedTest.baseline?.test_metrics
                                    ?.metrics?.[metric.name],
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
                                    <Typography
                                      variant="body1"
                                      sx={{ fontWeight: 600 }}
                                    >
                                      {behavior.name}
                                    </Typography>
                                    <Chip
                                      label={`${baselinePassedCount}/${behaviorMetrics.length}`}
                                      size="small"
                                      color={
                                        baselinePassedCount ===
                                        behaviorMetrics.length
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
                                            {metric.baselineResult
                                              ?.is_successful ? (
                                              <CheckCircleIcon
                                                fontSize="small"
                                                sx={{
                                                  color:
                                                    theme.palette.success.main,
                                                }}
                                              />
                                            ) : (
                                              <CancelIcon
                                                fontSize="small"
                                                sx={{
                                                  color:
                                                    theme.palette.error.main,
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
                                                      justifyContent:
                                                        'space-between',
                                                      mb: 0.5,
                                                    }}
                                                  >
                                                    <Typography variant="caption">
                                                      Score:{' '}
                                                      {Number(
                                                        metric.baselineResult
                                                          .score
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
                                                                    .success
                                                                    .main
                                                                : theme.palette
                                                                    .error.main,
                                                            fontWeight: 500,
                                                          }}
                                                        >
                                                          (
                                                          {scoreDiff! > 0
                                                            ? '+'
                                                            : ''}
                                                          {scoreDiff!.toFixed(
                                                            2
                                                          )}
                                                          )
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
                                                        metric.baselineResult
                                                          .score
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
                                                        theme.shape
                                                          .borderRadius / 4,
                                                      bgcolor:
                                                        theme.palette.background
                                                          .light2,
                                                    }}
                                                  />
                                                </Box>
                                              )}
                                              {metric.baselineResult
                                                ?.reason && (
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
                        </>
                      )}
                    </Box>
                  </Grid>

                  {/* Current Column */}
                  <Grid item xs={12} md={6}>
                    <Box
                      sx={{
                        p: 3,
                        height: '100%',
                        overflow: 'auto',
                      }}
                    >
                      <Box
                        sx={{
                          mb: 3,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          flexWrap: 'wrap',
                        }}
                      >
                        <Typography
                          variant="overline"
                          color="text.secondary"
                          sx={{ fontWeight: 600 }}
                        >
                          Current Run
                        </Typography>
                        <MetricStatusChip
                          passedCount={
                            Object.values(
                              selectedTest.current.test_metrics?.metrics || {}
                            ).filter(m => m.is_successful).length
                          }
                          totalCount={
                            Object.values(
                              selectedTest.current.test_metrics?.metrics || {}
                            ).length
                          }
                          size="small"
                          variant="filled"
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
                            {selectedTest.current.test_output?.output ||
                              'No response available'}
                          </Typography>
                        </Paper>
                      </Box>

                      {/* Metrics */}
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
                                <Typography
                                  variant="body1"
                                  sx={{ fontWeight: 600 }}
                                >
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
                                      currentPassedCount ===
                                      behaviorMetrics.length
                                        ? 'success'
                                        : 'error'
                                    }
                                  />
                                  {hasChanges && (
                                    <>
                                      {currentPassedCount >
                                      baselinePassedCount ? (
                                        <TrendingUpIcon
                                          fontSize="small"
                                          sx={{
                                            color: theme.palette.success.main,
                                          }}
                                        />
                                      ) : (
                                        <TrendingDownIcon
                                          fontSize="small"
                                          sx={{
                                            color: theme.palette.error.main,
                                          }}
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
                                            sx={{
                                              color: theme.palette.error.main,
                                            }}
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
                                                        theme.palette.success
                                                          .main,
                                                    }}
                                                  />
                                                ) : (
                                                  <TrendingDownIcon
                                                    fontSize="small"
                                                    sx={{
                                                      color:
                                                        theme.palette.error
                                                          .main,
                                                    }}
                                                  />
                                                )}
                                              </>
                                            )}
                                          </Box>
                                          {metric.currentResult?.score !=
                                            null && (
                                            <Box sx={{ mb: 1 }}>
                                              <Box
                                                sx={{
                                                  display: 'flex',
                                                  justifyContent:
                                                    'space-between',
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
                                                            ? theme.palette
                                                                .success.main
                                                            : theme.palette
                                                                .error.main,
                                                        fontWeight: 500,
                                                      }}
                                                    >
                                                      (
                                                      {scoreDiff! > 0
                                                        ? '+'
                                                        : ''}
                                                      {scoreDiff!.toFixed(2)})
                                                    </Typography>
                                                  )}
                                                </Typography>
                                                {metric.currentResult
                                                  .threshold != null && (
                                                  <Typography
                                                    variant="caption"
                                                    color="text.secondary"
                                                  >
                                                    Threshold: ≥
                                                    {Number(
                                                      metric.currentResult
                                                        .threshold
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
                                                  metric.currentResult
                                                    .is_successful
                                                    ? 'success'
                                                    : 'error'
                                                }
                                                sx={{
                                                  height: 8,
                                                  borderRadius:
                                                    theme.shape.borderRadius /
                                                    4,
                                                  bgcolor:
                                                    theme.palette.background
                                                      .light2,
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
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
}
