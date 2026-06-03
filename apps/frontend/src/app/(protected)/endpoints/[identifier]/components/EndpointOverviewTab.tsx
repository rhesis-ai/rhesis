'use client';

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
  Typography,
  FormControl,
  InputLabel,
} from '@mui/material';
import GridBadge from '@/components/common/GridBadge';
import EditableSection from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useEndpointDetailContext } from './EndpointDetailContext';
import { ENVIRONMENTS } from './endpoint-detail-shared';

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

  const identityInitial = useMemo(
    () => identityFromEndpoint(endpoint),
    [endpoint]
  );
  const projectInitial = useMemo(
    () => projectFromEndpoint(endpoint),
    [endpoint]
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <EditableSection
        title="Identity"
        initialValue={identityInitial}
        onSave={async draft => {
          await saveFields({
            name: draft.name,
            description: draft.description,
          });
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <Grid container spacing={2}>
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
                  minRows={2}
                />
              ) : (
                <ViewField
                  label="Description"
                  value={endpoint.description || 'No description provided'}
                />
              )}
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
          <Grid container spacing={2}>
            {/* Project is immutable after creation — always shown read-only */}
            <Grid size={12}>
              <ViewField
                label="Project"
                value={
                  endpoint.project_id
                    ? projects[endpoint.project_id]?.name ||
                      endpoint.project?.name ||
                      'Loading project...'
                    : 'No project assigned'
                }
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
                        {env}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ) : (
                <ViewField
                  label="Environment"
                  value={
                    endpoint.environment.charAt(0).toUpperCase() +
                    endpoint.environment.slice(1)
                  }
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
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Tracing
                  </Typography>
                  <Box sx={{ mt: 0.5, display: 'flex', gap: 1 }}>
                    <GridBadge
                      size="detail"
                      label={endpoint.disable_tracing ? 'Disabled' : 'Enabled'}
                    />
                  </Box>
                </Box>
              )}
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="caption" color="text.secondary">
                Status
              </Typography>
              <Box sx={{ mt: 0.5, display: 'flex', gap: 1 }}>
                <GridBadge
                  size="detail"
                  label={endpoint.status?.name ?? 'Unknown'}
                />
              </Box>
            </Grid>
          </Grid>
        )}
      </EditableSection>
    </Box>
  );
}
