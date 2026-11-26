'use client';

import React, {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useRef,
} from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useSession } from 'next-auth/react';
import BaseDrawer from '@/components/common/BaseDrawer';
import BaseTag from '@/components/common/BaseTag';
import {
  drawerOutlinedFieldSx,
  drawerTagFieldSx,
} from '@/components/common/drawerFormFieldSx';
import ModelSelector from '@/components/common/ModelSelector';
import { PreflightDialog } from '@/components/common/PreflightDialog';
import SelectExperimentsDrawer from '@/components/common/SelectExperimentsDrawer';
import type { MetricScope } from '@/utils/api-client/interfaces/metric';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { safeRandomUUID } from '@/utils/uuid';
import { useEndpoints } from '@/hooks/useEndpoints';
import type {
  TestSetMetric,
  LastTestRunSummary,
  TestSet,
} from '@/utils/api-client/interfaces/test-set';
import type { ExperimentDetail } from '@/utils/api-client/interfaces/parameters';
import { useNotifications } from '@/components/common/NotificationContext';
import { getApiErrorMessage } from '@/utils/error-utils';
import { getApiErrorStatus } from '@/utils/api-client/is-not-found-error';
import {
  executeBatchedTestRuns,
  assignTagsToRuns,
  type BatchRunOutcome,
  type SelectedExperiment,
} from '@/utils/test-run-batch';
import tagStyles from '@/styles/BaseTag.module.css';
import type { UUID } from 'crypto';
import { readActiveProjectId } from '@/utils/active-project';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { QuotaResource } from '@/constants/quota';
import { useQuotaErrorHandler, useQuotaGate } from '@/hooks/useQuotaGate';
import { useRunTestCount } from '@/hooks/useRunTestCount';
import { Capability } from '@/constants/capabilities';
import { useCan } from '@/components/common/Can';
import RunDrawerSection from '@/components/common/run-drawer/RunDrawerSection';
import WhenField from '@/components/common/run-drawer/WhenField';
import {
  EndpointField,
  FixedField,
  TestSetField,
  type EndpointOption,
} from '@/components/common/run-drawer/TargetFields';
import {
  ExperimentPicker,
  ExperimentVersionPicker,
} from '@/components/common/run-drawer/ExperimentFields';
import {
  MetricsField,
  ScoringTargetField,
} from '@/components/common/run-drawer/ScoringFields';
import {
  ExecutionModeField,
  PreflightField,
} from '@/components/common/run-drawer/OptionFields';
import {
  EXECUTION_MODE,
  METRIC_MODE,
  RUN_WHEN,
  RUN_WHEN_LABEL,
  SCORING_TARGET,
  type MetricMode,
  type RunWhen,
  type ScoringTarget,
  type SelectedMetric,
} from '@/components/common/run-drawer/run-drawer-types';
import {
  changedFields,
  defaultScheduleForm,
  formatRunTime,
  fromSchedule,
  toScheduleSpec,
  type ScheduleForm,
} from '@/components/common/run-drawer/schedule-form';
import type {
  TestRunScheduleDetail,
  TestRunScheduleUpdate,
} from '@/utils/api-client/interfaces/test-run-schedule';
import { useQueryClient } from '@tanstack/react-query';
import { scheduleKeys } from '@/constants/query-keys';

// ---------------------------------------------------------------------------
// Rerun config (mirrors the old RerunTestRunDrawer's props)
// ---------------------------------------------------------------------------

interface OriginalMetric {
  id: string;
  name: string;
  scope?: string[];
}

export interface RerunConfig {
  testSetId: string;
  testSetName: string;
  testSetType?: string;
  endpointId: string;
  endpointName: string;
  projectId?: string;
  projectName: string;
  testRunId: string;
  originalAttributes?: {
    metrics?: OriginalMetric[];
    parameters_ref?: {
      experiment_id?: string;
      version?: string;
      label?: string;
    };
    [key: string]: unknown;
  };
}

// ---------------------------------------------------------------------------
// Mode-specific data discriminated union
// ---------------------------------------------------------------------------

type RunDrawerModeProps =
  | {
      mode: 'executeTestSet';
      data: {
        testSetId: string;
        /** Edit this schedule's settings instead of starting or scheduling a run. */
        schedule?: TestRunScheduleDetail;
      };
    }
  | { mode: 'newTestRun'; data?: undefined }
  | {
      mode: 'runExperiment';
      data: {
        experiment: ExperimentDetail;
        /** Optional pre-seed: hashes selected in the Versions grid. When omitted the latest version is preselected inside the drawer. */
        initialVersionHashes?: Set<string>;
      };
    }
  | { mode: 'rerunTestRun'; data: RerunConfig }
  | { mode: 'createFromGrid'; data: { selectedTestSetIds: string[] } };

type RunDrawerProps = {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  /** Fired synchronously with the raw execution outcome, before onSuccess/
   *  onClose -- callers that need to redirect to the run this created (e.g.
   *  resolving its id via pollForTestRun) hook in here rather than every
   *  mode picking up router logic that most callers don't want. */
  onExecuted?: (outcome: BatchRunOutcome) => void;
  /** Open with "When" set to a schedule instead of "Now". */
  initialSchedule?: boolean;
  /** Schedule fields to start from, e.g. carried over from the compact create drawer. */
  scheduleSeed?: ScheduleForm;
  /** Endpoint to preselect, e.g. carried over from the compact create drawer. */
  endpointSeed?: string;
} & RunDrawerModeProps;

// ---------------------------------------------------------------------------
// Per-mode static config
// ---------------------------------------------------------------------------

interface ModeConfig {
  title: string;
  saveButtonText: string;
  /** Endpoints load and the active project filters them. */
  projectEditable: boolean;
  endpointEditable: boolean;
  /** `fixed`: the caller chose the test set(s); `single`: pick one here. */
  testSetMode: 'fixed' | 'single';
  experimentsEditable: boolean;
}

