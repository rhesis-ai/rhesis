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
  Dialog,
  DialogContent,
  Collapse,
  LinearProgress,
  Chip,
  Grid,
  Paper,
  useTheme,
  alpha,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import Link from 'next/link';
import Image from 'next/image';
import {
  TestResultDetail,
  MetricResult,
} from '@/utils/api-client/interfaces/test-results';
import { experimentHref } from '@/utils/experiment-links';
import { MetricStatusChip } from '@/components/common/StatusChip';
import ConversationHistory from '@/components/common/ConversationHistory';
import { SearchPill } from '@/components/common/SearchPill';
import { PrimarySegmentedPills } from '@/components/common/GridToolbar';
import { BiotechIcon } from '@/components/icons';
import { shortVersion } from '@/utils/api-client/interfaces/parameters';
import { formatDate } from '@/utils/date';

interface RunExperimentInfo {
  experiment_id?: string;
  parameter_version?: string;
  experiment_name?: string;
}

interface ComparisonViewProps {
  currentTestRun: {
    id: string;
    name?: string;
    created_at: string;
  } & RunExperimentInfo;
  currentTestResults: TestResultDetail[];
  availableTestRuns: Array<
    {
      id: string;
      name?: string;
      created_at: string;
      pass_rate?: number;
    } & RunExperimentInfo
  >;
  onClose: () => void;
  onLoadBaseline: (testRunId: string) => Promise<TestResultDetail[]>;
  prompts: Record<string, { content: string; name?: string }>;
  behaviors: Array<{
    id: string;
    name: string;
    description?: string;
    metrics: Array<{ name: string; description?: string }>;
  }>;
  testSetType?: string;
  project?: { icon?: string; useCase?: string; name?: string };
  projectName?: string;
  initialBaselineId?: string;
  closeButtonLabel?: string;
}

interface ComparisonTest {
  id: string;
  baseline?: TestResultDetail;
  current: TestResultDetail;
}

function ExperimentRunLink({
  experimentId,
  parameterVersion,
  experimentName,
}: {
  experimentId?: string;
  parameterVersion?: string;
  experimentName?: string;
}) {
  if (!experimentId || !parameterVersion) return null;

  return (
    <Link
      href={experimentHref(experimentId, parameterVersion)}
      target="_blank"
      rel="noopener noreferrer"
      style={{ textDecoration: 'none' }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          '&:hover .experiment-label': {
            color: 'primary.main',
            textDecoration: 'underline',
          },
        }}
      >
        <BiotechIcon fontSize="small" sx={{ color: 'text.secondary' }} />
        <Typography
          variant="caption"
          className="experiment-label"
          color="text.secondary"
        >
          {experimentName || 'Experiment'}
        </Typography>
        <Chip
          label={shortVersion(parameterVersion)}
          size="small"
          variant="outlined"
        />
        <OpenInNewIcon fontSize="inherit" sx={{ color: 'text.disabled' }} />
      </Box>
    </Link>
  );
}

// Individual metric result row matching Figma "Testrun Comparison" component
function MetricRow({
  metricName,
  result,
}: {
  metricName: string;
  result?: MetricResult;
}) {
  const isPassed = result?.is_successful ?? false;
  return (
    <Paper
      variant="outlined"
      sx={{ borderRadius: '4px', pt: '30px', pb: '20px', px: '30px' }}
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
        {isPassed ? (
          <CheckCircleIcon
            sx={{
              color: 'success.main',
              fontSize: 24,
              flexShrink: 0,
              mt: '2px',
            }}
          />
        ) : (
          <CancelIcon
            sx={{ color: 'error.main', fontSize: 24, flexShrink: 0, mt: '2px' }}
          />
        )}
        <Box sx={{ flex: 1 }}>
          <Typography
            sx={{ fontWeight: 700, fontSize: 16, lineHeight: '24px' }}
          >
            {metricName}
          </Typography>
          {result != null && result.score != null && (
            <Box sx={{ mt: 1 }}>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  mb: 0.5,
                }}
              >
                <Typography sx={{ fontSize: 14, lineHeight: '22px' }}>
                  Score: {Number(result.score).toFixed(2)}
                </Typography>
                {result.threshold != null && (
                  <Typography
                    sx={{
                      fontSize: 14,
                      lineHeight: '22px',
                      color: 'text.secondary',
                    }}
                  >
                    Threshold: ≥{Number(result.threshold).toFixed(2)}
                  </Typography>
                )}
              </Box>
              <LinearProgress
                variant="determinate"
                value={Math.min(Number(result.score) * 100, 100)}
                color={isPassed ? 'success' : 'error'}
                sx={{
                  height: 8,
                  borderRadius: '999px',
                  bgcolor: theme => theme.palette.background.light2,
                }}
              />
              {result.reason && (
                <Typography
                  sx={{
                    mt: 1,
                    fontSize: 14,
                    lineHeight: '22px',
                    color: theme => theme.palette.greyscale.body,
                  }}
                >
                  {result.reason}
                </Typography>
              )}
            </Box>
          )}
        </Box>
      </Box>
    </Paper>
  );
}

