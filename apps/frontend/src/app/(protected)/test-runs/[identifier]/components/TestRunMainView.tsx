'use client';

import React, {
  useState,
  useMemo,
  useCallback,
  useEffect,
  useRef,
} from 'react';
import { Box, Typography, TextField } from '@mui/material';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { testRunKeys } from '@/constants/query-keys';
import DetailTabNav from '@/components/common/DetailTabNav';
import TestRunDetailHeader from './TestRunDetailHeader';
import TestRunConfigurationTab from './TestRunConfigurationTab';
import TestRunStatsTab from './TestRunStatsTab';
import TestRunLinkedEntitiesTab from './TestRunLinkedEntitiesTab';
import TestRunTracesTab from './TestRunTracesTab';
import RerunTestRunDrawer from '@/components/common/RerunTestRunDrawer';
import BaseDrawer from '@/components/common/BaseDrawer';
import { FilterState } from './TestRunFilterBar';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { useNotifications } from '@/components/common/NotificationContext';
import { can } from '@/utils/affordances';
import { Capability } from '@/constants/capabilities';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useTestRunDetailData } from '../hooks/useTestRunDetailData';
import { getTestEvaluationSummary } from '@/utils/test-result-status';

const TAB_KEYS = [
  'summary',
  'linked_entities',
  'configuration',
  'traces',
] as const;
type TabKey = (typeof TAB_KEYS)[number];

const TAB_LABELS: Record<TabKey, string> = {
  summary: 'Summary',
  configuration: 'Configuration',
  linked_entities: 'Test Cases',
  traces: 'Traces',
};

function tabIndexFromKey(
  key: string | null,
  preferLinkedEntities: boolean
): number {
  if (key === 'results') {
    return TAB_KEYS.indexOf('linked_entities');
  }
  if (key === 'stats') {
    return TAB_KEYS.indexOf('summary');
  }
  if (key === 'logs') {
    return TAB_KEYS.indexOf('traces');
  }
  const idx = TAB_KEYS.indexOf(key as TabKey);
  if (idx >= 0) return idx;
  return preferLinkedEntities ? TAB_KEYS.indexOf('linked_entities') : 0;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`test-run-tabpanel-${index}`}
      aria-labelledby={`test-run-tab-${index}`}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

interface TestRunMainViewProps {
  testRunId: string;
  testRunData: {
    id: string;
    name?: string;
    created_at: string;
    test_configuration_id?: string;
  };
  testRun: TestRunDetail;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
  initialSelectedTestId?: string;
}

