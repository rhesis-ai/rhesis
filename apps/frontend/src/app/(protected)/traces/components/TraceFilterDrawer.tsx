'use client';

import * as React from 'react';
import type { Theme } from '@mui/material/styles';
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { readActiveProjectId } from '@/utils/active-project';
import { TRACE_METRICS_STATUS } from '@/utils/api-client/interfaces/telemetry';
import {
  EMPTY_TRACE_DRAWER_FILTERS,
  sanitizeTraceDrawerFiltersForTestRunScope,
  type TraceDrawerFilters,
  type TraceTimeRange,
} from './trace-filter-params';

export type { TraceDrawerFilters };
export {
  EMPTY_TRACE_DRAWER_FILTERS,
  hasActiveTraceDrawerFilters,
  countActiveTraceDrawerFilters,
} from './trace-filter-params';

const TIME_RANGE_OPTIONS: { label: string; value: TraceTimeRange }[] = [
  { label: 'All time', value: 'all' },
  { label: '24h', value: '24h' },
  { label: '7d', value: '7d' },
  { label: '30d', value: '30d' },
];

const SOURCE_OPTIONS = [
  { label: 'Tests', value: 'test' },
  { label: 'Live', value: 'operation' },
] as const;

const EVAL_OPTIONS = [
  { label: 'Pass', value: TRACE_METRICS_STATUS.PASS },
  { label: 'Fail', value: TRACE_METRICS_STATUS.FAIL },
  { label: 'Error', value: TRACE_METRICS_STATUS.ERROR },
] as const;

const ENV_OPTIONS = [
  { label: 'Development', value: 'development' },
  { label: 'Staging', value: 'staging' },
  { label: 'Production', value: 'production' },
] as const;

const textFieldSx = {
  '& .MuiOutlinedInput-root': {
    borderRadius: BORDER_RADIUS.sm,
    fontSize: 14,
  },
  '& .MuiOutlinedInput-input': {
    padding: (theme: Theme) => theme.spacing(2.5, 1.75),
  },
};

interface TraceFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TraceDrawerFilters;
  onApply: (filters: TraceDrawerFilters) => void;
  sessionToken: string;
  fixedTestRunId?: string;
}

