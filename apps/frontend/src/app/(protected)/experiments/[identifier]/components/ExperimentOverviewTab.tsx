'use client';

import * as React from 'react';
import { useCallback, useMemo } from 'react';
import {
  Box,
  Chip,
  Grid,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import Link from 'next/link';
import EditableSection from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { SectionCard } from '@/components/common/SectionCard';
import {
  ArrowOutwardIcon,
  PublicIcon,
  PublicOffIcon,
} from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentDetail,
  ExperimentVisibility,
  ProjectEnvironments,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { useNotifications } from '@/components/common/NotificationContext';

interface IdentityDraft {
  description: string;
  visibility: ExperimentVisibility;
}

interface ExperimentOverviewTabProps {
  experiment: ExperimentDetail;
  environments: ProjectEnvironments | null;
  sessionToken: string;
  onUpdated: (updated: ExperimentDetail) => void;
  onUnbindEnvironment: (name: string) => void;
}

export default function ExperimentOverviewTab({
  experiment,
  environments,
  sessionToken,
  onUpdated,
  onUnbindEnvironment,
}: ExperimentOverviewTabProps) {
  const notifications = useNotifications();

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const identityInitial: IdentityDraft = useMemo(
    () => ({
      description: experiment.description ?? '',
      visibility: experiment.visibility,
    }),
    [experiment]
  );

  const handleSaveIdentity = useCallback(
    async (draft: IdentityDraft) => {
      const patch: Partial<{
        description: string | null;
        visibility: ExperimentVisibility;
      }> = {};
      const trimmedDesc = draft.description.trim();
      if (trimmedDesc !== (experiment.description ?? ''))
        patch.description = trimmedDesc || null;
      if (draft.visibility !== experiment.visibility)
        patch.visibility = draft.visibility;
      if (Object.keys(patch).length === 0) return;
      const client = apiFactory.getParametersClient();
      const updated = await client.patchExperiment(experiment.id, patch);
      onUpdated(updated as unknown as ExperimentDetail);
      notifications.show('Experiment updated', { severity: 'success' });
    },
    [apiFactory, experiment, notifications, onUpdated]
  );

  const environmentsForExperiment = useMemo(() => {
    if (!environments) return [] as string[];
    return Object.entries(environments.environments)
      .filter(([, ptr]) => ptr !== null && ptr.experiment_id === experiment.id)
      .map(([name]) => name);
  }, [environments, experiment]);

  const latestVersion = experiment.versions[experiment.versions.length - 1];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <EditableSection
        title="Experiment Overview"
        initialValue={identityInitial}
        onSave={handleSaveIdentity}
      >
        {({ draft, setDraft, isEditing }) => (
          <Grid container spacing={2}>
            {/* Description — full width so it never sits beside a differently-styled field */}
            <Grid size={12}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="Description"
                  value={draft.description}
                  onChange={e =>
                    setDraft(prev => ({ ...prev, description: e.target.value }))
                  }
                />
              ) : (
                <ViewField
                  label="Description"
                  value={experiment.description || undefined}
                />
              )}
            </Grid>
            {/* Project (always read-only) and Visibility — same row, consistent display */}
            <Grid size={{ xs: 12, md: 6 }}>
              <ViewField label="Project">
                <Box
                  component={Link}
                  href={`/projects/${experiment.project_id}?tab=parameters`}
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.5,
                    fontSize: 16,
                    lineHeight: '24px',
                    color: theme => theme.palette.greyscale.body,
                    textDecoration: 'none',
                    '&:hover': { textDecoration: 'underline' },
                  }}
                >
                  {experiment.project?.name ?? experiment.project_id}
                  <ArrowOutwardIcon sx={{ fontSize: 14, opacity: 0.7 }} />
                </Box>
              </ViewField>
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              {isEditing ? (
                <Box>
                  <Typography
                    sx={{
                      fontSize: 14,
                      color: 'text.secondary',
                      px: '14px',
                      mb: '6px',
                    }}
                  >
                    Visibility
                  </Typography>
                  <ToggleButtonGroup
                    value={draft.visibility}
                    exclusive
                    size="small"
                    onChange={(_, value: ExperimentVisibility | null) => {
                      if (value)
                        setDraft(prev => ({ ...prev, visibility: value }));
                    }}
                    aria-label="experiment visibility"
                    sx={{
                      '& .MuiToggleButton-root': {
                        px: 2,
                        py: 0.5,
                        gap: 0.75,
                        textTransform: 'none',
                        fontWeight: 500,
                      },
                      '& .MuiToggleButton-root.Mui-selected': {
                        bgcolor: 'primary.main',
                        color: 'primary.contrastText',
                        '&:hover': { bgcolor: 'primary.dark' },
                      },
                    }}
                  >
                    <ToggleButton value="private" aria-label="Private">
                      <PublicOffIcon fontSize="small" />
                      Private
                    </ToggleButton>
                    <ToggleButton value="shared" aria-label="Shared">
                      <PublicIcon fontSize="small" />
                      Shared
                    </ToggleButton>
                  </ToggleButtonGroup>
                </Box>
              ) : (
                <ViewField
                  label="Visibility"
                  value={
                    experiment.visibility === 'shared' ? 'Shared' : 'Private'
                  }
                />
              )}
            </Grid>
            {environmentsForExperiment.length > 0 && (
              <Grid size={12}>
                <Typography
                  sx={{
                    fontSize: 14,
                    color: 'text.secondary',
                    px: '14px',
                    mb: '6px',
                  }}
                >
                  Active Environments
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {environmentsForExperiment.map(name => (
                    <Chip
                      key={name}
                      color="success"
                      variant="outlined"
                      size="small"
                      label={name}
                      onDelete={() => onUnbindEnvironment(name)}
                    />
                  ))}
                </Box>
              </Grid>
            )}
          </Grid>
        )}
      </EditableSection>

      <SectionCard title="Experiment Iterations">
        <Grid container spacing={2}>
          <Grid size={{ xs: 6, md: 3 }}>
            <ViewField
              label="Latest Version"
              value={
                latestVersion ? shortVersion(latestVersion.version) : undefined
              }
            />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <ViewField
              label="Total Versions"
              value={String(
                experiment.versions_count ?? experiment.versions.length
              )}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <ViewField
              label="Last Saved"
              value={
                latestVersion
                  ? new Date(latestVersion.created_at).toLocaleString()
                  : undefined
              }
            />
          </Grid>
        </Grid>
      </SectionCard>
    </Box>
  );
}