const MODE_CONFIGS: Record<RunDrawerProps['mode'], ModeConfig> = {
  executeTestSet: {
    title: 'Execute Test Set',
    saveButtonText: 'Execute Test Set',
    projectEditable: true,
    endpointEditable: true,
    testSetMode: 'fixed',
    experimentsEditable: true,
  },
  newTestRun: {
    title: 'Test Run Configuration',
    saveButtonText: 'Execute Now',
    projectEditable: true,
    endpointEditable: true,
    testSetMode: 'single',
    experimentsEditable: true,
  },
  runExperiment: {
    title: 'Run Experiment',
    saveButtonText: 'Run Experiment',
    projectEditable: false,
    endpointEditable: true,
    testSetMode: 'single',
    experimentsEditable: false,
  },
  rerunTestRun: {
    title: 'Re-run Tests',
    saveButtonText: 'Re-run Tests',
    projectEditable: false,
    endpointEditable: false,
    testSetMode: 'fixed',
    experimentsEditable: true,
  },
  createFromGrid: {
    title: 'Execute Test Sets',
    saveButtonText: 'Run Test Sets',
    projectEditable: true,
    endpointEditable: true,
    testSetMode: 'fixed',
    experimentsEditable: true,
  },
};

/** Modes that can schedule; re-run and experiment runs stay "now" only. */
const SCHEDULABLE_MODES = new Set<RunDrawerProps['mode']>([
  'executeTestSet',
  'newTestRun',
  'createFromGrid',
]);

const METRIC_MODE_SUMMARY: Record<MetricMode, string> = {
  [METRIC_MODE.TEST_SET]: 'Test set metrics',
  [METRIC_MODE.REQUIREMENT]: 'Requirement metrics',
  [METRIC_MODE.CUSTOM]: 'Custom metrics',
};

/** Shown in "What to run" when the fixed test set's name can't be loaded. */
const UNKNOWN_TEST_SET_NAME = 'Selected test set';

const plural = (count: number, word: string) =>
  `${count} ${word}${count === 1 ? '' : 's'}`;

/** Joins the parts of a section's one-line summary, skipping empty ones. */
const summaryOf = (...parts: (string | false | null | undefined)[]) =>
  parts.filter(Boolean).join(' · ');

