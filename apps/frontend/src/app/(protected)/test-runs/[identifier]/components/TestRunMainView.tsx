'use client';

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { Box, Typography, TextField } from '@mui/material';
import { useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { testRunKeys } from '@/constants/query-keys';
import DetailTabNav from '@/components/common/DetailTabNav';
import {
  TestRunTitle,
  TestRunMetadata,
  TestRunActions,
} from './TestRunDetailHeader';
import { PageLayout } from '@/components/layout/PageLayout';
import TestRunConfigurationTab from './TestRunConfigurationTab';
import RunSummary from './summary/RunSummary';
import TestRunTags from './TestRunTags';
import TestRunLinkedEntitiesTab from './TestRunLinkedEntitiesTab';
import TestRunTracesTab from './TestRunTracesTab';
import RerunTestRunDrawer from '@/components/common/RerunTestRunDrawer';
import BaseDrawer from '@/components/common/BaseDrawer';
import { FilterState } from './TestRunFilterBar';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import {
  TestRunDetail,
  VerdictMatrix,
} from '@/utils/api-client/interfaces/test-run';
import type { TraceSummary } from '@/utils/api-client/interfaces/telemetry';
import { useNotifications } from '@/components/common/NotificationContext';
import { useViewingEntity } from '@/contexts/NotificationsContext';
import { NotificationSection } from '@/constants/notifications';
import { can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  resolveSingleCreatedRun,
  watchRunHref,
  type BatchRunOutcome,
} from '@/utils/test-run-batch';
import { useTestRunDetailData } from '../hooks/useTestRunDetailData';
import { useLiveTestRun } from '../hooks/useLiveTestRun';
import {
  getTestEvaluationSummary,
  getEffectiveTestResultStatus,
} from '@/utils/test-result-status';
import { TAB_KEYS, TabKey, tabIndexFromKey } from '../utils/tab-key';

const TAB_LABELS: Record<TabKey, string> = {
  summary: 'Summary',
  configuration: 'Configuration',
  linked_entities: 'Tests',
  traces: 'Traces',
};

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
  /** Drawer tab to open when deep-linking via selectedresult (e.g. "reviews"). */
  initialDetailTab?: string;
  /** Server-prefetched results (small runs only, only when the Tests tab is opening); see
   * `useTestRunDetailData`. */
  initialTestResults?: TestResultDetail[];
  /** Server-prefetched verdict grid, always fetched -- it's what the default Summary tab
   * renders; see `useTestRunLive`. */
  initialVerdictMatrix?: VerdictMatrix;
  /** Server-prefetched first page of this run's traces, only when the Traces tab is opening;
   * see `TestRunTracesTab`. */
  initialTraces?: TraceSummary[];
  initialTracesTotalCount?: number;
  /** Whether the test set for this run still exists (server-prefetched). `undefined` means the
   * check was skipped (no capability or no test set ID). */
  initialTestSetExists?: boolean;
  /** Whether other runs exist on the same test set (server-prefetched). */
  initialHasComparisonRuns?: boolean;
}