export default function TraceFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
  sessionToken,
  fixedTestRunId,
}: TraceFilterDrawerProps) {
  const isTestRunScope = Boolean(fixedTestRunId);

  const resetFilters = React.useMemo(
    () =>
      fixedTestRunId
        ? sanitizeTraceDrawerFiltersForTestRunScope(
            EMPTY_TRACE_DRAWER_FILTERS,
            fixedTestRunId
          )
        : EMPTY_TRACE_DRAWER_FILTERS,
    [fixedTestRunId]
  );

  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    resetFilters,
    onApply,
    onClose
  );
  const [projects, setProjects] = React.useState<
    Array<{ id: string; name: string }>
  >([]);
  const [endpoints, setEndpoints] = React.useState<Endpoint[]>([]);

  // Use a ref so the effect can read the current projectId without re-running
  // every time the draft changes (which would cause an infinite loop).
  const draftProjectIdRef = React.useRef(draft.projectId);
  draftProjectIdRef.current = draft.projectId;

  React.useEffect(() => {
    const fetchData = async () => {
      if (!sessionToken) return;
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const projectsResponse = await clientFactory
          .getProjectsClient()
          .getProjects({ limit: 100 });
        const projectsData = Array.isArray(projectsResponse)
          ? projectsResponse
          : projectsResponse?.data || [];
        setProjects(projectsData);

        // Pre-select active project when no project filter is already set
        if (!draftProjectIdRef.current) {
          const activeId = readActiveProjectId();
          if (
            activeId &&
            projectsData.some((p: { id: string }) => String(p.id) === activeId)
          ) {
            setDraft(prev => ({ ...prev, projectId: activeId }));
          }
        }

        const endpointsResponse = await clientFactory
          .getEndpointsClient()
          .getEndpoints({ limit: 100 });
        const endpointsData = Array.isArray(endpointsResponse)
          ? endpointsResponse
          : endpointsResponse?.data || [];
        setEndpoints(endpointsData);
      } catch {
        setProjects([]);
        setEndpoints([]);
      }
    };

    if (open && sessionToken && !isTestRunScope) {
      fetchData();
    }
  }, [open, sessionToken, isTestRunScope, setDraft]);

  const filteredEndpoints = draft.projectId
    ? endpoints.filter(e => e.project_id === draft.projectId)
    : endpoints;

  const setTimeRange = (range: TraceTimeRange) => {
    setDraft(prev => ({
      ...prev,
      timeRange: range,
      ...(range !== 'custom'
        ? { startTimeAfter: undefined, startTimeBefore: undefined }
        : {}),
    }));
  };

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
      title="Filter"
    >
      {!isTestRunScope && (
        <>
          <FilterSection title="Project">
            <FormControl fullWidth size="small">
              <InputLabel>Project</InputLabel>
              <Select
                value={draft.projectId || ''}
                label="Project"
                onChange={e => {
                  const projectId = e.target.value || undefined;
                  setDraft(prev => {
                    const next = { ...prev, projectId };
                    if (prev.endpointId && projectId) {
                      const ep = endpoints.find(x => x.id === prev.endpointId);
                      if (ep && ep.project_id !== projectId) {
                        next.endpointId = undefined;
                      }
                    }
                    return next;
                  });
                }}
              >
                <MenuItem value="">All projects</MenuItem>
                {projects.map(project => (
                  <MenuItem key={project.id} value={project.id}>
                    {project.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </FilterSection>

          <FilterSection title="Endpoint">
            <FormControl
              fullWidth
              size="small"
              disabled={filteredEndpoints.length === 0 && !!draft.projectId}
            >
              <InputLabel>Endpoint</InputLabel>
              <Select
                value={draft.endpointId || ''}
                label="Endpoint"
                onChange={e =>
                  setDraft(prev => ({
                    ...prev,
                    endpointId: e.target.value || undefined,
                  }))
                }
              >
                <MenuItem value="">
                  {draft.projectId && filteredEndpoints.length === 0
                    ? 'No endpoints in project'
                    : 'All endpoints'}
                </MenuItem>
                {filteredEndpoints.map(endpoint => (
                  <MenuItem key={endpoint.id} value={endpoint.id}>
                    {endpoint.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </FilterSection>

          <FilterSection title="Environment">
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {ENV_OPTIONS.map(opt => (
                <Box
                  key={opt.value}
                  component="button"
                  type="button"
                  onClick={() =>
                    setDraft(prev => ({
                      ...prev,
                      environment:
                        prev.environment === opt.value ? undefined : opt.value,
                    }))
                  }
                  sx={filterChipSx(draft.environment === opt.value)}
                >
                  {opt.label}
                </Box>
              ))}
            </Box>
          </FilterSection>

          <FilterSection title="Time range">
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
              {TIME_RANGE_OPTIONS.map(opt => (
                <Box
                  key={opt.value}
                  component="button"
                  type="button"
                  onClick={() => setTimeRange(opt.value)}
                  sx={filterChipSx(draft.timeRange === opt.value)}
                >
                  {opt.label}
                </Box>
              ))}
              <Box
                component="button"
                type="button"
                onClick={() => setTimeRange('custom')}
                sx={filterChipSx(draft.timeRange === 'custom')}
              >
                Custom
              </Box>
            </Box>
            {draft.timeRange === 'custom' && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <TextField
                  fullWidth
                  size="small"
                  label="Start time after"
                  type="datetime-local"
                  value={
                    draft.startTimeAfter
                      ? new Date(draft.startTimeAfter)
                          .toISOString()
                          .slice(0, 16)
                      : ''
                  }
                  onChange={e =>
                    setDraft(prev => ({
                      ...prev,
                      startTimeAfter: e.target.value
                        ? new Date(e.target.value).toISOString()
                        : undefined,
                    }))
                  }
                  InputLabelProps={{ shrink: true }}
                  sx={textFieldSx}
                />
                <TextField
                  fullWidth
                  size="small"
                  label="Start time before"
                  type="datetime-local"
                  value={
                    draft.startTimeBefore
                      ? new Date(draft.startTimeBefore)
                          .toISOString()
                          .slice(0, 16)
                      : ''
                  }
                  onChange={e =>
                    setDraft(prev => ({
                      ...prev,
                      startTimeBefore: e.target.value
                        ? new Date(e.target.value).toISOString()
                        : undefined,
                    }))
                  }
                  InputLabelProps={{ shrink: true }}
                  sx={textFieldSx}
                />
              </Box>
            )}
          </FilterSection>

          <FilterSection title="Source">
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {SOURCE_OPTIONS.map(opt => (
                <Box
                  key={opt.value}
                  component="button"
                  type="button"
                  onClick={() =>
                    setDraft(prev => ({
                      ...prev,
                      traceSource:
                        prev.traceSource === opt.value ? undefined : opt.value,
                    }))
                  }
                  sx={filterChipSx(draft.traceSource === opt.value)}
                >
                  {opt.label}
                </Box>
              ))}
            </Box>
          </FilterSection>
        </>
      )}

      <FilterSection title="Evaluation">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {EVAL_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  traceMetricsStatus:
                    prev.traceMetricsStatus === opt.value
                      ? undefined
                      : opt.value,
                }))
              }
              sx={filterChipSx(draft.traceMetricsStatus === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title={isTestRunScope ? 'Test case' : 'Test association'}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {!isTestRunScope && (
            <TextField
              fullWidth
              placeholder="Test run ID"
              value={draft.testRunId || ''}
              onChange={e =>
                setDraft(prev => ({
                  ...prev,
                  testRunId: e.target.value || undefined,
                }))
              }
              sx={textFieldSx}
            />
          )}
          <TextField
            fullWidth
            placeholder="Test result ID"
            value={draft.testResultId || ''}
            onChange={e =>
              setDraft(prev => ({
                ...prev,
                testResultId: e.target.value || undefined,
              }))
            }
            sx={textFieldSx}
          />
          <TextField
            fullWidth
            placeholder="Test ID"
            value={draft.testId || ''}
            onChange={e =>
              setDraft(prev => ({
                ...prev,
                testId: e.target.value || undefined,
              }))
            }
            sx={textFieldSx}
          />
        </Box>
      </FilterSection>
    </FilterDrawerShell>
  );
}