const whenFor = (form: ScheduleForm): RunWhen =>
  form.repeat ? RUN_WHEN.REPEAT : RUN_WHEN.ONCE;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RunDrawer(props: RunDrawerProps) {
  const { open, onClose, onSuccess, onExecuted, mode } = props;
  const cfg = MODE_CONFIGS[mode];
  const notifications = useNotifications();
  const { status } = useSession();

  // ---- Core state ----
  const [executing, setExecuting] = useState(false);
  // Bumped by the reset on open, so sections mount with that opening's state.
  const [session, setSession] = useState(0);
  const [error, setError] = useState<React.ReactNode>();

  // The reactive 402 path; the preflight gate sits below, once the drawer
  // knows which test sets and experiments a click would run.
  const asQuotaError = useQuotaErrorHandler();

  // ---- Endpoint ----
  const { data: rawEndpoints, isLoading: endpointsLoading } = useEndpoints(
    { sort_by: 'name', sort_order: 'asc', limit: 100 },
    open && (cfg.projectEditable || mode === 'runExperiment')
  );
  const endpoints = useMemo<EndpointOption[]>(
    () =>
      (rawEndpoints ?? [])
        .filter(e => e.id && e.name && e.name.trim() !== '')
        .map(e => ({
          id: e.id as UUID,
          name: e.name,
          environment: e.environment,
          project_id: e.project_id,
          organization_id: e.organization_id,
          connection_type: e.connection_type,
        })),
    [rawEndpoints]
  );
  const [filteredEndpoints, setFilteredEndpoints] = useState<EndpointOption[]>(
    []
  );
  const [selectedProject, setSelectedProject] = useState<UUID | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<UUID | null>(null);

  // ---- Test set (single-select for newTestRun / runExperiment) ----
  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [selectedTestSet, setSelectedTestSet] = useState<TestSet | null>(null);

  // ---- Test set info (for metrics/multi-turn) ----
  const [testSetName, setTestSetName] = useState<string | null>(null);
  const [testSetType, setTestSetType] = useState<string | null>(null);
  const [testSetMetrics, setTestSetMetrics] = useState<TestSetMetric[]>([]);

  // ---- Execution mode ----
  const [executionMode, setExecutionMode] = useState<string>(
    EXECUTION_MODE.PARALLEL
  );

  // ---- When: now, or a schedule ----
  const canSchedule =
    useCan(Capability.TestRun.EXECUTE) && SCHEDULABLE_MODES.has(mode);
  const [when, setWhen] = useState<RunWhen>(RUN_WHEN.NOW);
  const scheduleMode = when !== RUN_WHEN.NOW;
  const [scheduleForm, setScheduleForm] = useState<ScheduleForm>(() =>
    defaultScheduleForm()
  );
  const [schedulePreviewError, setSchedulePreviewError] = useState<
    string | null
  >(null);
  useEffect(() => {
    if (!open) return;
    const editing = mode === 'executeTestSet' ? props.data.schedule : null;
    const form = editing
      ? fromSchedule(editing)
      : (props.scheduleSeed ?? defaultScheduleForm());
    setScheduleForm(form);
    setWhen(
      editing || (props.initialSchedule && canSchedule)
        ? whenFor(form)
        : RUN_WHEN.NOW
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset only when the drawer opens
  }, [open]);

  const [reuseDropped, setReuseDropped] = useState(false);

  // ---- Scoring target ----
  const [scoringTarget, setScoringTarget] = useState<ScoringTarget>(
    SCORING_TARGET.FRESH
  );
  const [lastTestRun, setLastTestRun] = useState<LastTestRunSummary | null>(
    null
  );

  // ---- Metrics ----
  const [metricMode, setMetricMode] = useState<MetricMode>(
    METRIC_MODE.REQUIREMENT
  );
  const [selectedMetrics, setSelectedMetrics] = useState<SelectedMetric[]>([]);

  // ---- Models ----
  const [selectedExecutionModelId, setSelectedExecutionModelId] = useState('');
  const [selectedEvaluationModelId, setSelectedEvaluationModelId] =
    useState('');

  // ---- Experiments ----
  const [selectedExperiments, setSelectedExperiments] = useState<
    SelectedExperiment[]
  >([]);
  const [experimentsDrawerOpen, setExperimentsDrawerOpen] = useState(false);

  // ---- runExperiment internal version selection ----
  const [internalVersionHashes, setInternalVersionHashes] = useState<
    Set<string>
  >(new Set());

  // ---- Tags ----
  const [tags, setTags] = useState<string[]>([]);

  // ---- Preflight ----
  const [preflightEnabled, setPreflightEnabled] = useState(true);
  const [preflightDialogOpen, setPreflightDialogOpen] = useState(false);
  const [preflightCorrelationId, setPreflightCorrelationId] = useState('');
  const [preflightChecks, setPreflightChecks] = useState<
    Array<{
      check_id: string;
      label: string;
      applicable: boolean;
      test_set_id?: string;
      test_set_name?: string;
      composite_key?: string;
    }>
  >([]);

  const apiFactory = useMemo(() => new ApiClientFactory(), []);
  const queryClient = useQueryClient();

  // -----------------------------------------------------------------------
  // Derived helpers
  // -----------------------------------------------------------------------

  const rerunConfig = mode === 'rerunTestRun' ? props.data : null;
  const experimentData = mode === 'runExperiment' ? props.data : null;
  const executeTestSetId =
    mode === 'executeTestSet' ? props.data.testSetId : null;
  const editingSchedule =
    mode === 'executeTestSet' ? (props.data.schedule ?? null) : null;
  const gridTestSetIds =
    mode === 'createFromGrid' ? props.data.selectedTestSetIds : null;

  const effectiveProjectId = useMemo(() => {
    if (rerunConfig?.projectId) return rerunConfig.projectId as UUID;
    if (experimentData?.experiment.project_id)
      return experimentData.experiment.project_id as UUID;
    return selectedProject;
  }, [rerunConfig, experimentData, selectedProject]);

  // -----------------------------------------------------------------------
  // Reset state on open
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!open) return;
    setSession(prev => prev + 1);
    setError(undefined);
    setExecuting(false);
    setTestSetName(null);
    setReuseDropped(false);
    setTags([]);
    setExecutionMode(EXECUTION_MODE.PARALLEL);
    setScoringTarget(SCORING_TARGET.FRESH);
    setLastTestRun(null);
    setSelectedMetrics([]);
    setMetricMode(METRIC_MODE.REQUIREMENT);
    setSelectedExecutionModelId('');
    setSelectedEvaluationModelId('');
    setSelectedExperiments([]);
    setSelectedTestSet(null);
    setPreflightEnabled(true);
    setPreflightDialogOpen(false);
    setPreflightCorrelationId('');
    setPreflightChecks([]);

    if (cfg.projectEditable) {
      // The session's active project filters the endpoints.
      const activeId = readActiveProjectId();
      setSelectedProject(activeId ? (activeId as UUID) : null);
      setSelectedEndpoint(null);
    } else if (experimentData) {
      setSelectedProject(experimentData.experiment.project_id as UUID);
      setSelectedEndpoint(null);
      // Initialise internal version selection: use pre-seed from grid checkboxes,
      // falling back to the latest version if none are provided.
      const preseed = experimentData.initialVersionHashes;
      if (preseed && preseed.size > 0) {
        setInternalVersionHashes(new Set(preseed));
      } else {
        const versions = experimentData.experiment.versions;
        const latest = versions[versions.length - 1];
        setInternalVersionHashes(
          latest ? new Set([latest.version]) : new Set()
        );
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // `runExperiment` mode filters endpoints to the experiment's project as
  // soon as the shared endpoints list resolves (the general
  // "filter endpoints when project changes" effect below skips this mode).
  useEffect(() => {
    if (mode !== 'runExperiment' || !experimentData) return;
    setFilteredEndpoints(
      endpoints.filter(
        e => e.project_id === experimentData.experiment.project_id
      )
    );
  }, [mode, experimentData, endpoints]);

  // -----------------------------------------------------------------------
  // Load test sets (newTestRun & runExperiment modes)
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!open || !isAuthenticated(status)) return;
    if (cfg.testSetMode !== 'single') return;
    let mounted = true;
    const load = async () => {
      try {
        const res = await apiFactory
          .getTestSetsClient()
          .getTestSets({ limit: 100 });
        if (mounted) setTestSets(Array.isArray(res?.data) ? res.data : []);
      } catch {
        if (mounted) setTestSets([]);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [open, status, cfg.testSetMode, apiFactory]);

  // -----------------------------------------------------------------------
  // Test set info + metrics (executeTestSet & rerunTestRun)
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!open) return;
    const testSetId = executeTestSetId ?? rerunConfig?.testSetId ?? null;
    if (!testSetId) return;

    let mounted = true;
    const load = async () => {
      try {
        const client = apiFactory.getTestSetsClient();
        const testSet = await client.getTestSet(testSetId);
        if (!mounted) return;
        setTestSetName(testSet?.name ?? null);
        setTestSetType(testSet?.test_set_type?.type_value || null);

        const metrics = await client.getTestSetMetrics(testSetId);
        if (!mounted) return;
        setTestSetMetrics(metrics || []);

        if (mode === 'executeTestSet' && !editingSchedule) {
          setMetricMode(
            metrics?.length > 0 ? METRIC_MODE.TEST_SET : METRIC_MODE.REQUIREMENT
          );
        }
      } catch {
        if (mounted) {
          setTestSetName(UNKNOWN_TEST_SET_NAME);
          setTestSetType(null);
          setTestSetMetrics([]);
          setMetricMode(METRIC_MODE.REQUIREMENT);
        }
      }
    };
    load();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- editingSchedule is fixed while open
  }, [open, executeTestSetId, rerunConfig?.testSetId, mode, apiFactory]);

  // One set picked in the test sets list: name it in "What to run".
  const singleGridTestSetId =
    gridTestSetIds && gridTestSetIds.length === 1 ? gridTestSetIds[0] : null;
  useEffect(() => {
    if (!open || !singleGridTestSetId) return;
    let mounted = true;
    apiFactory
      .getTestSetsClient()
      .getTestSet(singleGridTestSetId)
      .then(testSet => {
        if (mounted) setTestSetName(testSet?.name ?? null);
      })
      .catch(() => {
        if (mounted) setTestSetName(UNKNOWN_TEST_SET_NAME);
      });
    return () => {
      mounted = false;
    };
  }, [open, singleGridTestSetId, apiFactory]);

  // Editing a schedule: start from what its runs use now.
  useEffect(() => {
    if (!open || !editingSchedule) return;
    const settings = editingSchedule.run_settings;
    setExecutionMode(settings.execution_mode ?? EXECUTION_MODE.PARALLEL);
    setSelectedExecutionModelId(settings.execution_model_id ?? '');
    setSelectedEvaluationModelId(settings.evaluation_model_id ?? '');
    if (
      settings.metrics_source === 'execution_time' &&
      settings.metrics.length > 0
    ) {
      setMetricMode(METRIC_MODE.CUSTOM);
      setSelectedMetrics(
        settings.metrics.map(m => ({ id: m.id as UUID, name: m.name }))
      );
    } else {
      setMetricMode(
        settings.metrics_source === 'test_set'
          ? METRIC_MODE.TEST_SET
          : METRIC_MODE.REQUIREMENT
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fill once per open
  }, [open]);

  // Pick the schedule's endpoint once the endpoint list has it.
  const endpointSeeded = useRef(false);
  useEffect(() => {
    if (!open) {
      endpointSeeded.current = false;
      return;
    }
    const id = editingSchedule?.endpoint?.id ?? props.endpointSeed;
    if (!id || endpointSeeded.current) return;
    if (filteredEndpoints.some(e => e.id === id)) {
      endpointSeeded.current = true;
      setSelectedEndpoint(id as UUID);
    }
  }, [open, editingSchedule, filteredEndpoints, props.endpointSeed]);

  // Rerun: pre-fill metrics from original attributes. Models are NOT
  // carried forward so the rerun picks up the user's current defaults
  // instead of the model that happened to be active on the original run.
  useEffect(() => {
    if (!open || mode !== 'rerunTestRun' || !rerunConfig) return;
    const origMetrics = rerunConfig.originalAttributes?.metrics;
    if (origMetrics && origMetrics.length > 0) {
      setMetricMode(METRIC_MODE.CUSTOM);
      setSelectedMetrics(
        origMetrics.map(m => ({
          id: m.id as UUID,
          name: m.name,
          scope: m.scope,
        }))
      );
    }
    setSelectedExecutionModelId('');
    setSelectedEvaluationModelId('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode]);

  // Rerun: pre-fill experiment from original run
  useEffect(() => {
    if (!open || mode !== 'rerunTestRun') return;
    const origRef = rerunConfig?.originalAttributes?.parameters_ref;
    const origExpId = origRef?.experiment_id;
    if (!origExpId) {
      setSelectedExperiments([]);
      return;
    }

    let cancelled = false;
    const load = async () => {
      try {
        const exp = await apiFactory
          .getParametersClient()
          .getExperiment(origExpId);
        if (cancelled) return;
        const version = origRef?.version || exp.latest_version;
        if (!version) {
          setSelectedExperiments([]);
          return;
        }
        setSelectedExperiments([
          {
            experiment_id: exp.id,
            experiment_name: exp.name,
            version,
          },
        ]);
      } catch {
        if (!cancelled) setSelectedExperiments([]);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode]);

  // -----------------------------------------------------------------------
  // Filter endpoints when project changes
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (mode === 'runExperiment' || mode === 'rerunTestRun') return;
    // When a project is selected filter to its endpoints; otherwise show all
    const filtered = selectedProject
      ? endpoints.filter(e => e.project_id === selectedProject)
      : endpoints;
    setFilteredEndpoints(filtered);
    // Clear endpoint selection if it no longer appears in the filtered list
    setSelectedEndpoint(prev =>
      prev && filtered.some(e => e.id === prev) ? prev : null
    );
  }, [selectedProject, endpoints, mode]);

  // Clear experiments on project switch (project-scoped)
  useEffect(() => {
    if (cfg.experimentsEditable) setSelectedExperiments([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProject]);

  // -----------------------------------------------------------------------
  // Scoring target: fetch last test run (executeTestSet)
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (
      mode !== 'executeTestSet' ||
      !executeTestSetId ||
      !selectedEndpoint ||
      !open
    ) {
      if (mode === 'executeTestSet') {
        setLastTestRun(null);
        setScoringTarget(SCORING_TARGET.FRESH);
      }
      return;
    }
    let mounted = true;
    const load = async () => {
      try {
        const result = await apiFactory
          .getTestSetsClient()
          .getLastTestRun(executeTestSetId, selectedEndpoint);
        if (mounted) {
          setLastTestRun(result);
          setScoringTarget(SCORING_TARGET.FRESH);
        }
      } catch {
        if (mounted) {
          setLastTestRun(null);
          setScoringTarget(SCORING_TARGET.FRESH);
        }
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [mode, selectedEndpoint, executeTestSetId, open, apiFactory]);

  // -----------------------------------------------------------------------
  // Field handlers
  // -----------------------------------------------------------------------

  const handleMetricModeChange = (next: MetricMode) => {
    setMetricMode(next);
    if (next !== METRIC_MODE.CUSTOM) setSelectedMetrics([]);
  };

  const handleAddMetric = (metric: {
    id: UUID;
    name: string;
    metric_scope?: MetricScope[];
  }) => {
    setSelectedMetrics(prev =>
      prev.some(m => m.id === metric.id)
        ? prev
        : [
            ...prev,
            { id: metric.id, name: metric.name, scope: metric.metric_scope },
          ]
    );
  };

  const handleRemoveMetric = (metricId: UUID) => {
    setSelectedMetrics(prev => prev.filter(m => m.id !== metricId));
  };

  const handleToggleVersion = (version: string) => {
    setInternalVersionHashes(prev => {
      const next = new Set(prev);
      if (next.has(version)) {
        next.delete(version);
      } else {
        next.add(version);
      }
      return next;
    });
  };

  const handleWhenChange = (next: RunWhen) => {
    setWhen(next);
    if (next === RUN_WHEN.NOW) {
      setReuseDropped(false);
      return;
    }
    // Scheduled runs always call the endpoint, so reusing outputs is off.
    if (scoringTarget === SCORING_TARGET.REUSE) {
      setScoringTarget(SCORING_TARGET.FRESH);
      setReuseDropped(true);
    }
    setScheduleForm(prev => ({ ...prev, repeat: next === RUN_WHEN.REPEAT }));
  };

  // -----------------------------------------------------------------------
  // Resolve test set IDs + endpoint ID for execution
  // -----------------------------------------------------------------------

  const resolveTestSetIds = (): string[] => {
    switch (mode) {
      case 'executeTestSet':
        return [props.data.testSetId];
      case 'newTestRun':
        return selectedTestSet ? [selectedTestSet.id as string] : [];
      case 'runExperiment':
        return selectedTestSet ? [selectedTestSet.id as string] : [];
      case 'rerunTestRun':
        return [props.data.testSetId];
      case 'createFromGrid':
        return props.data.selectedTestSetIds;
    }
  };

  const resolveEndpointId = (): string | null => {
    if (mode === 'rerunTestRun') return props.data.endpointId;
    return selectedEndpoint;
  };

  const resolveExperiments = (): SelectedExperiment[] => {
    if (mode === 'runExperiment') {
      return Array.from(internalVersionHashes).map(hash => ({
        experiment_id: props.data.experiment.id,
        experiment_name: props.data.experiment.name,
        version: hash,
      }));
    }
    return selectedExperiments;
  };

  // -----------------------------------------------------------------------
  // Execute
  // -----------------------------------------------------------------------

  const preflightRequestRef = useRef<{
    testSetIds: string[];
    endpointId: string;
    correlationId: string;
  } | null>(null);

  const startPreflight = () => {
    setError(undefined);
    const testSetIds = resolveTestSetIds();
    const endpointId = resolveEndpointId();
    if (!endpointId || testSetIds.length === 0) return;

    const correlationId = safeRandomUUID();
    setPreflightCorrelationId(correlationId);

    preflightRequestRef.current = {
      testSetIds,
      endpointId,
      correlationId,
    };

    setPreflightChecks([]);
    setPreflightDialogOpen(true);
  };

  const firePreflightPost = useCallback(async () => {
    const req = preflightRequestRef.current;
    if (!req) return;

    try {
      const preflightClient = apiFactory.getPreflightClient();
      const response = await preflightClient.runPreflightChecks({
        test_set_ids: req.testSetIds,
        endpoint_id: req.endpointId,
        correlation_id: req.correlationId,
        scoring_target: scoringTarget,
        metric_mode: metricMode,
        selected_metrics:
          metricMode === METRIC_MODE.CUSTOM
            ? selectedMetrics.map(m => ({
                id: m.id,
                name: m.name,
                scope: m.scope,
              }))
            : undefined,
        execution_model_id: selectedExecutionModelId || undefined,
        evaluation_model_id: selectedEvaluationModelId || undefined,
        mode: 'async',
      });

      setPreflightChecks(response.checks);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to start preflight checks'));
      setPreflightDialogOpen(false);
    }
  }, [
    apiFactory,
    scoringTarget,
    metricMode,
    selectedMetrics,
    selectedExecutionModelId,
    selectedEvaluationModelId,
  ]);

  const handlePreflightProceed = () => {
    setPreflightDialogOpen(false);
    doExecute();
  };

  const handlePreflightCancel = () => {
    setPreflightDialogOpen(false);
  };

  const handlePreflightRetry = () => {
    const testSetIds = resolveTestSetIds();
    const endpointId = resolveEndpointId();
    if (!endpointId || testSetIds.length === 0) return;

    const newCorrelationId = safeRandomUUID();
    setPreflightCorrelationId(newCorrelationId);
    setPreflightChecks([]);

    preflightRequestRef.current = {
      testSetIds,
      endpointId,
      correlationId: newCorrelationId,
    };
  };

  const customMetricsPayload = () =>
    metricMode === METRIC_MODE.CUSTOM && selectedMetrics.length > 0
      ? selectedMetrics.map(m => ({ id: m.id, name: m.name, scope: m.scope }))
      : null;

  const doExecute = async () => {
    const testSetIds = resolveTestSetIds();
    const endpointId = resolveEndpointId();
    if (!endpointId || testSetIds.length === 0) return;

    setExecuting(true);
    try {
      const testSetsClient = apiFactory.getTestSetsClient();
      const experiments = resolveExperiments();

      const baseAttributes: Record<string, unknown> = {
        execution_mode: executionMode,
        // Recorded so the run's Configuration tab reports the choice that was actually
        // made. It used to be honoured here and then dropped, leaving the tab to
        // default it to "on" for every run, including ones where it was turned off.
        run_preflight_checks: preflightEnabled,
      };

      const metrics = customMetricsPayload();
      if (metrics) baseAttributes.metrics = metrics;

      if (selectedExecutionModelId) {
        baseAttributes.execution_model_id = selectedExecutionModelId;
      }
      if (selectedEvaluationModelId) {
        baseAttributes.evaluation_model_id = selectedEvaluationModelId;
      }

      if (scoringTarget === SCORING_TARGET.REUSE) {
        if (mode === 'rerunTestRun' && rerunConfig?.testRunId) {
          baseAttributes.reference_test_run_id = rerunConfig.testRunId;
        } else if (lastTestRun) {
          baseAttributes.reference_test_run_id = lastTestRun.id;
        }
      }

      const outcome = await executeBatchedTestRuns({
        testSetsClient,
        testSetIds,
        endpointId,
        selectedExperiments: experiments,
        baseAttributes,
      });

      if (tags.length > 0) {
        try {
          let organizationId: string;
          if (mode === 'rerunTestRun') {
            const ep = await apiFactory
              .getEndpointsClient()
              .getEndpoint(endpointId);
            organizationId = ep.organization_id as string;
          } else {
            const epObj =
              filteredEndpoints.find(e => e.id === endpointId) ??
              endpoints.find(e => e.id === endpointId);
            if (epObj?.organization_id) {
              organizationId = epObj.organization_id;
            } else {
              const ep = await apiFactory
                .getEndpointsClient()
                .getEndpoint(endpointId);
              organizationId = ep.organization_id as string;
            }
          }

          await assignTagsToRuns({
            outcome,
            testRunsClient: apiFactory.getTestRunsClient(),
            tags,
            organizationId,
          });
        } catch (tagError) {
          console.error('Failed to assign tags to test run(s):', tagError);
        }
      }

      const runCount = outcome.members.length;
      notifications.show(
        runCount > 1
          ? `Queued ${runCount} test runs`
          : 'Test execution queued successfully',
        { severity: 'success', autoHideDuration: 5000 }
      );

      onExecuted?.(outcome);
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(
        asQuotaError(err)?.notice ??
          getApiErrorMessage(err, 'Failed to execute')
      );
    } finally {
      setExecuting(false);
    }
  };

  const saveScheduleSettings = async (
    schedule: TestRunScheduleDetail,
    endpointId: string,
    runSettings: NonNullable<TestRunScheduleUpdate['run_settings']>
  ) => {
    // Send only the timing that changed: changing it clears moved and skipped runs.
    const spec = changedFields(
      toScheduleSpec(fromSchedule(schedule)),
      toScheduleSpec(scheduleForm)
    );
    await apiFactory.getTestRunSchedulesClient().update(schedule.id, {
      ...spec,
      ...(endpointId !== schedule.endpoint?.id
        ? { endpoint_id: endpointId }
        : {}),
      run_settings: runSettings,
    });
    await queryClient.invalidateQueries({ queryKey: scheduleKeys.all() });
    notifications.show(`Saved ${schedule.name}`, { severity: 'success' });
    onSuccess?.();
    onClose();
  };

  const doSchedule = async () => {
    const testSetIds = resolveTestSetIds();
    const endpointId = resolveEndpointId();
    if (!endpointId || testSetIds.length === 0) return;
    setExecuting(true);
    try {
      const metrics = customMetricsPayload();
      const runSettings = {
        execution_options: {
          execution_mode: executionMode,
          run_preflight_checks: preflightEnabled,
        },
        ...(metrics ? { metrics } : {}),
        // The selectors use '' for "default model"; the API wants null.
        execution_model_id: selectedExecutionModelId || null,
        evaluation_model_id: selectedEvaluationModelId || null,
      };
      if (editingSchedule) {
        await saveScheduleSettings(editingSchedule, endpointId, runSettings);
        return;
      }
      const created = await apiFactory.getTestRunSchedulesClient().create({
        ...(testSetIds.length > 1
          ? { test_set_ids: testSetIds }
          : { test_set_id: testSetIds[0] }),
        endpoint_id: endpointId,
        schedule: toScheduleSpec(scheduleForm),
        run_settings: runSettings,
      });
      const first = created[0];
      notifications.show(
        created.length > 1
          ? `Created ${created.length} schedules`
          : first?.next_run_at
            ? `Scheduled ${first.name}. Next run ${formatRunTime(first.next_run_at, first.timezone)}.`
            : 'Schedule created',
        { severity: 'success', autoHideDuration: 6000 }
      );
      await queryClient.invalidateQueries({ queryKey: scheduleKeys.all() });
      onSuccess?.();
      onClose();
    } catch (err) {
      if (getApiErrorStatus(err) === 403) {
        setError(
          editingSchedule
            ? "You don't have permission to change this schedule."
            : "You don't have permission to schedule runs in this project."
        );
        return;
      }
      setError(
        getApiErrorMessage(
          err,
          editingSchedule
            ? 'Could not save the schedule'
            : 'Failed to schedule the run'
        )
      );
    } finally {
      setExecuting(false);
    }
  };

  const handleExecute = async () => {
    if (scheduleMode) {
      await doSchedule();
      return;
    }
    if (preflightEnabled) {
      startPreflight();
      return;
    }
    await doExecute();
  };

  // -----------------------------------------------------------------------
  // Form validity
  // -----------------------------------------------------------------------

  // Proactive quota gate: mirrors the backend's TEST_EXECUTIONS check on the
  // execute endpoints, which refuses a run whose tests don't fit in what's
  // left, so the button is disabled before a request goes out at all rather
  // than only after it comes back 402. Not a replacement for that check --
  // usage can change between render and submit, and only the backend sees
  // runs still in flight -- so the server-side gate is still authoritative.
  // Until the test count loads it asks for 1, which fails open.
  //
  // Compares against `ceiling`, not `limit`: on a soft tier those differ by
  // the overage tolerance, and gating on `limit` would disable the button
  // for an org the backend would still happily accept -- erasing exactly the
  // grace band the tier grants.
  const runCount =
    resolveTestSetIds().length * Math.max(resolveExperiments().length, 1);
  const runTestCount = useRunTestCount(
    resolveTestSetIds(),
    Math.max(resolveExperiments().length, 1),
    open
  );
  const executionQuota = useQuotaGate(
    QuotaResource.TEST_EXECUTIONS,
    runTestCount ?? 1
  );

  const canExecute = useMemo(() => {
    const endpointId = resolveEndpointId();
    const testSetIds = resolveTestSetIds();
    if (!endpointId || testSetIds.length === 0) return false;
    if (mode === 'runExperiment' && internalVersionHashes.size === 0)
      return false;
    if (executionQuota.exhausted) return false;
    return true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    mode,
    selectedEndpoint,
    selectedTestSet,
    internalVersionHashes,
    executionQuota.exhausted,
  ]);

  const quotaExhaustedMessage = scheduleMode ? null : executionQuota.notice;
  const selectedEndpointIsSdk =
    filteredEndpoints.find(e => e.id === resolveEndpointId())
      ?.connection_type === 'SDK';
  // Scheduling spends nothing yet, so only the targets and the schedule itself gate it.
  const canSave = scheduleMode
    ? Boolean(resolveEndpointId()) &&
      resolveTestSetIds().length > 0 &&
      !schedulePreviewError
    : canExecute;

  // Effective test set type for multi-turn detection
  const effectiveTestSetType = useMemo(() => {
    if (testSetType) return testSetType;
    if (mode === 'newTestRun' && selectedTestSet) {
      return selectedTestSet.test_set_type?.type_value || null;
    }
    if (mode === 'rerunTestRun') return rerunConfig?.testSetType ?? null;
    return null;
  }, [testSetType, mode, selectedTestSet, rerunConfig]);

  // -----------------------------------------------------------------------
  // Section summaries (shown while a section is folded)
  // -----------------------------------------------------------------------

  const testSetSummary =
    gridTestSetIds && gridTestSetIds.length > 1
      ? plural(gridTestSetIds.length, 'test set')
      : (rerunConfig?.testSetName ??
        selectedTestSet?.name ??
        testSetName ??
        (cfg.testSetMode === 'fixed' ? 'Loading…' : 'Choose a test set'));

  const endpointName =
    rerunConfig?.endpointName ??
    filteredEndpoints.find(e => e.id === selectedEndpoint)?.name;
  const experimentCount = resolveExperiments().length;
  const targetSummary = summaryOf(
    endpointName ?? 'Choose an endpoint',
    !scheduleMode &&
      experimentCount > 0 &&
      plural(experimentCount, 'experiment')
  );

  const scoringSummary = summaryOf(
    metricMode === METRIC_MODE.CUSTOM
      ? `Custom metrics (${selectedMetrics.length})`
      : METRIC_MODE_SUMMARY[metricMode],
    selectedEvaluationModelId && 'chosen evaluation model',
    scoringTarget === SCORING_TARGET.REUSE ? 'reused outputs' : 'fresh outputs'
  );

  const whenSummary = RUN_WHEN_LABEL[when];

  const optionsSummary = summaryOf(
    executionMode,
    preflightEnabled ? 'preflight on' : 'preflight off',
    !scheduleMode && tags.length > 0 && plural(tags.length, 'tag')
  );

  const footerSummary = scheduleMode
    ? editingSchedule
      ? null
      : resolveTestSetIds().length > 1
        ? `Creates ${plural(resolveTestSetIds().length, 'schedule')}`
        : 'Creates 1 schedule'
    : runCount > 0
      ? summaryOf(
          plural(runCount, 'run'),
          runTestCount !== null &&
            runTestCount !== undefined &&
            plural(runTestCount, 'test')
        )
      : null;

  // -----------------------------------------------------------------------
  // Sections
  // -----------------------------------------------------------------------

  const renderTestSetField = () => {
    if (cfg.testSetMode === 'single') {
      return (
        <TestSetField
          testSets={testSets}
          value={selectedTestSet}
          onChange={setSelectedTestSet}
        />
      );
    }
    if (gridTestSetIds && gridTestSetIds.length > 1) {
      return (
        <FixedField
          label="Test Sets"
          value={`${gridTestSetIds.length} selected in the list`}
        />
      );
    }
    return <FixedField label="Test Set" value={testSetSummary} />;
  };

  const renderEndpointField = () =>
    cfg.endpointEditable ? (
      <EndpointField
        endpoints={filteredEndpoints}
        value={selectedEndpoint}
        onChange={setSelectedEndpoint}
        loading={endpointsLoading}
      />
    ) : (
      <FixedField label="Endpoint" value={rerunConfig?.endpointName ?? ''} />
    );

  const renderExperiments = () => {
    if (experimentData) {
      return (
        <ExperimentVersionPicker
          experiment={experimentData.experiment}
          selected={internalVersionHashes}
          onToggle={handleToggleVersion}
        />
      );
    }
    if (!cfg.experimentsEditable || !effectiveProjectId) return null;
    if (scheduleMode) {
      return (
        <Typography variant="body2" color="text.secondary">
          Scheduled runs run without an experiment.
        </Typography>
      );
    }
    return (
      <ExperimentPicker
        selected={selectedExperiments}
        onChange={setSelectedExperiments}
        onAdd={() => setExperimentsDrawerOpen(true)}
      />
    );
  };

  const reuseCaption = scheduleMode
    ? 'Scheduled runs always call the endpoint'
    : mode === 'rerunTestRun'
      ? 'Re-score outputs from this test run'
      : lastTestRun
        ? 'Re-score outputs from the latest test run'
        : 'No previous test run available';

  const showExecutionModel =
    effectiveTestSetType === 'Multi-Turn' || mode === 'createFromGrid';

  // -----------------------------------------------------------------------
  // Title and save button
  // -----------------------------------------------------------------------

  const title = editingSchedule
    ? `Edit ${editingSchedule.name}`
    : scheduleMode
      ? resolveTestSetIds().length > 1
        ? 'Schedule Test Sets'
        : 'Schedule Test Set'
      : mode === 'createFromGrid' && gridTestSetIds
        ? gridTestSetIds.length > 1
          ? 'Execute Test Sets'
          : 'Execute Test Set'
        : cfg.title;

  const saveButtonText = editingSchedule
    ? 'Save'
    : scheduleMode
      ? 'Schedule Run'
      : mode === 'createFromGrid' && gridTestSetIds
        ? gridTestSetIds.length > 1
          ? 'Run Test Sets'
          : 'Run Test Set'
        : cfg.saveButtonText;

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={title}
      loading={endpointsLoading || executing}
      error={error ?? quotaExhaustedMessage}
      onSave={handleExecute}
      saveDisabled={!canSave}
      saveButtonText={saveButtonText}
      loadingText={
        editingSchedule
          ? 'Saving...'
          : scheduleMode
            ? 'Scheduling...'
            : undefined
      }
      footerSummary={footerSummary}
    >
      {endpointsLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      ) : (
        // Keyed per opening so each section starts from that opening's default fold.
        <Box
          key={session}
          sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
        >
          <RunDrawerSection title="What to run" summary={testSetSummary}>
            {renderTestSetField()}
          </RunDrawerSection>

          <RunDrawerSection title="Run against" summary={targetSummary}>
            {renderEndpointField()}
            {renderExperiments()}
          </RunDrawerSection>

          <RunDrawerSection
            title="Scoring"
            summary={scoringSummary}
            defaultExpanded={
              mode === 'rerunTestRun' || metricMode === METRIC_MODE.CUSTOM
            }
          >
            <MetricsField
              metricMode={metricMode}
              onMetricModeChange={handleMetricModeChange}
              testSetMetricCount={testSetMetrics.length}
              selectedMetrics={selectedMetrics}
              onAddMetric={handleAddMetric}
              onRemoveMetric={handleRemoveMetric}
              scopeFilter={effectiveTestSetType ?? undefined}
            />
            <ModelSelector
              value={selectedEvaluationModelId}
              onChange={setSelectedEvaluationModelId}
              label="Evaluation Model"
              purpose="evaluation"
              hideHelperText
              compact
              fieldSx={drawerOutlinedFieldSx}
              enabled={open}
            />
            <ScoringTargetField
              value={scoringTarget}
              onChange={setScoringTarget}
              reuseCaption={reuseCaption}
              // Only a re-run or the set's last run has outputs to reuse.
              reuseDisabled={
                scheduleMode || (mode !== 'rerunTestRun' && !lastTestRun)
              }
              reusedRun={mode === 'executeTestSet' ? lastTestRun : null}
              reusingThisRun={mode === 'rerunTestRun'}
            />
          </RunDrawerSection>

          {(canSchedule || editingSchedule) && (
            <RunDrawerSection title="When" summary={whenSummary}>
              <WhenField
                when={when}
                onWhenChange={handleWhenChange}
                allowNow={!editingSchedule}
                form={scheduleForm}
                onFormChange={setScheduleForm}
                onPreviewError={setSchedulePreviewError}
                sdkEndpoint={selectedEndpointIsSdk}
                testSetCount={resolveTestSetIds().length}
                initialForm={
                  editingSchedule ? fromSchedule(editingSchedule) : undefined
                }
                reuseDropped={reuseDropped}
              />
            </RunDrawerSection>
          )}

          <RunDrawerSection
            title="More options"
            summary={optionsSummary}
            defaultExpanded={false}
          >
            <ExecutionModeField
              value={executionMode}
              onChange={setExecutionMode}
            />
            {showExecutionModel && (
              <ModelSelector
                value={selectedExecutionModelId}
                onChange={setSelectedExecutionModelId}
                label="Execution Model"
                purpose="execution"
                hideHelperText
                compact
                fieldSx={drawerOutlinedFieldSx}
                enabled={open}
              />
            )}
            <PreflightField
              checked={preflightEnabled}
              onChange={setPreflightEnabled}
            />
            {scheduleMode ? (
              <Typography variant="body2" color="text.secondary">
                Schedules don&apos;t keep test run tags.
              </Typography>
            ) : (
              <BaseTag
                value={tags}
                onChange={setTags}
                label="Test run tags"
                placeholder="Add tags (press Enter or comma to add)"
                chipColor="default"
                addOnBlur
                delimiters={[',', 'Enter']}
                size="small"
                margin="none"
                fullWidth
                chipClassName={tagStyles.modalTag}
                sx={drawerTagFieldSx}
              />
            )}
          </RunDrawerSection>
        </Box>
      )}
      {cfg.experimentsEditable && effectiveProjectId && (
        <SelectExperimentsDrawer
          open={experimentsDrawerOpen}
          onClose={() => setExperimentsDrawerOpen(false)}
          onConfirm={setSelectedExperiments}
          projectId={effectiveProjectId}
          initialSelection={selectedExperiments}
          title={`Experiments for this ${mode === 'rerunTestRun' ? 're-run' : 'run'}`}
          subtitle="Selecting multiple experiments queues one run per experiment."
        />
      )}
      {preflightDialogOpen && (
        <PreflightDialog
          open={preflightDialogOpen}
          correlationId={preflightCorrelationId}
          initialChecks={preflightChecks}
          onStart={firePreflightPost}
          onProceed={handlePreflightProceed}
          onCancel={handlePreflightCancel}
          onRetry={handlePreflightRetry}
        />
      )}
    </BaseDrawer>
  );
}