export default function TestRunMainView({
  testRunId,
  testRunData: _testRunData,
  testRun: initialTestRun,
  currentUserId,
  currentUserName,
  currentUserPicture,
  initialSelectedTestId,
  initialDetailTab,
  initialTestResults,
  initialVerdictMatrix,
  initialTraces,
  initialTracesTotalCount,
  initialTestSetExists,
  initialHasComparisonRuns = false,
}: TestRunMainViewProps) {
  const testRun = useLiveTestRun(testRunId, initialTestRun);
  // Already watching this run live on screen -- a completion notification
  // for it would be redundant noise, so mark it read on arrival instead of
  // badging/highlighting it (see useViewingEntity).
  useViewingEntity(NotificationSection.TEST_RUNS, testRunId);
  const notifications = useNotifications();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const preferLinkedEntities = Boolean(initialSelectedTestId);
  // Resolved once from the URL on load (so deep links like ?selectedresult=
  // or a legacy ?tab= alias land on the right tab). Later switches are local
  // state -- see handleTabChange -- so they don't force a server round trip.
  const [activeTab, setActiveTab] = useState(() =>
    tabIndexFromKey(
      searchParams.get('tab'),
      preferLinkedEntities && !searchParams.get('tab')
    )
  );

  // Fetch test results for the Tests tab.
  const needsTestResults = React.useRef(
    activeTab === TAB_KEYS.indexOf('linked_entities')
  );
  if (activeTab === TAB_KEYS.indexOf('linked_entities')) {
    needsTestResults.current = true;
  }

  const {
    testResults: loadedTestResults,
    prompts,
    requirements,
    availableMetrics,
    loading,
    error: loadError,
    refetch: refetchTestResults,
  } = useTestRunDetailData({
    testRunId,
    enabled: needsTestResults.current,
    initialTestResults,
  });

  const handleTabChange = useCallback((newValue: number) => {
    setActiveTab(newValue);
  }, []);

  const [isDownloading, setIsDownloading] = useState(false);
  const [isRerunDrawerOpen, setIsRerunDrawerOpen] = useState(false);
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const hasComparisonRuns = initialHasComparisonRuns;
  const testSetExists = initialTestSetExists ?? null;

  const [testResultUpdates, setTestResultUpdates] = useState<
    Map<string, TestResultDetail>
  >(new Map());

  const [filter, setFilter] = useState<FilterState>({
    searchQuery: '',
    statusFilter: 'all',
    selectedRequirements: [],
    overruleFilter: 'all',
    metricFilters: {},
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
      // Must use the same trusted outcome the row's own status chip renders.
      // Re-deriving it from raw metrics here made the filter disagree with
      // what the user could see: a test reviewed to Pass showed a "Passed"
      // chip but was excluded from the "passed" filter.
      filtered = filtered.filter(test => {
        const isPassed = getEffectiveTestResultStatus(test) === 'Pass';
        return filter.statusFilter === 'passed' ? isPassed : !isPassed;
      });
    }

    if (filter.selectedRequirements.length > 0) {
      filtered = filtered.filter(test => {
        const metrics = test.test_metrics?.metrics || {};
        return filter.selectedRequirements.some(requirementId => {
          const requirement = requirements.find(b => b.id === requirementId);
          if (!requirement) return false;
          return requirement.metrics.some(metric => metrics[metric.name]);
        });
      });
    }

    const activeMetricFilters = Object.entries(filter.metricFilters);
    if (activeMetricFilters.length > 0) {
      filtered = filtered.filter(test => {
        const metrics = test.test_metrics?.metrics || {};
        return activeMetricFilters.some(([metricName, outcome]) => {
          const metric = metrics[metricName];
          if (!metric) return false;
          if (outcome === 'evaluated') return true;
          return outcome === 'passed'
            ? metric.is_successful === true
            : metric.is_successful === false;
        });
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
  }, [testResults, filter, prompts, requirements]);

  const handleFilterChange = useCallback((newFilter: FilterState) => {
    setFilter(newFilter);
  }, []);

  const handleDrilldownToRequirement = useCallback(
    (requirementId: string) => {
      setFilter(prev => ({
        ...prev,
        selectedRequirements: [requirementId],
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
        metricFilters: { [metricName]: 'failed' },
        statusFilter: 'all',
      }));
      handleTabChange(TAB_KEYS.indexOf('linked_entities'));
    },
    [handleTabChange]
  );

  const handleDrilldownToFailures = useCallback(() => {
    setFilter(prev => ({
      ...prev,
      selectedRequirements: [],
      metricFilters: {},
      statusFilter: 'failed',
    }));
    handleTabChange(TAB_KEYS.indexOf('linked_entities'));
  }, [handleTabChange]);

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
    // A re-run creates a new test run, so drop the cached test-runs list pages
    // (kept fresh for 5 min otherwise) so it shows up immediately wherever
    // handleRerunExecuted lands us -- its own detail page normally, the list
    // as a fallback.
    void queryClient.invalidateQueries({ queryKey: testRunKeys.all() });
  }, [queryClient]);

  // Jump straight to the new run in Detail view so execution is visible as
  // it happens. executeTestSet only returns the test_configuration
  // synchronously -- the worker creates the run itself -- so this polls for
  // it the same way tag assignment already does. Falls back to the runs
  // list (the prior unconditional behaviour) if it doesn't show up in time.
  const handleRerunExecuted = useCallback(
    (outcome: BatchRunOutcome) => {
      void (async () => {
        const factory = new ApiClientFactory();
        const newRun = await resolveSingleCreatedRun(
          outcome,
          factory.getTestRunsClient()
        );
        router.push(newRun ? watchRunHref(newRun.id) : '/test-runs');
      })();
    },
    [router]
  );

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

  const canExecute = useCan(Capability.TestSet.EXECUTE);
  const canRerun =
    Boolean(testRun.test_configuration_id) &&
    canExecute &&
    testSetExists !== false;

  const rerunTooltip =
    testSetExists === false
      ? 'The test set for this run no longer exists'
      : !canExecute
        ? 'You do not have permission to re-run tests'
        : !testRun.test_configuration_id
          ? 'Cannot re-run: No test configuration found'
          : 'Re-run test';

  const title = testRun.name?.trim() || `Test Run ${testRunId}`;

  return (
    <PageLayout
      breadcrumbs={[
        { label: 'Test Runs', href: '/test-runs' },
        { label: title, href: `/test-runs/${testRunId}` },
      ]}
      title={
        <TestRunTitle
          testRun={testRun}
          onRename={handleRenameOpen}
          canRename={can(testRun, Capability.TestRun.UPDATE)}
        />
      }
      metadata={<TestRunMetadata testRun={testRun} />}
      actions={
        <TestRunActions
          testRun={testRun}
          onCompare={handleCompare}
          onDownload={handleDownload}
          onRerun={handleRerun}
          isDownloading={isDownloading}
          canRerun={canRerun}
          rerunTooltip={rerunTooltip}
          canCompare={hasComparisonRuns}
        />
      }
    >
      {loadError && (
        <Typography color="error" sx={{ mb: 2 }}>
          {loadError}
        </Typography>
      )}

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
        <RunSummary
          testRunId={testRunId}
          testRun={testRun}
          initialMatrix={initialVerdictMatrix}
          onViewRequirement={handleDrilldownToRequirement}
          onViewMetric={handleDrilldownToMetric}
          onViewFailures={handleDrilldownToFailures}
        />
        <Box sx={{ mt: 3 }}>
          <TestRunTags testRun={testRun} />
        </Box>
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <TestRunLinkedEntitiesTab
          filteredTests={filteredTests}
          filter={filter}
          onFilterChange={handleFilterChange}
          availableRequirements={requirements}
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
          requirements={requirements}
          onTestResultUpdate={handleTestResultUpdate}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
          initialSelectedTestId={initialSelectedTestId}
          initialDetailTab={initialDetailTab}
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
          initialTraces={initialTraces}
          initialTracesTotalCount={initialTracesTotalCount}
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
        onExecuted={handleRerunExecuted}
      />
    </PageLayout>
  );
}
