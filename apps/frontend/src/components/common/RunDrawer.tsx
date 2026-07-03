'use client';

import React, {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useRef,
} from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  FormHelperText,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  ArrowForward as ArrowForwardIcon,
  AutoGraph as AutoGraphIcon,
  Bolt as BoltIcon,
  CallSplit as CallSplitIcon,
  Close as CloseIcon,
  Edit as EditIcon,
  FlightTakeoff as FlightTakeoffIcon,
  Psychology as PsychologyIcon,
  Replay as ReplayIcon,
  Tune as TuneIcon,
} from '@mui/icons-material';
import Switch from '@mui/material/Switch';
import Link from 'next/link';
import BaseDrawer from '@/components/common/BaseDrawer';
import BaseTag from '@/components/common/BaseTag';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import {
  drawerDisabledFieldSx,
  drawerOutlinedFieldSx,
  drawerTagFieldSx,
} from '@/components/common/drawerFormFieldSx';
import ModelSelector from '@/components/common/ModelSelector';
import { PreflightDialog } from '@/components/common/PreflightDialog';
import SelectExperimentsDrawer from '@/components/common/SelectExperimentsDrawer';
import SelectMetricsDialog from '@/components/common/SelectMetricsDialog';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Project } from '@/utils/api-client/interfaces/project';
import { useEndpoints } from '@/hooks/useEndpoints';
import type {
  TestSetMetric,
  LastTestRunSummary,
  TestSet,
} from '@/utils/api-client/interfaces/test-set';
import {
  ExperimentDetail,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { useNotifications } from '@/components/common/NotificationContext';
import { getApiErrorMessage } from '@/utils/error-utils';
import {
  executeBatchedTestRuns,
  assignTagsToRuns,
  type SelectedExperiment,
} from '@/utils/test-run-batch';
import { BiotechIcon } from '@/components/icons';
import tagStyles from '@/styles/BaseTag.module.css';
import { BORDER_RADIUS } from '@/styles/theme';
import type { UUID } from 'crypto';
import { readActiveProjectId } from '@/utils/active-project';
import { formatDate } from '@/utils/date';

// ---------------------------------------------------------------------------
// Shared local types
// ---------------------------------------------------------------------------

interface ProjectOption {
  id: UUID;
  name: string;
  nano_id?: string;
  created_at?: string;
}

interface EndpointOption {
  id: UUID;
  name: string;
  environment?: 'development' | 'staging' | 'production' | 'local';
  project_id?: string;
  organization_id?: string;
}

interface SelectedMetric {
  id: UUID;
  name: string;
  scope?: string[];
}

type MetricMode = 'use_test_set' | 'use_behavior' | 'define_custom';
type ScoringTarget = 'fresh' | 'reuse';

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
  | { mode: 'executeTestSet'; data: { testSetId: string } }
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
  sessionToken: string;
  onSuccess?: () => void;
} & RunDrawerModeProps;

// ---------------------------------------------------------------------------
// Per-mode static config
// ---------------------------------------------------------------------------

interface ModeConfig {
  title: string;
  saveButtonText: string;
  projectEditable: boolean;
  /** Controls whether the project selector is rendered. Keeps projectEditable
   *  true so endpoints still load and the ambient project filters them. */
  showProjectField: boolean;
  endpointEditable: boolean;
  testSetMode: 'hidden' | 'single' | 'multi-search';
  experimentsEditable: boolean;
  showScoringTarget: boolean;
  showMetrics: boolean;
}

const MODE_CONFIGS: Record<RunDrawerProps['mode'], ModeConfig> = {
  executeTestSet: {
    title: 'Execute Test Set',
    saveButtonText: 'Execute Test Set',
    projectEditable: true,
    showProjectField: false,
    endpointEditable: true,
    testSetMode: 'hidden',
    experimentsEditable: true,
    showScoringTarget: true,
    showMetrics: true,
  },
  newTestRun: {
    title: 'Test Run Configuration',
    saveButtonText: 'Execute Now',
    projectEditable: true,
    showProjectField: false,
    endpointEditable: true,
    testSetMode: 'single',
    experimentsEditable: true,
    showScoringTarget: true,
    showMetrics: true,
  },
  runExperiment: {
    title: 'Run Experiment',
    saveButtonText: 'Run Experiment',
    projectEditable: false,
    showProjectField: false,
    endpointEditable: true,
    testSetMode: 'single',
    experimentsEditable: false,
    showScoringTarget: true,
    showMetrics: true,
  },
  rerunTestRun: {
    title: 'Re-run Tests',
    saveButtonText: 'Re-run Tests',
    projectEditable: false,
    showProjectField: false,
    endpointEditable: false,
    testSetMode: 'hidden',
    experimentsEditable: true,
    showScoringTarget: true,
    showMetrics: true,
  },
  createFromGrid: {
    title: 'Execute Test Sets',
    saveButtonText: 'Run Test Sets',
    projectEditable: true,
    showProjectField: false,
    endpointEditable: true,
    testSetMode: 'hidden',
    experimentsEditable: true,
    showScoringTarget: true,
    showMetrics: true,
  },
};

const RERUN_SECTION_SX = {
  display: 'flex',
  flexDirection: 'column',
  gap: '40px',
} as const;

const RERUN_FIELDS_SX = {
  display: 'flex',
  flexDirection: 'column',
  gap: '30px',
} as const;

