'use client';

import Link from 'next/link';
import { useMemo } from 'react';
import {
  Box,
  FormControlLabel,
  FormHelperText,
  Grid,
  MenuItem,
  Select,
  Switch,
  TextField,
  FormControl,
  InputLabel,
} from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import EditableSection from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useEndpointDetailContext } from './EndpointDetailContext';
import { ENVIRONMENTS } from './endpoint-detail-shared';
import {
  connectionTarget,
  detailGridSpacing,
  formatConfigSource,
  formatEnvironment,
} from './endpoint-overview-utils';

interface IdentityDraft {
  name: string;
  description: string;
}

interface ProjectDraft {
  environment: string;
  disable_tracing: boolean;
}

function identityFromEndpoint(endpoint: {
  name: string;
  description?: string;
}): IdentityDraft {
  return {
    name: endpoint.name,
    description: endpoint.description || '',
  };
}

function projectFromEndpoint(endpoint: {
  environment: string;
  disable_tracing?: boolean;
}): ProjectDraft {
  return {
    environment: endpoint.environment,
    disable_tracing: endpoint.disable_tracing ?? false,
  };
}

export default function EndpointOverviewTab() {
  const { endpoint, projects, saveFields } = useEndpointDetailContext();
  const target = connectionTarget(endpoint);

  const identityInitial = useMemo(
    () => identityFromEndpoint(endpoint),
    [endpoint]
  );
  const projectInitial = useMemo(
    () => projectFromEndpoint(endpoint),
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
        title="Endpoint details"
        initialValue={identityInitial}
        onSave={async draft => {
          await saveFields({
            name: draft.name,
            description: draft.description,
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
            <Grid size={{ xs: 12, md: 6 }}>
              <ViewField label="Connection type">
                <GridBadge size="detail" label={endpoint.connection_type} />
              </ViewField>
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

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <ViewField label="Status">
                <GridBadge
                  size="detail"
                  label={endpoint.status?.name ?? 'Unknown'}
                />
              </ViewField>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <ViewField label="Config source">
                <GridBadge
                  size="detail"
                  label={formatConfigSource(endpoint.config_source)}
                />
              </ViewField>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <ViewField label="Environment">
                <GridBadge
                  size="detail"
                  label={formatEnvironment(endpoint.environment)}
                />
              </ViewField>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              {endpoint.connection_type === 'REST' && endpoint.method ? (
                <ViewField label="Method">
                  <GridBadge size="detail" label={endpoint.method} />
                </ViewField>
              ) : (
                <ViewField label="Method" value="—" />
              )}
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
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
            </Grid>

            <Grid size={12}>
              <ViewField
                label="Target"
                value={target}
                inputSx={{
                  fontFamily:
                    endpoint.connection_type === 'SDK' ? 'monospace' : 'inherit',
                  wordBreak: 'break-all',
                }}
              />
            </Grid>
          </Grid>
        )}
      </EditableSection>

      <EditableSection
        title="Project and environment"
        initialValue={projectInitial}
        onSave={async draft => {
          await saveFields({
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
              <ViewField label="Project" value={projectName} />
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
                <ViewField
                  label="Environment"
                  value={formatEnvironment(endpoint.environment)}
                />
              )}
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              {isEditing ? (
                <>
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
                </>
              ) : (
                <ViewField label="Tracing">
                  <GridBadge
                    size="detail"
                    label={endpoint.disable_tracing ? 'Disabled' : 'Enabled'}
                  />
                </ViewField>
              )}
            </Grid>
          </Grid>
        )}
      </EditableSection>
    </Box>
  );
}
