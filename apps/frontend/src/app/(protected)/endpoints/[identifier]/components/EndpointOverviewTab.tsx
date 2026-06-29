'use client';

import Link from 'next/link';
import { useMemo } from 'react';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import {
  Box,
  CircularProgress,
  FormControlLabel,
  FormHelperText,
  Grid,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Select,
  Switch,
  TextField,
  FormControl,
  InputLabel,
} from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import { getProjectIcon } from '@/components/common/ProjectIcons';
import EditableSection from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useEndpointDetailContext } from './EndpointDetailContext';
import { ENVIRONMENTS } from './endpoint-detail-shared';
import {
  detailGridSpacing,
  formatConfigSource,
  formatEnvironment,
} from './endpoint-overview-utils';

interface EndpointDetailsDraft {
  name: string;
  description: string;
  project_id: string;
  environment: string;
  disable_tracing: boolean;
}

function detailsFromEndpoint(endpoint: {
  name: string;
  description?: string;
  project_id?: string;
  environment: string;
  disable_tracing?: boolean;
}): EndpointDetailsDraft {
  return {
    name: endpoint.name,
    description: endpoint.description || '',
    project_id: endpoint.project_id || '',
    environment: endpoint.environment,
    disable_tracing: endpoint.disable_tracing ?? false,
  };
}

export default function EndpointOverviewTab() {
  const { endpoint, projects, loadingProjects, saveFields } =
    useEndpointDetailContext();
  const canEditEndpoint = useCan(Capability.Endpoint.UPDATE);
  const projectList = useMemo(() => Object.values(projects), [projects]);

  const detailsInitial = useMemo(
    () => detailsFromEndpoint(endpoint),
    [endpoint]
  );

  const projectName = endpoint.project_id
    ? projects[endpoint.project_id]?.name ||
      endpoint.project?.name ||
      'Loading project...'
    : 'No project assigned';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <EditableSection
        editable={canEditEndpoint}
        title="Endpoint details"
        initialValue={detailsInitial}
        onSave={async draft => {
          await saveFields({
            name: draft.name,
            description: draft.description,
            project_id: draft.project_id || undefined,
            environment: draft.environment as Endpoint['environment'],
            disable_tracing: draft.disable_tracing,
          });
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <Grid
            container
            columnSpacing={detailGridSpacing.columnSpacing(isEditing)}
            rowSpacing={detailGridSpacing.rowSpacing(isEditing)}
          >
            <Grid size={{ xs: 12, md: 6 }}>
              {isEditing ? (
                <FormControl fullWidth required>
                  <InputLabel>Project</InputLabel>
                  <Select
                    value={draft.project_id}
                    label="Project"
                    disabled={loadingProjects}
                    onChange={e =>
                      setDraft(prev => ({
                        ...prev,
                        project_id: e.target.value,
                      }))
                    }
                    renderValue={selected => {
                      const p = projects[selected];
                      return (
                        <Box
                          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                        >
                          {p && getProjectIcon(p)}
                          {p?.name || 'Select project'}
                        </Box>
                      );
                    }}
                  >
                    {loadingProjects ? (
                      <MenuItem disabled value={draft.project_id || ''}>
                        <CircularProgress size={20} sx={{ mr: 1 }} />
                        Loading projects...
                      </MenuItem>
                    ) : (
                      projectList.map(p => (
                        <MenuItem key={p.id} value={p.id}>
                          <ListItemIcon>{getProjectIcon(p)}</ListItemIcon>
                          <ListItemText
                            primary={p.name}
                            secondary={p.description}
                          />
                        </MenuItem>
                      ))
                    )}
                  </Select>
                  {!draft.project_id && (
                    <FormHelperText>Required</FormHelperText>
                  )}
                </FormControl>
              ) : (
                <ViewField label="Project">
                  {endpoint.project_id ? (
                    <Link
                      href={`/projects/${endpoint.project_id}`}
                      style={{ color: 'inherit', fontWeight: 500 }}
                    >
                      {projectName}
                    </Link>
                  ) : (
                    'No project assigned'
                  )}
                </ViewField>
              )}
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Name"
                  value={draft.name}
                  onChange={e =>
                    setDraft(prev => ({ ...prev, name: e.target.value }))
                  }
                />
              ) : (
                <ViewField label="Name" value={endpoint.name} />
              )}
            </Grid>

            <Grid size={12}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Description"
                  value={draft.description}
                  onChange={e =>
                    setDraft(prev => ({
                      ...prev,
                      description: e.target.value,
                    }))
                  }
                  multiline
                  minRows={3}
                />
              ) : (
                <ViewField
                  label="Description"
                  value={endpoint.description || 'No description provided'}
                  multiline
                />
              )}
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              {isEditing ? (
                <FormControl fullWidth>
                  <InputLabel>Environment</InputLabel>
                  <Select
                    value={draft.environment}
                    label="Environment"
                    onChange={e =>
                      setDraft(prev => ({
                        ...prev,
                        environment: e.target.value,
                      }))
                    }
                  >
                    {ENVIRONMENTS.map(env => (
                      <MenuItem key={env} value={env}>
                        {formatEnvironment(env)}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ) : (
                <ViewField label="Environment">
                  <GridBadge
                    size="detail"
                    label={formatEnvironment(endpoint.environment)}
                  />
                </ViewField>
              )}
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              {isEditing ? (
                <Box>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={draft.disable_tracing}
                        onChange={e =>
                          setDraft(prev => ({
                            ...prev,
                            disable_tracing: e.target.checked,
                          }))
                        }
                      />
                    }
                    label="Disable tracing"
                  />
                  <FormHelperText>
                    When enabled, invocations will not generate traces or
                    telemetry
                  </FormHelperText>
                </Box>
              ) : (
                <ViewField label="Tracing">
                  <GridBadge
                    size="detail"
                    label={endpoint.disable_tracing ? 'Disabled' : 'Enabled'}
                  />
                </ViewField>
              )}
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <ViewField label="Connection type">
                <GridBadge size="detail" label={endpoint.connection_type} />
              </ViewField>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <ViewField label="Status">
                <GridBadge
                  size="detail"
                  label={endpoint.status?.name ?? 'Unknown'}
                />
              </ViewField>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <ViewField label="Config source">
                <GridBadge
                  size="detail"
                  label={formatConfigSource(endpoint.config_source)}
                />
              </ViewField>
            </Grid>
          </Grid>
        )}
      </EditableSection>
    </Box>
  );
}
