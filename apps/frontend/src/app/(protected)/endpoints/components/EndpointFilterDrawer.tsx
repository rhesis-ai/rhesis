'use client';

import * as React from 'react';
import { Box, FormControl, InputLabel, MenuItem, Select } from '@mui/material';
import { useSession } from 'next-auth/react';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Project } from '@/utils/api-client/interfaces/project';
import { Status } from '@/utils/api-client/interfaces/status';

export interface EndpointFilters {
  connectionType: string;
  environment: string;
  projectId: string;
  status: string;
}

export const EMPTY_ENDPOINT_FILTERS: EndpointFilters = {
  connectionType: '',
  environment: '',
  projectId: '',
  status: '',
};

export function hasActiveEndpointFilters(f: EndpointFilters): boolean {
  return Object.values(f).some(v => v !== '');
}

const CONNECTION_TYPE_OPTIONS = [
  { label: 'REST', value: 'REST' },
  { label: 'WebSocket', value: 'WEBSOCKET' },
  { label: 'gRPC', value: 'GRPC' },
  { label: 'SDK', value: 'SDK' },
] as const;

const ENVIRONMENT_OPTIONS = [
  { label: 'Production', value: 'production' },
  { label: 'Staging', value: 'staging' },
  { label: 'Development', value: 'development' },
  { label: 'Local', value: 'local' },
] as const;

const selectSx = {
  borderRadius: BORDER_RADIUS.sm,
  fontSize: 14,
  '& .MuiOutlinedInput-notchedOutline': {
    borderRadius: BORDER_RADIUS.sm,
  },
};

interface EndpointFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: EndpointFilters;
  onApply: (filters: EndpointFilters) => void;
  /** Hide project filter when the grid is already scoped to a project */
  hideProjectFilter?: boolean;
}

export default function EndpointFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
  hideProjectFilter = false,
}: EndpointFilterDrawerProps) {
  const { data: session } = useSession();
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_ENDPOINT_FILTERS,
    onApply,
    onClose
  );
  const [projects, setProjects] = React.useState<Project[]>([]);
  const [statuses, setStatuses] = React.useState<Status[]>([]);
  const [loadingOptions, setLoadingOptions] = React.useState(false);

  React.useEffect(() => {
    const sessionToken = session?.session_token;
    if (!open || !sessionToken) return;

    const loadOptions = async () => {
      setLoadingOptions(true);
      try {
        const factory = new ApiClientFactory(sessionToken);
        const [projectsResponse, statusesResponse] = await Promise.all([
          hideProjectFilter
            ? Promise.resolve(null)
            : factory.getProjectsClient().getProjects(),
          factory.getStatusClient().getStatuses({
            entity_type: 'General',
            sort_by: 'name',
            sort_order: 'asc',
          }),
        ]);

        if (!hideProjectFilter && projectsResponse) {
          const projectsArray = Array.isArray(projectsResponse)
            ? projectsResponse
            : projectsResponse?.data || [];
          setProjects(projectsArray.filter((p: Project) => p?.id && p?.name));
        }

        const uniqueStatuses = statusesResponse.filter(
          (s, i, arr) => s?.name && arr.findIndex(x => x.name === s.name) === i
        );
        setStatuses(uniqueStatuses);
      } catch {
        if (!hideProjectFilter) setProjects([]);
        setStatuses([]);
      } finally {
        setLoadingOptions(false);
      }
    };

    loadOptions();
  }, [open, session?.session_token, hideProjectFilter]);

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
      title="Filter"
    >
      <FilterSection title="Connection Type">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {CONNECTION_TYPE_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  connectionType:
                    prev.connectionType === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.connectionType === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Environment">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {ENVIRONMENT_OPTIONS.map(opt => (
            <Box
              key={opt.value}
              component="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  environment: prev.environment === opt.value ? '' : opt.value,
                }))
              }
              sx={filterChipSx(draft.environment === opt.value)}
            >
              {opt.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      {!hideProjectFilter && (
        <FilterSection title="Project">
          <FormControl fullWidth size="small" disabled={loadingOptions}>
            <InputLabel id="endpoint-filter-project-label">Project</InputLabel>
            <Select
              labelId="endpoint-filter-project-label"
              label="Project"
              value={draft.projectId}
              onChange={e =>
                setDraft(prev => ({ ...prev, projectId: e.target.value }))
              }
              sx={selectSx}
            >
              <MenuItem value="">
                <em>All projects</em>
              </MenuItem>
              {projects.map(project => (
                <MenuItem key={project.id} value={project.id}>
                  {project.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </FilterSection>
      )}

      <FilterSection title="Status">
        <FormControl fullWidth size="small" disabled={loadingOptions}>
          <InputLabel id="endpoint-filter-status-label">Status</InputLabel>
          <Select
            labelId="endpoint-filter-status-label"
            label="Status"
            value={draft.status}
            onChange={e =>
              setDraft(prev => ({ ...prev, status: e.target.value }))
            }
            sx={selectSx}
          >
            <MenuItem value="">
              <em>All statuses</em>
            </MenuItem>
            {statuses.map(status => (
              <MenuItem key={status.id} value={status.name}>
                {status.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </FilterSection>
    </FilterDrawerShell>
  );
}
