'use client';

import { useMemo } from 'react';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import {
  Box,
  FormControlLabel,
  FormHelperText,
  Grid,
  MenuItem,
  Select,
  Switch,
  FormControl,
  InputLabel,
} from '@mui/material';
import { SECTION_GRID } from '@/styles/theme-constants';
import GridBadge from '@/components/common/GridBadge';
import EditableSection from '@/components/common/EditableSection';
import EditableField from '@/components/common/EditableField';
import ViewField from '@/components/common/ViewField';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useEndpointDetailContext } from './EndpointDetailContext';
import { ENVIRONMENTS } from './endpoint-detail-shared';
import {
  formatConfigSource,
  formatEnvironment,
} from './endpoint-overview-utils';

interface EndpointDetailsDraft {
  name: string;
  description: string;
  environment: string;
  disable_tracing: boolean;
}

function detailsFromEndpoint(endpoint: {
  name: string;
  description?: string;
  environment: string;
  disable_tracing?: boolean;
}): EndpointDetailsDraft {
  return {
    name: endpoint.name,
    description: endpoint.description || '',
    environment: endpoint.environment,
    disable_tracing: endpoint.disable_tracing ?? false,
  };
}

export default function EndpointOverviewTab() {
  const { endpoint, projects, saveFields } = useEndpointDetailContext();
  const canEditEndpoint = useCan(Capability.Endpoint.UPDATE);

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
            environment: draft.environment as Endpoint['environment'],
            disable_tracing: draft.disable_tracing,
          });
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <Grid
            container
            columnSpacing={SECTION_GRID.columnSpacing}
            rowSpacing={SECTION_GRID.rowSpacing}
          >
            <Grid size={{ xs: 12, md: 6 }}>
              <EditableField
                fullWidth
                editing={isEditing}
                label="Name"
                value={isEditing ? draft.name : endpoint.name}
                onChange={e =>
                  setDraft(prev => ({ ...prev, name: e.target.value }))
                }
              />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <EditableField
                fullWidth
                editing={false}
                label="Project"
                value={projectName}
              />
            </Grid>

            <Grid size={12}>
              <EditableField
                fullWidth
                editing={isEditing}
                label="Description"
                value={
                  isEditing
                    ? draft.description
                    : endpoint.description || 'No description provided'
                }
                onChange={e =>
                  setDraft(prev => ({
                    ...prev,
                    description: e.target.value,
                  }))
                }
                multiline
                minRows={3}
              />
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