const RERUN_OUTLINE_BUTTON_SX = {
  borderWidth: 2,
  borderColor: 'primary.main',
  color: 'primary.main',
  fontWeight: 700,
  fontSize: 14,
  lineHeight: '22px',
  borderRadius: BORDER_RADIUS.sm,
  px: '16px',
  py: '8px',
  textTransform: 'none',
  '&:hover': { borderWidth: 2 },
} as const;

const EXPERIMENT_SECTION_DESCRIPTION =
  "Each selected experiment triggers its own test run with that experiment's parameters pinned. Leave empty to run without an experiment.";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RunDrawer(props: RunDrawerProps) {
  const { open, onClose, sessionToken, onSuccess, mode } = props;
  const cfg = MODE_CONFIGS[mode];
  const notifications = useNotifications();

  // ---- Core state ----
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string>();

  // ---- Project / Endpoint ----
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const { data: rawEndpoints, isLoading: endpointsLoading } = useEndpoints(
    sessionToken,
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
        })),
    [rawEndpoints]
  );
  const [filteredEndpoints, setFilteredEndpoints] = useState<EndpointOption[]>(
    []
  );
  const [selectedProject, setSelectedProject] = useState<UUID | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<UUID | null>(null);

  // ---- Test set (single-select for newTestRun) ----
  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [selectedTestSet, setSelectedTestSet] = useState<TestSet | null>(null);

  // ---- Test set multi-search (runExperiment) ----
  const [searchTestSets, setSearchTestSets] = useState<TestSet[]>([]);
  const [selectedSearchTestSets, setSelectedSearchTestSets] = useState<
    TestSet[]
  >([]);
  const [testSetInput, setTestSetInput] = useState('');
  const [testSetSearching, setTestSetSearching] = useState(false);
  const searchTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

  // ---- Test set info (for metrics/multi-turn) ----
  const [testSetType, setTestSetType] = useState<string | null>(null);
  const [testSetMetrics, setTestSetMetrics] = useState<TestSetMetric[]>([]);

  // ---- Execution mode ----
  const [executionMode, setExecutionMode] = useState<string>('Parallel');

  // ---- Scoring target ----
  const [scoringTarget, setScoringTarget] = useState<ScoringTarget>('fresh');
  const [lastTestRun, setLastTestRun] = useState<LastTestRunSummary | null>(
    null
  );

  // ---- Metrics ----
  const [metricMode, setMetricMode] = useState<MetricMode>('use_behavior');
  const [selectedMetrics, setSelectedMetrics] = useState<SelectedMetric[]>([]);
  const [metricsDialogOpen, setMetricsDialogOpen] = useState(false);

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
  const [preflightEnabled, setPreflightEnabled] = useState(false);
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

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  // -----------------------------------------------------------------------
  // Derived helpers
  // -----------------------------------------------------------------------

  const rerunConfig = mode === 'rerunTestRun' ? props.data : null;
  const experimentData = mode === 'runExperiment' ? props.data : null;
  const executeTestSetId =
    mode === 'executeTestSet' ? props.data.testSetId : null;
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
    setError(undefined);
    setExecuting(false);
    setTags([]);
    setExecutionMode('Parallel');
    setScoringTarget('fresh');
    setLastTestRun(null);
    setSelectedMetrics([]);
    setMetricMode('use_behavior');
    setSelectedExecutionModelId('');
    setSelectedEvaluationModelId('');
    setSelectedExperiments([]);
    setSelectedTestSet(null);
    setSelectedSearchTestSets([]);
    setTestSetInput('');
    setPreflightDialogOpen(false);
    setPreflightCorrelationId('');
    setPreflightChecks([]);

    if (cfg.projectEditable) {
      // Pre-select the session's active project so users don't have to choose
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

  // -----------------------------------------------------------------------
  // Load projects + endpoints (editable modes)
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!open || !sessionToken) return;
    if (!cfg.projectEditable && mode !== 'runExperiment') return;

    let mounted = true;
    const load = async () => {
      setLoading(true);
      try {
        const projectsClient = apiFactory.getProjectsClient();
        const projectsData = await projectsClient.getProjects({
          sort_by: 'name',
          sort_order: 'asc',
          limit: 100,
        });

        if (!mounted) return;

        let projectsArray: Project[] = [];
        if (Array.isArray(projectsData)) {
          projectsArray = projectsData;
        } else if (projectsData && Array.isArray(projectsData.data)) {
          projectsArray = projectsData.data;
        }

        setProjects(
          projectsArray
            .filter((p: Project) => p.id && p.name && p.name.trim() !== '')
            .map((p: Project) => ({
              id: p.id as UUID,
              name: p.name,
              nano_id: (p as Project & { nano_id?: string }).nano_id,
              created_at: p.created_at,
            }))
        );
      } catch {
        if (mounted) {
          setProjects([]);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, sessionToken, mode]);

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
    if (!open || (mode !== 'newTestRun' && mode !== 'runExperiment')) return;
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
  }, [open, mode, apiFactory]);

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
        setTestSetType(testSet?.test_set_type?.type_value || null);

        const metrics = await client.getTestSetMetrics(testSetId);
        if (!mounted) return;
        setTestSetMetrics(metrics || []);

        if (mode === 'executeTestSet') {
          setMetricMode(metrics?.length > 0 ? 'use_test_set' : 'use_behavior');
        }
      } catch {
        if (mounted) {
          setTestSetType(null);
          setTestSetMetrics([]);
          setMetricMode('use_behavior');
        }
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [open, executeTestSetId, rerunConfig?.testSetId, mode, apiFactory]);

  // Rerun: pre-fill metrics & models from original attributes
  useEffect(() => {
    if (!open || mode !== 'rerunTestRun' || !rerunConfig) return;
    const orig = rerunConfig.originalAttributes;
    const origMetrics = orig?.metrics;
    if (origMetrics && origMetrics.length > 0) {
      setMetricMode('define_custom');
      setSelectedMetrics(
        origMetrics.map(m => ({
          id: m.id as UUID,
          name: m.name,
          scope: m.scope,
        }))
      );
    }
    setSelectedExecutionModelId((orig?.execution_model_id as string) || '');
    setSelectedEvaluationModelId((orig?.evaluation_model_id as string) || '');
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
        setScoringTarget('fresh');
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
          setScoringTarget('fresh');
        }
      } catch {
        if (mounted) {
          setLastTestRun(null);
          setScoringTarget('fresh');
        }
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [mode, selectedEndpoint, executeTestSetId, open, apiFactory]);

  // -----------------------------------------------------------------------
  // Multi-search test sets (runExperiment mode)
  // -----------------------------------------------------------------------

  const fetchSearchTestSets = useCallback(
    async (search: string) => {
      setTestSetSearching(true);
      try {
        const client = apiFactory.getTestSetsClient();
        const params: Record<string, unknown> = {
          sort_by: 'name',
          sort_order: 'asc' as const,
          limit: 100,
        };
        if (search.trim().length >= 2) {
          const escaped = search.replace(/'/g, "''");
          params.$filter = `contains(tolower(name), tolower('${escaped}'))`;
        }
        const res = await client.getTestSets(params);
        setSearchTestSets(Array.isArray(res?.data) ? res.data : []);
      } catch {
        setSearchTestSets([]);
      } finally {
        setTestSetSearching(false);
      }
    },
    [apiFactory]
  );

  useEffect(() => {
    if (open && mode === 'runExperiment') fetchSearchTestSets('');
  }, [open, mode, fetchSearchTestSets]);

  const handleTestSetInputChange = useCallback(
    (_: unknown, value: string, reason: string) => {
      setTestSetInput(value);
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
      if (value === '' || reason === 'reset') {
        fetchSearchTestSets('');
        return;
      }
      if (value.length < 2) return;
      searchTimeoutRef.current = setTimeout(
        () => fetchSearchTestSets(value),
        500
      );
    },
    [fetchSearchTestSets]
  );

  // -----------------------------------------------------------------------
  // Metric helpers
  // -----------------------------------------------------------------------

  const handleAddMetric = async (metricId: UUID) => {
    try {
      const metric = await apiFactory.getMetricsClient().getMetric(metricId);
      if (metric) {
        setSelectedMetrics(prev => [
          ...prev,
          {
            id: metric.id as UUID,
            name: metric.name,
            scope: metric.metric_scope,
          },
        ]);
      }
    } catch (err) {
      console.error('Failed to fetch metric details:', err);
    }
  };

  const handleRemoveMetric = (metricId: UUID) => {
    setSelectedMetrics(prev => prev.filter(m => m.id !== metricId));
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

    const correlationId = crypto.randomUUID();
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
          metricMode === 'define_custom'
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

    const newCorrelationId = crypto.randomUUID();
    setPreflightCorrelationId(newCorrelationId);
    setPreflightChecks([]);

    preflightRequestRef.current = {
      testSetIds,
      endpointId,
      correlationId: newCorrelationId,
    };
  };

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
      };

      if (
        cfg.showMetrics &&
        metricMode === 'define_custom' &&
        selectedMetrics.length > 0
      ) {
        baseAttributes.metrics = selectedMetrics.map(m => ({
          id: m.id,
          name: m.name,
          scope: m.scope,
        }));
      }

      if (selectedExecutionModelId) {
        baseAttributes.execution_model_id = selectedExecutionModelId;
      }
      if (selectedEvaluationModelId) {
        baseAttributes.evaluation_model_id = selectedEvaluationModelId;
      }

      if (cfg.showScoringTarget && scoringTarget === 'reuse') {
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
            sessionToken,
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

      onSuccess?.();
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to execute'));
    } finally {
      setExecuting(false);
    }
  };

  const handleExecute = async () => {
    if (preflightEnabled) {
      startPreflight();
      return;
    }
    await doExecute();
  };

  // -----------------------------------------------------------------------
  // Form validity
  // -----------------------------------------------------------------------

  const canExecute = useMemo(() => {
    const endpointId = resolveEndpointId();
    const testSetIds = resolveTestSetIds();
    if (!endpointId || testSetIds.length === 0) return false;
    if (mode === 'runExperiment' && internalVersionHashes.size === 0)
      return false;
    return true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, selectedEndpoint, selectedTestSet, internalVersionHashes]);

  // Effective test set type for multi-turn detection
  const effectiveTestSetType = useMemo(() => {
    if (testSetType) return testSetType;
    if (mode === 'newTestRun' && selectedTestSet) {
      return selectedTestSet.test_set_type?.type_value || null;
    }
    if (mode === 'rerunTestRun') return rerunConfig?.testSetType ?? null;
    return null;
  }, [testSetType, mode, selectedTestSet, rerunConfig]);

  // Effective scope filter for metrics dialog
  const metricScopeFilter = effectiveTestSetType ?? undefined;

  // -----------------------------------------------------------------------
  // Render helpers
  // -----------------------------------------------------------------------

  const renderProjectField = () => {
    if (!cfg.showProjectField) return null;

    if (!cfg.projectEditable) {
      if (mode === 'rerunTestRun') {
        return (
          <TextField
            label="Project"
            value={rerunConfig?.projectName ?? ''}
            disabled
            fullWidth
            InputLabelProps={{ shrink: true }}
            sx={drawerDisabledFieldSx}
          />
        );
      }
      return null;
    }

    return (
      <FormControl fullWidth>
        <Autocomplete
          options={projects}
          value={projects.find(p => p.id === selectedProject) || null}
          onChange={(_, v) => {
            setSelectedProject(v?.id ?? null);
            setSelectedEndpoint(null);
          }}
          getOptionLabel={option => {
            const hasDuplicate =
              projects.filter(p => p.name === option.name).length > 1;
            if (!hasDuplicate) return option.name;
            const suffix = option.nano_id
              ? option.nano_id.slice(0, 6)
              : option.id.slice(0, 6);
            return `${option.name} (${suffix})`;
          }}
          renderOption={(props, option) => {
            const { key: _key, ...otherProps } = props;
            const hasDuplicate =
              projects.filter(p => p.name === option.name).length > 1;
            return (
              <Box component="li" key={option.id} {...otherProps}>
                <Box>
                  <Typography variant="body2">{option.name}</Typography>
                  {hasDuplicate && (
                    <Typography variant="caption" color="text.secondary">
                      {option.created_at
                        ? `Created ${formatDate(option.created_at)}`
                        : `ID: ${option.nano_id ?? option.id.slice(0, 8)}`}
                    </Typography>
                  )}
                </Box>
              </Box>
            );
          }}
          renderInput={params => (
            <TextField
              {...params}
              label="Project (optional — filters endpoints)"
              placeholder="Active project"
            />
          )}
          isOptionEqualToValue={(a, b) => a.id === b.id}
        />
        {projects.length === 0 && !loading && (
          <FormHelperText>No projects available</FormHelperText>
        )}
      </FormControl>
    );
  };

  const renderEndpointField = () => {
    if (!cfg.endpointEditable) {
      if (mode === 'rerunTestRun') {
        return (
          <TextField
            label="Endpoint"
            value={rerunConfig?.endpointName ?? ''}
            disabled
            fullWidth
            InputLabelProps={{ shrink: true }}
            sx={drawerDisabledFieldSx}
          />
        );
      }
      return null;
    }

    const options = filteredEndpoints;

    return (
      <FormControl fullWidth>
        <Autocomplete
          options={options}
          value={options.find(e => e.id === selectedEndpoint) || null}
          onChange={(_, v) => setSelectedEndpoint(v?.id ?? null)}
          getOptionLabel={opt => opt.name}
          renderInput={params => (
            <TextField
              {...params}
              label="Endpoint"
              required
              placeholder="Select endpoint"
            />
          )}
          renderOption={(props, option) => {
            const { key: _key, ...otherProps } = props;
            return (
              <Box
                key={option.id}
                {...otherProps}
                component="li"
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span>{option.name}</span>
                {option.environment && (
                  <Chip
                    label={option.environment}
                    size="small"
                    color={
                      option.environment === 'production'
                        ? 'error'
                        : option.environment === 'staging'
                          ? 'warning'
                          : 'success'
                    }
                    sx={{ ml: 1 }}
                  />
                )}
              </Box>
            );
          }}
          isOptionEqualToValue={(a, b) => a.id === b.id}
        />
        {options.length === 0 && !loading && !endpointsLoading && (
          <FormHelperText>
            No endpoints available for this project
          </FormHelperText>
        )}
      </FormControl>
    );
  };

  const renderTestSetField = () => {
    if (cfg.testSetMode === 'hidden') {
      if (mode === 'rerunTestRun') {
        return (
          <TextField
            label="Test Set"
            value={rerunConfig?.testSetName ?? ''}
            disabled
            fullWidth
            InputLabelProps={{ shrink: true }}
            sx={drawerDisabledFieldSx}
          />
        );
      }
      return null;
    }

    if (cfg.testSetMode === 'single') {
      return (
        <Autocomplete
          options={testSets}
          value={selectedTestSet}
          onChange={(_, v) => setSelectedTestSet(v)}
          getOptionLabel={opt => opt.name || 'Unnamed Test Set'}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          renderOption={(props, option) => {
            const { key: _key, ...otherProps } = props;
            return (
              <Box component="li" key={option.id} {...otherProps}>
                {option.name || 'Unnamed Test Set'}
              </Box>
            );
          }}
          fullWidth
          renderInput={params => (
            <TextField {...params} label="Test Set" required />
          )}
        />
      );
    }

    // multi-search
    return (
      <Autocomplete
        multiple
        options={searchTestSets}
        value={selectedSearchTestSets}
        onChange={(_, v) => setSelectedSearchTestSets(v)}
        inputValue={testSetInput}
        onInputChange={handleTestSetInputChange}
        getOptionLabel={opt => opt.name || 'Unnamed Test Set'}
        isOptionEqualToValue={(a, b) => a.id === b.id}
        filterOptions={x => x}
        loading={testSetSearching}
        fullWidth
        renderOption={(props, option) => {
          const { key: _key, ...otherProps } = props;
          return (
            <Box component="li" key={option.id} {...otherProps}>
              {option.name || 'Unnamed Test Set'}
            </Box>
          );
        }}
        renderInput={params => (
          <TextField
            {...params}
            label="Test Set"
            required
            placeholder="Type to search test sets..."
            InputProps={{
              ...params.InputProps,
              endAdornment: (
                <>
                  {testSetSearching && (
                    <CircularProgress color="inherit" size={20} />
                  )}
                  {params.InputProps.endAdornment}
                </>
              ),
            }}
          />
        )}
      />
    );
  };

  const renderExperimentVersionBoxes = () => {
    if (mode !== 'runExperiment') return null;
    const allVersions = props.data.experiment.versions;
    // Deduplicate versions (same logic as VersionHistory)
    const seen = new Set<string>();
    const uniqueVersions = allVersions.filter(v => {
      if (seen.has(v.version)) return false;
      seen.add(v.version);
      return true;
    });
    return (
      <Box
        sx={{
          p: 1.5,
          border: 1,
          borderColor: 'divider',
          borderRadius: theme => theme.spacing(1),
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
          <BiotechIcon fontSize="small" color="primary" />
          <Typography variant="body2" fontWeight={500} noWrap>
            {props.data.experiment.name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            — select versions to run
          </Typography>
        </Box>
        {uniqueVersions.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No versions saved yet.
          </Typography>
        ) : (
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {[...uniqueVersions].reverse().map(v => {
              const selected = internalVersionHashes.has(v.version);
              return (
                <Chip
                  key={v.version}
                  label={shortVersion(v.version)}
                  size="small"
                  variant={selected ? 'filled' : 'outlined'}
                  color={selected ? 'primary' : 'default'}
                  sx={{ fontFamily: 'monospace', cursor: 'pointer' }}
                  onClick={() => {
                    setInternalVersionHashes(prev => {
                      const next = new Set(prev);
                      if (next.has(v.version)) {
                        next.delete(v.version);
                      } else {
                        next.add(v.version);
                      }
                      return next;
                    });
                  }}
                />
              );
            })}
          </Stack>
        )}
      </Box>
    );
  };

  const renderSelectedExperimentGroups = () => {
    if (selectedExperiments.length === 0) return null;

    const grouped = new Map<
      string,
      { name: string; versions: SelectedExperiment[] }
    >();
    for (const exp of selectedExperiments) {
      const key = String(exp.experiment_id);
      const group = grouped.get(key) ?? {
        name: exp.experiment_name,
        versions: [],
      };
      group.versions.push(exp);
      grouped.set(key, group);
    }

    return (
      <Stack spacing={1}>
        {Array.from(grouped.entries()).map(([expId, group]) => (
          <Box
            key={expId}
            sx={{
              p: 1.5,
              border: 1,
              borderColor: 'divider',
              borderRadius: theme => theme.spacing(1),
            }}
          >
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                mb: 1,
              }}
            >
              <BiotechIcon fontSize="small" color="primary" />
              <Typography variant="body2" noWrap>
                {group.name}
              </Typography>
            </Box>
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              {group.versions.map(exp => (
                <Chip
                  key={exp.version}
                  label={shortVersion(exp.version)}
                  size="small"
                  variant="outlined"
                  sx={{ fontFamily: 'monospace' }}
                  onDelete={() =>
                    setSelectedExperiments(prev =>
                      prev.filter(
                        row =>
                          row.experiment_id !== exp.experiment_id ||
                          row.version !== exp.version
                      )
                    )
                  }
                />
              ))}
            </Stack>
          </Box>
        ))}
      </Stack>
    );
  };

  const renderExperimentsSection = () => {
    if (!cfg.experimentsEditable) return null;
    if (!effectiveProjectId) return null;

    if (mode === 'rerunTestRun') {
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <FormSectionDivider
            headline="Experiment"
            descriptiveText={EXPERIMENT_SECTION_DESCRIPTION}
          />
          {renderSelectedExperimentGroups()}
          <Button
            variant="outlined"
            fullWidth
            startIcon={<AddIcon />}
            onClick={() => setExperimentsDrawerOpen(true)}
            sx={RERUN_OUTLINE_BUTTON_SX}
          >
            Add experiment
          </Button>
        </Box>
      );
    }

    const experimentGroups = renderSelectedExperimentGroups();

    return (
      <Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {EXPERIMENT_SECTION_DESCRIPTION}
        </Typography>

        {experimentGroups && <Box sx={{ mb: 2 }}>{experimentGroups}</Box>}

        <Button
          variant="outlined"
          size="small"
          startIcon={<AddIcon />}
          onClick={() => setExperimentsDrawerOpen(true)}
        >
          Add Experiment
        </Button>
      </Box>
    );
  };

  const renderExecutionMode = () => (
    <FormControl fullWidth sx={drawerOutlinedFieldSx}>
      <InputLabel shrink>Execution Mode</InputLabel>
      <Select
        value={executionMode}
        onChange={e => setExecutionMode(e.target.value)}
        label="Execution Mode"
        notched
      >
        <MenuItem value="Parallel">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CallSplitIcon fontSize="small" />
            <Box>
              <Typography variant="body1">Parallel</Typography>
              <Typography variant="caption" color="text.secondary">
                Tests run simultaneously for faster execution (default)
              </Typography>
            </Box>
          </Box>
        </MenuItem>
        <MenuItem value="Sequential">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ArrowForwardIcon fontSize="small" />
            <Box>
              <Typography variant="body1">Sequential</Typography>
              <Typography variant="caption" color="text.secondary">
                Tests run one after another, better for rate-limited endpoints
              </Typography>
            </Box>
          </Box>
        </MenuItem>
      </Select>
    </FormControl>
  );

  const renderScoringTarget = () => {
    if (!cfg.showScoringTarget) return null;
    const reusableDisabled = mode === 'executeTestSet' && !lastTestRun;

    return (
      <>
        <FormControl fullWidth sx={drawerOutlinedFieldSx}>
          <InputLabel shrink>Scoring Target</InputLabel>
          <Select
            value={scoringTarget}
            onChange={e => setScoringTarget(e.target.value as ScoringTarget)}
            label="Scoring Target"
            notched
          >
            <MenuItem value="fresh">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <BoltIcon fontSize="small" />
                <Box>
                  <Typography variant="body1">Fresh Outputs</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Call the endpoint and score the new responses
                  </Typography>
                </Box>
              </Box>
            </MenuItem>
            <MenuItem value="reuse" disabled={reusableDisabled}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ReplayIcon fontSize="small" />
                <Box>
                  <Typography variant="body1">Reuse Outputs</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {mode === 'rerunTestRun'
                      ? 'Re-score outputs from this test run'
                      : lastTestRun
                        ? 'Re-score outputs from the latest test run'
                        : 'No previous test run available'}
                  </Typography>
                </Box>
              </Box>
            </MenuItem>
          </Select>
        </FormControl>

        {scoringTarget === 'reuse' &&
          mode === 'executeTestSet' &&
          lastTestRun && (
            <Alert severity="info">
              Outputs from{' '}
              <Link
                href={`/test-runs/${lastTestRun.nano_id || lastTestRun.id}`}
                target="_blank"
                style={{ fontWeight: 600 }}
              >
                {lastTestRun.name ||
                  `Test run from ${
                    lastTestRun.created_at
                      ? formatDate(lastTestRun.created_at)
                      : 'unknown date'
                  }`}
              </Link>{' '}
              ({lastTestRun.pass_rate}% pass rate, {lastTestRun.test_count}{' '}
              tests) will be reused. Only metrics will be re-evaluated.
            </Alert>
          )}

        {scoringTarget === 'reuse' && mode === 'rerunTestRun' && (
          <Alert severity="info">
            Outputs from this test run will be reused. Only metrics will be
            re-evaluated.
          </Alert>
        )}
      </>
    );
  };

  const renderMetrics = () => {
    if (!cfg.showMetrics) return null;

    return (
      <>
        <FormControl fullWidth sx={drawerOutlinedFieldSx}>
          <InputLabel shrink>Metrics Source</InputLabel>
          <Select
            value={metricMode}
            onChange={e => {
              setMetricMode(e.target.value as MetricMode);
              if (e.target.value !== 'define_custom') setSelectedMetrics([]);
            }}
            label="Metrics Source"
            notched
          >
            {testSetMetrics.length > 0 && (
              <MenuItem value="use_test_set">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <TuneIcon fontSize="small" />
                  <Box>
                    <Typography variant="body1">Test Set Metrics</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Use {testSetMetrics.length} metric
                      {testSetMetrics.length !== 1 ? 's' : ''} configured on
                      this test set
                    </Typography>
                  </Box>
                </Box>
              </MenuItem>
            )}
            <MenuItem value="use_behavior">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <PsychologyIcon fontSize="small" />
                <Box>
                  <Typography variant="body1">Behavior Metrics</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Use default metrics defined on each test&apos;s behavior
                  </Typography>
                </Box>
              </Box>
            </MenuItem>
            <MenuItem value="define_custom">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <EditIcon fontSize="small" />
                <Box>
                  <Typography variant="body1">Custom Metrics</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Define specific metrics for this execution only
                  </Typography>
                </Box>
              </Box>
            </MenuItem>
          </Select>
        </FormControl>

        {metricMode === 'define_custom' && (
          <Box>
            <Alert severity="info" sx={{ mb: 2 }}>
              These metrics will only be used for this specific execution and
              will not be saved to the test set.
            </Alert>

            {selectedMetrics.length > 0 && (
              <Stack spacing={1} sx={{ mb: 2 }}>
                {selectedMetrics.map(metric => (
                  <Box
                    key={metric.id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      p: 1,
                      border: 1,
                      borderColor: 'divider',
                      borderRadius: theme => theme.spacing(1),
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <AutoGraphIcon fontSize="small" color="primary" />
                      <Typography variant="body2">{metric.name}</Typography>
                    </Box>
                    <IconButton
                      size="small"
                      onClick={() => handleRemoveMetric(metric.id)}
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </Box>
                ))}
              </Stack>
            )}

            <Button
              variant="outlined"
              size="small"
              startIcon={<AddIcon />}
              onClick={() => setMetricsDialogOpen(true)}
            >
              Add Metric
            </Button>

            <SelectMetricsDialog
              open={metricsDialogOpen}
              onClose={() => setMetricsDialogOpen(false)}
              onSelect={handleAddMetric}
              sessionToken={sessionToken}
              excludeMetricIds={selectedMetrics.map(m => m.id)}
              title="Add Metric to Execution"
              subtitle="Select a metric to use for this test run"
              scopeFilter={metricScopeFilter}
              variant="drawer"
            />
          </Box>
        )}
      </>
    );
  };

  // -----------------------------------------------------------------------
  // RerunTestRunDrawer layout (Figma 1641:16598)
  // -----------------------------------------------------------------------

  const renderRerunTestRunContent = () => (
    <>
      <Box sx={RERUN_SECTION_SX}>
        <FormSectionDivider headline="Execution Target" />
        <Box sx={RERUN_FIELDS_SX}>
          {renderTestSetField()}
          {renderProjectField()}
          {renderEndpointField()}
        </Box>
      </Box>

      {renderExperimentsSection()}

      <Box sx={RERUN_SECTION_SX}>
        <FormSectionDivider headline="Configuration" />
        <Box sx={RERUN_FIELDS_SX}>
          <FormControl fullWidth sx={drawerOutlinedFieldSx}>
            <InputLabel shrink>Execution Mode</InputLabel>
            <Select
              value={executionMode}
              onChange={e => setExecutionMode(e.target.value)}
              label="Execution Mode"
            >
              <MenuItem value="Parallel">Parallel</MenuItem>
              <MenuItem value="Sequential">Sequential</MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth sx={drawerOutlinedFieldSx}>
            <InputLabel shrink>Scoring Target</InputLabel>
            <Select
              value={scoringTarget}
              onChange={e => setScoringTarget(e.target.value as ScoringTarget)}
              label="Scoring Target"
            >
              <MenuItem value="fresh">Fresh Outputs</MenuItem>
              <MenuItem value="reuse">Reuse Outputs</MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth sx={drawerOutlinedFieldSx}>
            <InputLabel shrink>Metric Source</InputLabel>
            <Select
              value={metricMode}
              onChange={e => {
                setMetricMode(e.target.value as MetricMode);
                if (e.target.value !== 'define_custom') setSelectedMetrics([]);
              }}
              label="Metric Source"
            >
              {testSetMetrics.length > 0 && (
                <MenuItem value="use_test_set">Test Set Metrics</MenuItem>
              )}
              <MenuItem value="use_behavior">Behavior Metrics</MenuItem>
              <MenuItem value="define_custom">Custom Metrics</MenuItem>
            </Select>
          </FormControl>

          {metricMode === 'define_custom' && (
            <Box>
              {selectedMetrics.length > 0 && (
                <Stack spacing={1} sx={{ mb: 2 }}>
                  {selectedMetrics.map(metric => (
                    <Box
                      key={metric.id}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        p: 1,
                        border: 1,
                        borderColor: 'divider',
                        borderRadius: theme => theme.spacing(1),
                      }}
                    >
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                      >
                        <AutoGraphIcon fontSize="small" color="primary" />
                        <Typography variant="body2">{metric.name}</Typography>
                      </Box>
                      <IconButton
                        size="small"
                        onClick={() => handleRemoveMetric(metric.id)}
                      >
                        <CloseIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  ))}
                </Stack>
              )}

              <Button
                variant="outlined"
                fullWidth
                startIcon={<AddIcon />}
                onClick={() => setMetricsDialogOpen(true)}
                sx={RERUN_OUTLINE_BUTTON_SX}
              >
                Add metric
              </Button>

              <SelectMetricsDialog
                open={metricsDialogOpen}
                onClose={() => setMetricsDialogOpen(false)}
                onSelect={handleAddMetric}
                sessionToken={sessionToken}
                excludeMetricIds={selectedMetrics.map(m => m.id)}
                title="Add Metric to Execution"
                subtitle="Select a metric to use for this test run"
                scopeFilter={metricScopeFilter}
                variant="drawer"
              />
            </Box>
          )}
        </Box>
      </Box>

      <Box sx={RERUN_SECTION_SX}>
        <FormSectionDivider headline="Model Settings" />
        <Box sx={RERUN_FIELDS_SX}>
          <ModelSelector
            sessionToken={sessionToken}
            value={selectedEvaluationModelId}
            onChange={setSelectedEvaluationModelId}
            label="Evaluation Model"
            purpose="evaluation"
            hideHelperText
            compact
            fieldSx={drawerOutlinedFieldSx}
          />

          {effectiveTestSetType === 'Multi-Turn' && (
            <ModelSelector
              sessionToken={sessionToken}
              value={selectedExecutionModelId}
              onChange={setSelectedExecutionModelId}
              label="Execution Model"
              purpose="execution"
              hideHelperText
              compact
              fieldSx={drawerOutlinedFieldSx}
            />
          )}

          <Box
            sx={{
              borderTop: 1,
              borderColor: theme => theme.palette.greyscale.border,
              pt: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <Typography
              sx={{
                fontSize: 16,
                lineHeight: '24px',
                color: theme => theme.palette.greyscale.title,
              }}
            >
              Run Preflight Checks
            </Typography>
            <Switch
              checked={preflightEnabled}
              onChange={e => setPreflightEnabled(e.target.checked)}
              size="small"
            />
          </Box>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <FormSectionDivider headline="Tags" />
        <BaseTag
          value={tags}
          onChange={setTags}
          label="Tags"
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
      </Box>
    </>
  );

  // -----------------------------------------------------------------------
  // Dynamic title for createFromGrid
  // -----------------------------------------------------------------------

  const title =
    mode === 'createFromGrid' && gridTestSetIds
      ? gridTestSetIds.length > 1
        ? 'Execute Test Sets'
        : 'Execute Test Set'
      : cfg.title;

  const saveButtonText =
    mode === 'createFromGrid' && gridTestSetIds
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
      loading={loading || endpointsLoading || executing}
      error={error}
      onSave={handleExecute}
      saveDisabled={!canExecute}
      saveButtonText={saveButtonText}
    >
      {loading || endpointsLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      ) : mode === 'rerunTestRun' ? (
        renderRerunTestRunContent()
      ) : (
        <>
          {/* Execution Target */}
          <Box sx={RERUN_SECTION_SX}>
            <FormSectionDivider
              headline="Execution Target"
              descriptiveText="The endpoint that will receive and respond to each test case."
            />
            <Box sx={RERUN_FIELDS_SX}>
              {mode === 'runExperiment' && renderExperimentVersionBoxes()}
              {renderTestSetField()}
              {renderProjectField()}
              {renderEndpointField()}
            </Box>
          </Box>

          {/* Experiment */}
          {cfg.experimentsEditable &&
            effectiveProjectId &&
            (() => {
              const experimentGroups = renderSelectedExperimentGroups();
              return (
                <Box
                  sx={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
                >
                  <FormSectionDivider
                    headline="Experiment"
                    descriptiveText={EXPERIMENT_SECTION_DESCRIPTION}
                  />
                  {experimentGroups}
                  <Button
                    variant="outlined"
                    startIcon={<AddIcon />}
                    onClick={() => setExperimentsDrawerOpen(true)}
                    sx={RERUN_OUTLINE_BUTTON_SX}
                  >
                    Add experiment
                  </Button>
                </Box>
              );
            })()}

          {/* Run count summary (runExperiment only) */}
          {mode === 'runExperiment' &&
            canExecute &&
            (() => {
              const totalRuns = internalVersionHashes.size;
              return (
                <Alert severity="info">
                  This will create {totalRuns} test run
                  {totalRuns !== 1 ? 's' : ''} (1 test set &times;{' '}
                  {internalVersionHashes.size} version
                  {internalVersionHashes.size !== 1 ? 's' : ''})
                </Alert>
              );
            })()}

          {/* Advanced Options */}
          <Box sx={RERUN_SECTION_SX}>
            <FormSectionDivider
              headline="Advanced Options"
              descriptiveText="Optional overrides — defaults work well for most runs."
            />
            <Box sx={RERUN_FIELDS_SX}>
              {renderExecutionMode()}
              {renderScoringTarget()}
              {cfg.showMetrics && renderMetrics()}
              <ModelSelector
                sessionToken={sessionToken}
                value={selectedEvaluationModelId}
                onChange={setSelectedEvaluationModelId}
                label="Evaluation Model"
                purpose="evaluation"
                hideHelperText
                compact
                fieldSx={drawerOutlinedFieldSx}
              />
              {(effectiveTestSetType === 'Multi-Turn' ||
                mode === 'createFromGrid') && (
                <ModelSelector
                  sessionToken={sessionToken}
                  value={selectedExecutionModelId}
                  onChange={setSelectedExecutionModelId}
                  label="Execution Model"
                  purpose="execution"
                  hideHelperText
                  compact
                  fieldSx={drawerOutlinedFieldSx}
                />
              )}
              <FormControl fullWidth sx={drawerOutlinedFieldSx}>
                <InputLabel shrink>Run Preflight Checks</InputLabel>
                <Select
                  value={preflightEnabled ? 'yes' : 'no'}
                  onChange={e => setPreflightEnabled(e.target.value === 'yes')}
                  label="Run Preflight Checks"
                  notched
                  renderValue={val => (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {val === 'yes' ? (
                        <FlightTakeoffIcon fontSize="small" />
                      ) : (
                        <CloseIcon fontSize="small" />
                      )}
                      <Box>
                        <Typography variant="body1">
                          {val === 'yes' ? 'Yes' : 'No'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {val === 'yes'
                            ? 'Validate endpoint and model configuration before executing'
                            : 'Skip validation and start the run immediately'}
                        </Typography>
                      </Box>
                    </Box>
                  )}
                >
                  <MenuItem value="no">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CloseIcon fontSize="small" />
                      <Box>
                        <Typography variant="body1">No</Typography>
                        <Typography variant="caption" color="text.secondary">
                          Skip validation and start the run immediately
                        </Typography>
                      </Box>
                    </Box>
                  </MenuItem>
                  <MenuItem value="yes">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <FlightTakeoffIcon fontSize="small" />
                      <Box>
                        <Typography variant="body1">Yes</Typography>
                        <Typography variant="caption" color="text.secondary">
                          Validate endpoint and model configuration before
                          executing
                        </Typography>
                      </Box>
                    </Box>
                  </MenuItem>
                </Select>
              </FormControl>
            </Box>
          </Box>

          {/* Test Run Tags */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <FormSectionDivider headline="Test Run Tags" />
            <BaseTag
              value={tags}
              onChange={setTags}
              label="Tags"
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
          </Box>
        </>
      )}
      {cfg.experimentsEditable && effectiveProjectId && (
        <SelectExperimentsDrawer
          open={experimentsDrawerOpen}
          onClose={() => setExperimentsDrawerOpen(false)}
          onConfirm={setSelectedExperiments}
          sessionToken={sessionToken}
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