export default function TestRunMainView({
  testRunId,
  testRunData: _testRunData,
  testRun,
  currentUserId,
  currentUserName,
  currentUserPicture,
  initialSelectedTestId,
}: TestRunMainViewProps) {
  const notifications = useNotifications();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const preferLinkedEntities = Boolean(initialSelectedTestId);
  const activeTab = tabIndexFromKey(
    searchParams.get('tab'),
    preferLinkedEntities && !searchParams.get('tab')
  );

  // Fetch test results for Summary (reviews/corrections) and Test Cases tabs.
  const needsTestResults = React.useRef(
    activeTab === TAB_KEYS.indexOf('linked_entities') ||
      activeTab === TAB_KEYS.indexOf('summary')
  );
  if (
    activeTab === TAB_KEYS.indexOf('linked_entities') ||
    activeTab === TAB_KEYS.indexOf('summary')
  ) {
    needsTestResults.current = true;
  }

  const {
    testResults: loadedTestResults,
    prompts,
    behaviors,
    availableMetrics,
    loading,
    error: loadError,
    refetch: refetchTestResults,
  } = useTestRunDetailData({
    testRunId,
    enabled: needsTestResults.current,
  });

  const handleTabChange = useCallback(
    (newValue: number) => {
      const key = TAB_KEYS[newValue];
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', key);
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  const [isDownloading, setIsDownloading] = useState(false);
  const [isRerunDrawerOpen, setIsRerunDrawerOpen] = useState(false);
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  // Whether another test run exists on the same test set to compare against.
  const [hasComparisonRuns, setHasComparisonRuns] = useState(false);
  const [testSetExists, setTestSetExists] = useState<boolean | null>(null);
  const [testSetCheckError, setTestSetCheckError] = useState(false);

  const [testResultUpdates, setTestResultUpdates] = useState<
    Map<string, TestResultDetail>
  >(new Map());

  const [filter, setFilter] = useState<FilterState>({
    searchQuery: '',
    statusFilter: 'all',
    selectedBehaviors: [],
    overruleFilter: 'all',
    selectedMetrics: [],
    commentFilter: 'all',
    commentCountRange: { min: 0, max: 20 },
    taskFilter: 'all',
    taskCountRange: { min: 0, max: 10 },
  });

  const testResults = useMemo(() => {
    if (testResultUpdates.size === 0) return loadedTestResults;
    return loadedTestResults.map(
      test => testResultUpdates.get(test.id) || test
    );
  }, [loadedTestResults, testResultUpdates]);

  const filteredTests = useMemo(() => {
    let filtered = [...testResults];

    if (filter.searchQuery) {
      const query = filter.searchQuery.toLowerCase();
      filtered = filtered.filter(test => {
        const promptContent = (
          (test.prompt_id && prompts[test.prompt_id]
            ? prompts[test.prompt_id].content
            : test.test?.prompt?.content) || ''
        ).toLowerCase();
        const goalContent =
          test.test_output?.test_configuration?.goal?.toLowerCase() || '';
        const evaluationContent = getTestEvaluationSummary(test).toLowerCase();
        return (
          promptContent.includes(query) ||
          goalContent.includes(query) ||
          evaluationContent.includes(query)
        );
      });
    }

    if (filter.statusFilter !== 'all') {
      filtered = filtered.filter(test => {
        const metrics = test.test_metrics?.metrics || {};
        const metricValues = Object.values(metrics);
        const totalMetrics = metricValues.length;
        const passedMetrics = metricValues.filter(m => m.is_successful).length;
        const isPassed = totalMetrics > 0 && passedMetrics === totalMetrics;
        return filter.statusFilter === 'passed' ? isPassed : !isPassed;
      });
    }

    if (filter.selectedBehaviors.length > 0) {
      filtered = filtered.filter(test => {
        const metrics = test.test_metrics?.metrics || {};
        return filter.selectedBehaviors.some(behaviorId => {
          const behavior = behaviors.find(b => b.id === behaviorId);
          if (!behavior) return false;
          return behavior.metrics.some(metric => metrics[metric.name]);
        });
      });
    }

    if (filter.selectedMetrics.length > 0) {
      filtered = filtered.filter(test => {
        const metrics = test.test_metrics?.metrics || {};
        return filter.selectedMetrics.some(metricName =>
          Object.hasOwn(metrics, metricName)
        );
      });
    }

    if (filter.overruleFilter !== 'all') {
      filtered = filtered.filter(test => {
        const hasReview = !!test.last_review;
        const hasConflict = !test.matches_review;
        if (filter.overruleFilter === 'overruled') return hasReview;
        if (filter.overruleFilter === 'original') return !hasReview;
        if (filter.overruleFilter === 'conflicting')
          return hasReview && hasConflict;
        return true;
      });
    }

    if (filter.commentFilter !== 'all') {
      filtered = filtered.filter(test => {
        const commentCount = test.counts?.comments || 0;
        if (filter.commentFilter === 'with_comments') return commentCount > 0;
        if (filter.commentFilter === 'without_comments')
          return commentCount === 0;
        if (filter.commentFilter === 'range') {
          return (
            commentCount >= filter.commentCountRange.min &&
            commentCount <= filter.commentCountRange.max
          );
        }
        return true;
      });
    }

    if (filter.taskFilter !== 'all') {
      filtered = filtered.filter(test => {
        const taskCount = test.counts?.tasks || 0;
        if (filter.taskFilter === 'with_tasks') return taskCount > 0;
        if (filter.taskFilter === 'without_tasks') return taskCount === 0;
        if (filter.taskFilter === 'range') {
          return (
            taskCount >= filter.taskCountRange.min &&
            taskCount <= filter.taskCountRange.max
          );
        }
        return true;
      });
    }

    return filtered;
  }, [testResults, filter, prompts, behaviors]);

  const handleFilterChange = useCallback((newFilter: FilterState) => {
    setFilter(newFilter);
  }, []);

  const handleDrilldownToBehavior = useCallback(
    (behaviorId: string) => {
      setFilter(prev => ({
        ...prev,
        selectedBehaviors: [behaviorId],
        statusFilter: 'failed',
      }));
      handleTabChange(TAB_KEYS.indexOf('linked_entities'));
    },
    [handleTabChange]
  );

  const handleDrilldownToMetric = useCallback(
    (metricName: string) => {
      setFilter(prev => ({
        ...prev,
        selectedMetrics: [metricName],
        statusFilter: 'failed',
      }));
      handleTabChange(TAB_KEYS.indexOf('linked_entities'));
    },
    [handleTabChange]
  );

  const handleTestResultUpdate = useCallback(
    (updatedTest: TestResultDetail) => {
      setTestResultUpdates(prev => {
        const newMap = new Map(prev);
        newMap.set(updatedTest.id, updatedTest);
        return newMap;
      });
      void refetchTestResults();
      void queryClient.invalidateQueries({
        queryKey: [...testRunKeys.all(), 'list'],
      });
    },
    [refetchTestResults, queryClient]
  );

  const previousTabRef = useRef(activeTab);

  useEffect(() => {
    const summaryTabIndex = TAB_KEYS.indexOf('summary');
    const switchedToSummary =
      activeTab === summaryTabIndex &&
      previousTabRef.current !== summaryTabIndex;
    previousTabRef.current = activeTab;

    if (switchedToSummary) {
      void refetchTestResults();
    }
  }, [activeTab, refetchTestResults]);

  const handleDownload = useCallback(async () => {
    setIsDownloading(true);
    try {
      const testRunsClient = new ApiClientFactory().getTestRunsClient();
      const blob = await testRunsClient.downloadTestRun(testRunId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `test_run_${testRunId}_results.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      notifications.show('Test run results downloaded successfully', {
        severity: 'success',
      });
    } catch {
      notifications.show('Failed to download test run results', {
        severity: 'error',
      });
    } finally {
      setIsDownloading(false);
    }
  }, [testRunId, notifications]);

  const handleRerun = useCallback(() => {
    if (testSetExists === false) {
      return;
    }
    if (!testRun.test_configuration_id) {
      notifications.show('Cannot re-run: No test configuration found', {
        severity: 'error',
      });
      return;
    }
    const testSet = testRun.test_configuration?.test_set;
    const endpoint = testRun.test_configuration?.endpoint;
    if (!testSet?.id || !endpoint?.id) {
      notifications.show('Cannot re-run: Missing test set or endpoint data', {
        severity: 'error',
      });
      return;
    }
    setIsRerunDrawerOpen(true);
  }, [testRun, notifications, testSetExists]);

  const testSetId = testRun.test_configuration?.test_set?.id;

  useEffect(() => {
    if (!testSetId) {
      setTestSetExists(false);
      setTestSetCheckError(false);
      return;
    }
    let cancelled = false;
    setTestSetCheckError(false);
    (async () => {
      try {
        await new ApiClientFactory().getTestSetsClient().getTestSet(testSetId);
        if (!cancelled) {
          setTestSetExists(true);
          setTestSetCheckError(false);
        }
      } catch (err: unknown) {
        if (cancelled) return;
        const status = (err as { status?: number })?.status;
        if (status === 404 || status === 410) {
          setTestSetExists(false);
          setTestSetCheckError(false);
        } else {
          setTestSetExists(null);
          setTestSetCheckError(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [testSetId]);

  useEffect(() => {
    if (!testSetId) {
      setHasComparisonRuns(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const testRunsClient = new ApiClientFactory().getTestRunsClient();
        const response = await testRunsClient.getTestRuns({
          limit: 2,
          skip: 0,
          sort_by: 'created_at',
          sort_order: 'desc',
          filter: `test_configuration/test_set/id eq '${testSetId}'`,
        });
        if (!cancelled) {
          const others = response.data.filter(run => run.id !== testRunId);
          setHasComparisonRuns(others.length > 0);
        }
      } catch {
        if (!cancelled) setHasComparisonRuns(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [testSetId, testRunId]);

  const handleCompare = useCallback(() => {
    window.open(
      `/test-runs/${testRunId}/compare`,
      '_blank',
      'noopener,noreferrer'
    );
  }, [testRunId]);

  const handleRenameOpen = useCallback(() => {
    setRenameValue(testRun.name || '');
    setRenameDialogOpen(true);
  }, [testRun.name]);

  const handleRenameClose = useCallback(() => {
    setRenameDialogOpen(false);
  }, []);

  const handleRenameSubmit = useCallback(async () => {
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === testRun.name) {
      setRenameDialogOpen(false);
      return;
    }
    try {
      const testRunsClient = new ApiClientFactory().getTestRunsClient();
      await testRunsClient.updateTestRun(testRunId, { name: trimmed });
      notifications.show('Test run renamed successfully', {
        severity: 'success',
      });
      setRenameDialogOpen(false);
      router.refresh();
    } catch {
      notifications.show('Failed to rename test run', {
        severity: 'error',
      });
    }
  }, [renameValue, testRun.name, testRunId, notifications, router]);

  const handleRerunSuccess = useCallback(() => {
    router.push('/test-runs');
  }, [router]);

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (initialSelectedTestId && (!tab || tab === 'results')) {
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', 'linked_entities');
      router.replace(`?${params.toString()}`, { scroll: false });
    }
  }, [initialSelectedTestId, router, searchParams]);

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label: TAB_LABELS[key],
    id: `test-run-tab-${index}`,
    'aria-controls': `test-run-tabpanel-${index}`,
  }));

  const canCreateRerun = can(testRun, Capability.TestRun.CREATE);
  const canRerun =
    Boolean(testRun.test_configuration_id) &&
    canCreateRerun &&
    testSetExists !== false;

  const rerunTooltip =
    testSetExists === false
      ? 'The test set for this run no longer exists'
      : !canCreateRerun
        ? 'You do not have permission to re-run tests'
        : !testRun.test_configuration_id
          ? 'Cannot re-run: No test configuration found'
          : testSetCheckError
            ? "Couldn't verify test set availability"
            : testSetExists === null
              ? 'Checking test set…'
              : 'Re-run test';

  return (
    <Box>
      {loadError && (
        <Typography color="error" sx={{ mb: 2 }}>
          {loadError}
        </Typography>
      )}

      <TestRunDetailHeader
        testRun={testRun}
        onRename={handleRenameOpen}
        onCompare={handleCompare}
        onDownload={handleDownload}
        onRerun={handleRerun}
        isDownloading={isDownloading}
        canRerun={canRerun}
        rerunTooltip={rerunTooltip}
        canCompare={hasComparisonRuns}
        canRename={can(testRun, Capability.TestRun.UPDATE)}
      />

      <BaseDrawer
        open={renameDialogOpen}
        onClose={handleRenameClose}
        title="Rename Test Run"
        onSave={() => void handleRenameSubmit()}
        saveDisabled={
          !renameValue.trim() || renameValue.trim() === testRun.name
        }
        saveButtonText="Save"
      >
        <TextField
          autoFocus
          fullWidth
          label="Name"
          value={renameValue}
          onChange={e => setRenameValue(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              void handleRenameSubmit();
            }
          }}
          sx={{ flexShrink: 0 }}
        />
      </BaseDrawer>

      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Test run detail tabs"
      />

      <TabPanel value={activeTab} index={0}>
        <TestRunStatsTab
          testRun={testRun}
          testRunId={testRunId}
          testResults={testResults}
          loading={loading}
          onRefresh={() => router.refresh()}
          behaviors={behaviors}
          onViewBehavior={handleDrilldownToBehavior}
          onViewMetric={handleDrilldownToMetric}
        />
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <TestRunLinkedEntitiesTab
          filteredTests={filteredTests}
          filter={filter}
          onFilterChange={handleFilterChange}
          availableBehaviors={behaviors}
          availableMetrics={availableMetrics}
          isDownloading={isDownloading}
          onDownload={handleDownload}
          onCompare={handleCompare}
          canCompare={hasComparisonRuns}
          onRerun={handleRerun}
          isRerunning={isRerunDrawerOpen}
          canRerun={canRerun}
          totalTests={testResults.length}
          testRunId={testRunId}
          loading={loading}
          prompts={prompts}
          behaviors={behaviors}
          onTestResultUpdate={handleTestResultUpdate}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
          initialSelectedTestId={initialSelectedTestId}
          testSetType={
            testRun.test_configuration?.test_set?.test_set_type?.type_value
          }
          project={testRun.test_configuration?.endpoint?.project}
          projectName={testRun.test_configuration?.endpoint?.project?.name}
          metricsSource={testRun.test_configuration?.attributes?.metrics_source}
        />
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        <TestRunConfigurationTab testRun={testRun} />
      </TabPanel>

      <TabPanel value={activeTab} index={3}>
        <TestRunTracesTab
          testRunId={testRunId}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
        />
      </TabPanel>

      <RerunTestRunDrawer
        open={isRerunDrawerOpen}
        onClose={() => setIsRerunDrawerOpen(false)}
        data={{
          testSetId: testRun.test_configuration?.test_set?.id || '',
          testSetName: testRun.test_configuration?.test_set?.name || 'Unknown',
          testSetType:
            testRun.test_configuration?.test_set?.test_set_type?.type_value,
          endpointId: testRun.test_configuration?.endpoint?.id || '',
          endpointName: testRun.test_configuration?.endpoint?.name || 'Unknown',
          projectId: testRun.test_configuration?.endpoint?.project?.id,
          projectName:
            testRun.test_configuration?.endpoint?.project?.name || 'Unknown',
          testRunId: testRun.id,
          originalAttributes: testRun.test_configuration?.attributes,
        }}
        onSuccess={handleRerunSuccess}
      />
    </Box>
  );
}