// Collapsible behavior section card matching Figma "section 1" component
function BehaviorSection({
  behaviorName,
  passedCount,
  totalCount,
  children,
}: {
  behaviorName: string;
  passedCount: number;
  totalCount: number;
  children: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(true);
  return (
    <Box
      sx={{
        border: theme => `1px solid ${theme.palette.greyscale.border}`,
        borderRadius: '12px',
        boxShadow: '0px 2px 2px rgba(84, 90, 101, 0.25)',
        bgcolor: 'background.paper',
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: '30px',
          pt: '30px',
          pb: '30px',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <Typography
            sx={{
              fontSize: 20,
              fontWeight: 600,
              lineHeight: '24px',
              color: theme => theme.palette.greyscale.title,
            }}
          >
            {behaviorName}
          </Typography>
          <Chip
            label={`${passedCount}/${totalCount}`}
            size="small"
            color={passedCount === totalCount ? 'success' : 'error'}
          />
        </Box>
        <IconButton
          onClick={() => setExpanded(prev => !prev)}
          size="small"
          sx={{
            transform: expanded ? 'rotate(0deg)' : 'rotate(180deg)',
            transition: 'transform 0.2s',
          }}
        >
          <KeyboardArrowUpIcon />
        </IconButton>
      </Box>
      <Collapse in={expanded}>
        <Box
          sx={{
            px: '30px',
            pb: '30px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          {children}
        </Box>
      </Collapse>
    </Box>
  );
}

// Response text box for a single run
function RunResponseBox({ response }: { response: string }) {
  return (
    <Paper
      variant="outlined"
      sx={{
        bgcolor: theme => theme.palette.background.light1,
        borderRadius: '4px',
        p: '30px',
        borderColor: theme => theme.palette.greyscale.border,
      }}
    >
      <Typography
        sx={{
          fontSize: 14,
          lineHeight: '22px',
          color: theme => theme.palette.greyscale.body,
        }}
      >
        {response}
      </Typography>
    </Paper>
  );
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
  initialBaselineId,
  closeButtonLabel = 'Close Comparison',
}: ComparisonViewProps) {
  const theme = useTheme();
  const [selectedBaselineId, setSelectedBaselineId] = useState<string>(
    initialBaselineId || availableTestRuns[0]?.id || ''
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
        .catch(_error => {
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
  const _getPassRate = (test: TestResultDetail) => {
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

  const _getPromptSnippet = (
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
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
      {/* Header: Close Comparison (top-right) above logo + current run name */}
      <Box sx={{ display: 'flex', flexDirection: 'column' }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            mb: '12px',
          }}
        >
          <Button
            onClick={onClose}
            variant="contained"
            startIcon={<CloseIcon />}
            sx={{
              borderRadius: '8px',
              px: '16px',
              py: '8px',
              fontWeight: 700,
              fontSize: 14,
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            {closeButtonLabel}
          </Button>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Box
            sx={{
              width: 40,
              height: 40,
              flexShrink: 0,
              position: 'relative',
            }}
          >
            <Image
              src="/logos/rhesis-logo-favicon-transparent.svg"
              alt="Rhesis"
              fill
              sizes="40px"
              style={{ objectFit: 'contain' }}
            />
          </Box>
          <Typography
            sx={{
              fontSize: 28,
              fontWeight: 700,
              lineHeight: '33.6px',
              color: theme => theme.palette.greyscale.title,
            }}
          >
            {currentTestRun.name || 'Test Run'}
          </Typography>
        </Box>
      </Box>
      {/* Comparison Headers */}
      {baselineTestResults && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', md: 'row' },
            gap: '20px',
            alignItems: 'stretch',
          }}
        >
          {/* Baseline Run */}
          <Paper
            variant="outlined"
            sx={{
              flex: 1,
              minWidth: 0,
              p: '30px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              borderRadius: '4px',
            }}
          >
            <Typography
              sx={{
                fontSize: 20,
                fontWeight: 600,
                lineHeight: '24px',
                color: theme => theme.palette.greyscale.title,
              }}
            >
              Baseline Run
            </Typography>
            <FormControl fullWidth>
              <InputLabel>Select baseline run</InputLabel>
              <Select
                value={selectedBaselineId}
                onChange={e => setSelectedBaselineId(e.target.value)}
                label="Select baseline run"
                renderValue={value => {
                  const run = availableTestRuns.find(r => r.id === value);
                  const name = run?.name || `Run #${String(value).slice(0, 8)}`;
                  return (
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'baseline',
                        gap: 1,
                        minWidth: 0,
                      }}
                    >
                      <Box
                        component="span"
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {name}
                      </Box>
                      {run?.created_at && (
                        <Typography
                          component="span"
                          variant="caption"
                          color="text.secondary"
                          sx={{ flexShrink: 0 }}
                        >
                          {formatDate(run.created_at)}
                        </Typography>
                      )}
                    </Box>
                  );
                }}
              >
                {availableTestRuns.map(run => (
                  <MenuItem key={run.id} value={run.id}>
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        gap: 2,
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
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {baselinePassRate !== undefined && (
                  <Typography variant="body2" color="text.secondary">
                    Pass rate:{' '}
                    <Box
                      component="span"
                      sx={{ fontWeight: 700, color: 'text.primary' }}
                    >
                      {Math.round(baselinePassRate)}%
                    </Box>
                  </Typography>
                )}
                {baselineRun.experiment_id && baselineRun.parameter_version && (
                  <ExperimentRunLink
                    experimentId={baselineRun.experiment_id}
                    parameterVersion={baselineRun.parameter_version}
                    experimentName={baselineRun.experiment_name}
                  />
                )}
              </Box>
            )}
          </Paper>

          {/* Compare arrows */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <CompareArrowsIcon
              sx={{
                fontSize: 48,
                color: theme => theme.palette.greyscale.body,
              }}
            />
          </Box>

          {/* Current Run */}
          <Paper
            variant="outlined"
            sx={{
              flex: 1,
              minWidth: 0,
              p: '30px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              borderRadius: '4px',
              bgcolor: theme => theme.palette.background.light2,
              border: theme => `1px solid ${theme.palette.primary.main}`,
            }}
          >
            <Typography
              sx={{
                fontSize: 20,
                fontWeight: 600,
                lineHeight: '24px',
                color: theme => theme.palette.greyscale.title,
              }}
            >
              Current Run
            </Typography>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                gap: 1,
              }}
            >
              <Typography sx={{ fontWeight: 700, fontSize: 16 }}>
                {currentTestRun.name || `Run #${currentTestRun.id.slice(0, 8)}`}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {formatDate(currentTestRun.created_at)}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Typography variant="body2" color="text.secondary">
                Pass rate:{' '}
                <Box
                  component="span"
                  sx={{ fontWeight: 700, color: 'text.primary' }}
                >
                  {currentPassRate}%
                </Box>
                {baselinePassRate !== undefined && (
                  <Box
                    component="span"
                    sx={{
                      ml: 0.5,
                      fontWeight: 700,
                      color:
                        currentPassRate > baselinePassRate
                          ? theme.palette.success.main
                          : currentPassRate < baselinePassRate
                            ? theme.palette.error.main
                            : theme.palette.text.secondary,
                    }}
                  >
                    ({currentPassRate > baselinePassRate ? '+' : ''}
                    {(currentPassRate - baselinePassRate).toFixed(1)}%)
                  </Box>
                )}
              </Typography>
              {currentTestRun.experiment_id &&
                currentTestRun.parameter_version && (
                  <ExperimentRunLink
                    experimentId={currentTestRun.experiment_id}
                    parameterVersion={currentTestRun.parameter_version}
                    experimentName={currentTestRun.experiment_name}
                  />
                )}
            </Box>
          </Paper>
        </Box>
      )}

      {/* Toolbar: search + status filter pills */}
      {baselineTestResults && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: { xs: 'column', md: 'row' },
            gap: 2,
            alignItems: { xs: 'stretch', md: 'center' },
          }}
        >
          <SearchPill
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search tests..."
            width={288}
          />
          <PrimarySegmentedPills
            mode="single"
            activeValue={statusFilter}
            onSingleChange={value =>
              setStatusFilter(
                value as 'all' | 'improved' | 'regressed' | 'unchanged'
              )
            }
            tabs={[
              { value: 'all', label: 'All' },
              { value: 'improved', label: `Improved (${stats.improved})` },
              { value: 'regressed', label: `Regressed (${stats.regressed})` },
              { value: 'unchanged', label: `Unchanged (${stats.unchanged})` },
            ]}
          />
        </Box>
      )}
      {/* Test-by-Test Comparison */}
      {baselineTestResults && (
        <Card
          sx={{
            borderRadius: '12px',
            border: theme => `1px solid ${theme.palette.greyscale.border}`,
          }}
        >
          <CardContent sx={{ p: '30px' }}>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: '20px',
              }}
            >
              <Typography
                sx={{
                  fontSize: 20,
                  fontWeight: 600,
                  lineHeight: '24px',
                  color: 'primary.main',
                }}
              >
                Test-by-Test Comparison
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Click any test to view details
              </Typography>
            </Box>
            <Box
              sx={{
                maxHeight:
                  comparisonTests.length >= 5 ? 'calc(70vh * 1.5)' : '70vh',
                overflow: 'auto',
              }}
            >
              {comparisonTests.map((test, _index) => {
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
                const _responseLabel = isMultiTurn
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
                      mb: '20px',
                      borderRadius: '4px',
                      overflow: 'hidden',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease-in-out',
                      pt: '30px',
                      pb: '20px',
                      '&:hover': {
                        boxShadow: theme.shadows[6],
                        borderColor: theme.palette.greyscale.subtitle,
                      },
                    }}
                    onClick={() => setSelectedTestId(test.id)}
                  >
                    <Box>
                      {/* Prompt/Goal Section - Full Width, Inline */}
                      <Box
                        sx={{
                          px: '30px',
                          pb: '20px',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '10px',
                        }}
                      >
                        <Typography
                          variant="body2"
                          sx={{ fontWeight: 700, color: '#000', flexShrink: 0 }}
                        >
                          {contentLabel}:
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{ flex: 1, color: theme.palette.greyscale.body }}
                        >
                          {promptContent}
                        </Typography>
                      </Box>

                      {/* Responses/Evaluations Side by Side */}
                      <Grid container spacing={0} sx={{ px: '20px' }}>
                        {/* Baseline Response/Evaluation */}
                        <Grid
                          sx={{
                            px: '10px',
                            py: '20px',
                            borderRight: { md: 1 },
                            borderColor: 'divider',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '10px',
                            bgcolor: isImproved
                              ? `${theme.palette.background.default}`
                              : isRegressed
                                ? `${theme.palette.background.default}`
                                : 'transparent',
                          }}
                          size={{
                            xs: 12,
                            md: 6,
                          }}
                        >
                          {/* Header with Status Inline */}
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '10px',
                              flexWrap: 'wrap',
                            }}
                          >
                            <Typography
                              variant="body2"
                              sx={{ fontWeight: 700, color: '#000' }}
                            >
                              Baseline
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
                          sx={{
                            pl: '10px',
                            pr: 0,
                            py: '20px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '10px',
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
                          size={{
                            xs: 12,
                            md: 6,
                          }}
                        >
                          {/* Header with Status Inline */}
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '10px',
                              flexWrap: 'wrap',
                            }}
                          >
                            <Typography
                              variant="body2"
                              sx={{ fontWeight: 700, color: '#000' }}
                            >
                              Current
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
      <Dialog
        open={selectedTestId !== null}
        onClose={() => setSelectedTestId(null)}
        maxWidth="xl"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: '16px',
            maxHeight: '90vh',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          },
        }}
        slotProps={{
          backdrop: {
            sx: { backgroundColor: 'rgba(0, 101, 140, 0.8)' },
          },
        }}
      >
        {/* Custom header: close icon + test title */}
        <Box
          sx={{
            position: 'relative',
            px: '37px',
            pt: '30px',
            pb: 0,
            flexShrink: 0,
          }}
        >
          <IconButton
            onClick={() => setSelectedTestId(null)}
            size="small"
            sx={{ position: 'absolute', top: 16, right: 16 }}
          >
            <CloseIcon />
          </IconButton>
          <Typography
            sx={{
              fontSize: 20,
              lineHeight: '24px',
              pr: '48px',
              color: theme.palette.greyscale.title,
            }}
          >
            <Box component="span" sx={{ fontWeight: 600 }}>
              Test #
              {allComparisonTests.findIndex(t => t.id === selectedTestId) + 1}:
            </Box>{' '}
            <Box component="span" sx={{ fontWeight: 400 }}>
              {selectedTest
                ? isMultiTurn
                  ? selectedTest.current.test_output?.test_configuration
                      ?.goal || 'No goal available'
                  : selectedTest.current.prompt_id &&
                      prompts[selectedTest.current.prompt_id]
                    ? prompts[selectedTest.current.prompt_id].content
                    : 'No prompt available'
                : ''}
            </Box>
          </Typography>
        </Box>

        <DialogContent
          sx={{ px: '37px', pt: '40px', pb: '30px', overflow: 'auto', flex: 1 }}
        >
          {selectedTest && (
            <Box>
              {isMultiTurn ? (
                /* Multi-turn: side-by-side ConversationHistory */
                <Grid
                  container
                  spacing={0}
                  sx={{ height: 'calc(90vh - 200px)' }}
                >
                  {/* Baseline Conversation Column */}
                  <Grid
                    sx={{
                      borderRight: { md: 1 },
                      borderColor: 'divider',
                    }}
                    size={{ xs: 12, md: 6 }}
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
                        <ExperimentRunLink
                          experimentId={baselineRun?.experiment_id}
                          parameterVersion={baselineRun?.parameter_version}
                          experimentName={baselineRun?.experiment_name}
                        />
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
                  <Grid size={{ xs: 12, md: 6 }}>
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
                        <ExperimentRunLink
                          experimentId={currentTestRun.experiment_id}
                          parameterVersion={currentTestRun.parameter_version}
                          experimentName={currentTestRun.experiment_name}
                        />
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
                /* Single-turn: Figma "Detail Test Compare Popup" layout */
                <Box
                  sx={{ display: 'flex', flexDirection: 'column', gap: '40px' }}
                >
                  {/* Row 1: Run headers with pass/fail badge */}
                  <Box sx={{ display: 'flex', gap: '40px' }}>
                    <Box
                      sx={{
                        flex: 1,
                        display: 'flex',
                        gap: '10px',
                        alignItems: 'center',
                      }}
                    >
                      <Typography
                        sx={{
                          fontSize: 23,
                          fontWeight: 700,
                          lineHeight: '27.6px',
                          color: theme.palette.greyscale.title,
                        }}
                      >
                        Baseline Run
                      </Typography>
                      {selectedTest.baseline ? (
                        <MetricStatusChip
                          passedCount={
                            Object.values(
                              selectedTest.baseline.test_metrics?.metrics || {}
                            ).filter(m => m.is_successful).length
                          }
                          totalCount={
                            Object.values(
                              selectedTest.baseline.test_metrics?.metrics || {}
                            ).length
                          }
                          size="small"
                          variant="filled"
                        />
                      ) : (
                        <Chip label="No data" size="small" />
                      )}
                    </Box>
                    <Box
                      sx={{
                        flex: 1,
                        display: 'flex',
                        gap: '10px',
                        alignItems: 'center',
                      }}
                    >
                      <Typography
                        sx={{
                          fontSize: 23,
                          fontWeight: 700,
                          lineHeight: '27.6px',
                          color: theme.palette.greyscale.title,
                        }}
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
                    </Box>
                  </Box>

                  {/* Row 2: Response boxes */}
                  <Box sx={{ display: 'flex', gap: '40px' }}>
                    <Box
                      sx={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '20px',
                      }}
                    >
                      <Typography
                        sx={{
                          fontWeight: 700,
                          fontSize: 16,
                          lineHeight: '24px',
                          color: theme.palette.greyscale.title,
                        }}
                      >
                        Response
                      </Typography>
                      <RunResponseBox
                        response={
                          selectedTest.baseline?.test_output?.output ||
                          'No response available'
                        }
                      />
                    </Box>
                    <Box
                      sx={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '20px',
                      }}
                    >
                      <Typography
                        sx={{
                          fontWeight: 700,
                          fontSize: 16,
                          lineHeight: '24px',
                          color: theme.palette.greyscale.title,
                        }}
                      >
                        Response
                      </Typography>
                      <RunResponseBox
                        response={
                          selectedTest.current.test_output?.output ||
                          'No response available'
                        }
                      />
                    </Box>
                  </Box>

                  {/* Row 3: Behavior sections — baseline left, current right */}
                  <Box
                    sx={{
                      display: 'flex',
                      gap: '40px',
                      alignItems: 'flex-start',
                    }}
                  >
                    {/* Baseline column */}
                    <Box
                      sx={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '40px',
                      }}
                    >
                      {behaviors.map(behavior => {
                        const bMetrics = behavior.metrics
                          .map(metric => ({
                            name: metric.name,
                            result:
                              selectedTest.baseline?.test_metrics?.metrics?.[
                                metric.name
                              ],
                          }))
                          .filter(
                            (m): m is { name: string; result: MetricResult } =>
                              m.result !== undefined
                          );
                        if (bMetrics.length === 0) return null;
                        const passed = bMetrics.filter(
                          m => m.result.is_successful
                        ).length;
                        return (
                          <BehaviorSection
                            key={behavior.id}
                            behaviorName={behavior.name}
                            passedCount={passed}
                            totalCount={bMetrics.length}
                          >
                            {bMetrics.map(m => (
                              <MetricRow
                                key={m.name}
                                metricName={m.name}
                                result={m.result}
                              />
                            ))}
                          </BehaviorSection>
                        );
                      })}
                    </Box>

                    {/* Current column */}
                    <Box
                      sx={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '40px',
                      }}
                    >
                      {behaviors.map(behavior => {
                        const bMetrics = behavior.metrics
                          .map(metric => ({
                            name: metric.name,
                            result:
                              selectedTest.current.test_metrics?.metrics?.[
                                metric.name
                              ],
                          }))
                          .filter(
                            (m): m is { name: string; result: MetricResult } =>
                              m.result !== undefined
                          );
                        if (bMetrics.length === 0) return null;
                        const passed = bMetrics.filter(
                          m => m.result.is_successful
                        ).length;
                        return (
                          <BehaviorSection
                            key={behavior.id}
                            behaviorName={behavior.name}
                            passedCount={passed}
                            totalCount={bMetrics.length}
                          >
                            {bMetrics.map(m => (
                              <MetricRow
                                key={m.name}
                                metricName={m.name}
                                result={m.result}
                              />
                            ))}
                          </BehaviorSection>
                        );
                      })}
                    </Box>
                  </Box>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
}
