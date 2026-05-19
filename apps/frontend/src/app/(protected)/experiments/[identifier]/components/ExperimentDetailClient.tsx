'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import { useRouter } from 'next/navigation';
import { PageContainer, Breadcrumb } from '@toolpad/core/PageContainer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentDetail,
  ExperimentVersion,
  ParameterSchema,
  ParameterValue,
  ProjectEnvironments,
} from '@/utils/api-client/interfaces/parameters';
import {
  DeleteIcon,
  PromoteIcon,
  PublicIcon,
  PublicOffIcon,
  SaveIcon,
} from '@/components/icons';
import { useNotifications } from '@/components/common/NotificationContext';
import TypedValueEditor from './TypedValueEditor';
import VersionHistory from './VersionHistory';
import PromoteEnvironmentDialog from './PromoteEnvironmentDialog';
import LatestResultsPanel from './LatestResultsPanel';

interface ExperimentDetailClientProps {
  experimentId: string;
  sessionToken: string;
}

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
      id={`experiment-tabpanel-${index}`}
      aria-labelledby={`experiment-tab-${index}`}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

function defaultsForSchema(
  schema: ParameterSchema
): Record<string, ParameterValue | null> {
  const out: Record<string, ParameterValue | null> = {};
  for (const field of schema.fields) {
    out[field.name] = field.default ?? null;
  }
  return out;
}

function valuesFromVersion(
  version: ExperimentVersion | undefined,
  schema: ParameterSchema
): Record<string, ParameterValue | null> {
  const base = defaultsForSchema(schema);
  if (!version) return base;
  for (const [name, value] of Object.entries(version.values)) {
    base[name] = value as ParameterValue;
  }
  return base;
}

/**
 * Detail page for one experiment.
 *
 * Three concerns sit on the same page so the user doesn't context-
 * switch:
 *
 * 1. Header (name, description, visibility toggle, delete).
 * 2. "Edit" tab: typed form rendered from the project schema.
 *    Saving submits a new version (idempotent on identical values).
 * 3. "Versions" tab: history list + per-row Promote action and
 *    typed before/after diff vs the previous version.
 *
 * Visibility flips and environment promotions both have guard rails — the
 * backend rejects unsharing while an environment points here, and environments
 * can only target shared experiments. The UI surfaces both as
 * disabled affordances rather than catching the 409 after the fact.
 */
export default function ExperimentDetailClient({
  experimentId,
  sessionToken,
}: ExperimentDetailClientProps) {
  const router = useRouter();
  const notifications = useNotifications();

  const [experiment, setExperiment] = useState<ExperimentDetail | null>(null);
  const [schema, setSchema] = useState<ParameterSchema | null>(null);
  const [environments, setEnvironments] = useState<ProjectEnvironments | null>(
    null
  );
  const [draft, setDraft] = useState<
    Record<string, ParameterValue | null>
  >({});
  const [message, setMessage] = useState<string>('');
  const [tab, setTab] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [promotePrefill, setPromotePrefill] = useState<{
    environment?: string;
    version?: string;
  }>({});

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const client = apiFactory.getParametersClient();
      const detail = await client.getExperiment(experimentId);
      setExperiment(detail);
      const schemaResp = await client.getSchema(detail.project_id);
      setSchema(schemaResp);
      const environmentsResp = await client.getEnvironments(detail.project_id);
      setEnvironments(environmentsResp);
      const latest = detail.versions[detail.versions.length - 1];
      setDraft(valuesFromVersion(latest, schemaResp));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load experiment');
    } finally {
      setLoading(false);
    }
  }, [apiFactory, experimentId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const environmentsForExperiment = useMemo(() => {
    if (!environments || !experiment) return [] as string[];
    return Object.entries(environments.environments)
      .filter(([, ptr]) => ptr !== null && ptr.experiment_id === experiment.id)
      .map(([name]) => name);
  }, [environments, experiment]);

  const updateDraft = useCallback(
    (name: string, value: ParameterValue | null) => {
      setDraft(prev => ({ ...prev, [name]: value }));
    },
    []
  );

  const handleSaveVersion = useCallback(async () => {
    if (!experiment || !schema) return;
    setSaving(true);
    try {
      const payloadValues: Record<string, unknown> = {};
      for (const [name, value] of Object.entries(draft)) {
        if (value !== null) {
          payloadValues[name] = value;
        }
      }
      const client = apiFactory.getParametersClient();
      await client.createExperimentVersion(experiment.id, {
        values: payloadValues,
        message: message.trim() || undefined,
      });
      notifications.show('Version saved', { severity: 'success' });
      setMessage('');
      await refresh();
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to save version',
        { severity: 'error' }
      );
    } finally {
      setSaving(false);
    }
  }, [apiFactory, draft, experiment, message, notifications, refresh, schema]);

  const handleVisibilityToggle = useCallback(async () => {
    if (!experiment) return;
    const next =
      experiment.visibility === 'shared' ? 'private' : 'shared';
    try {
      const client = apiFactory.getParametersClient();
      const updated = await client.patchExperiment(experiment.id, {
        visibility: next,
      });
      setExperiment(updated);
      notifications.show(
        next === 'shared'
          ? 'Experiment is now shared with the project'
          : 'Experiment is now private',
        { severity: 'success' }
      );
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to update visibility',
        { severity: 'error' }
      );
    }
  }, [apiFactory, experiment, notifications]);

  const handleDelete = useCallback(async () => {
    if (!experiment) return;
    if (
      !window.confirm(
        `Delete experiment "${experiment.name}"? Versions will also be removed.`
      )
    ) {
      return;
    }
    try {
      const client = apiFactory.getParametersClient();
      await client.deleteExperiment(experiment.id);
      notifications.show('Experiment deleted', { severity: 'success' });
      router.push('/experiments');
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to delete experiment',
        { severity: 'error' }
      );
    }
  }, [apiFactory, experiment, notifications, router]);

  const handlePromote = useCallback(
    (version?: string, environment?: string) => {
      setPromotePrefill({ version, environment });
      setPromoteOpen(true);
    },
    []
  );

  const handleUnbindEnvironment = useCallback(
    async (environmentName: string) => {
      if (!experiment) return;
      try {
        const client = apiFactory.getParametersClient();
        const next = await client.deleteEnvironment(
          experiment.project_id,
          environmentName
        );
        setEnvironments(next);
        notifications.show(`Environment "${environmentName}" unbound`, {
          severity: 'success',
        });
      } catch (e) {
        notifications.show(
          e instanceof Error ? e.message : 'Failed to unbind environment',
          { severity: 'error' }
        );
      }
    },
    [apiFactory, experiment, notifications]
  );

  // Inline editing for name and description
  const [editingName, setEditingName] = useState(false);
  const [editingDescription, setEditingDescription] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');

  const handleStartEditName = useCallback(() => {
    if (!experiment) return;
    setEditName(experiment.name);
    setEditingName(true);
  }, [experiment]);

  const handleStartEditDescription = useCallback(() => {
    if (!experiment) return;
    setEditDescription(experiment.description || '');
    setEditingDescription(true);
  }, [experiment]);

  const handleSaveName = useCallback(async () => {
    if (!experiment) return;
    const trimmed = editName.trim();
    if (!trimmed || trimmed === experiment.name) {
      setEditingName(false);
      return;
    }
    try {
      const client = apiFactory.getParametersClient();
      const updated = await client.patchExperiment(experiment.id, {
        name: trimmed,
      });
      setExperiment(updated);
      notifications.show('Name updated', { severity: 'success' });
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to update name',
        { severity: 'error' }
      );
    } finally {
      setEditingName(false);
    }
  }, [apiFactory, editName, experiment, notifications]);

  const handleSaveDescription = useCallback(async () => {
    if (!experiment) return;
    const trimmed = editDescription.trim();
    if (trimmed === (experiment.description || '')) {
      setEditingDescription(false);
      return;
    }
    try {
      const client = apiFactory.getParametersClient();
      const updated = await client.patchExperiment(experiment.id, {
        description: trimmed || null,
      });
      setExperiment(updated);
      notifications.show('Description updated', { severity: 'success' });
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to update description',
        { severity: 'error' }
      );
    } finally {
      setEditingDescription(false);
    }
  }, [apiFactory, editDescription, experiment, notifications]);

  const breadcrumbs: Breadcrumb[] = useMemo(() => {
    if (!experiment) return [];
    return [
      { title: 'Experiments', path: '/experiments' },
      {
        title: experiment.name || 'Experiment',
        path: `/experiments/${experiment.id}`,
      },
    ];
  }, [experiment]);

  if (loading) {
    return (
      <PageContainer title="Experiment" breadcrumbs={[]}>
        <Box sx={{ display: 'flex', alignItems: 'center', p: 3, gap: 2 }}>
          <CircularProgress size={20} />
          <Typography color="text.secondary">Loading experiment...</Typography>
        </Box>
      </PageContainer>
    );
  }

  if (error || !experiment || !schema) {
    return (
      <PageContainer title="Experiment" breadcrumbs={[]}>
        <Alert severity="error">{error ?? 'Experiment not found'}</Alert>
      </PageContainer>
    );
  }

  const isShared = experiment.visibility === 'shared';

  return (
    <PageContainer title={experiment.name} breadcrumbs={breadcrumbs}>
      <Stack spacing={2} sx={{ mt: 1 }}>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={2}
            alignItems={{ md: 'center' }}
            justifyContent="space-between"
          >
            <Box>
              {editingName ? (
                <TextField
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  onBlur={handleSaveName}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleSaveName();
                    if (e.key === 'Escape') setEditingName(false);
                  }}
                  size="small"
                  autoFocus
                  fullWidth
                  sx={{ mb: 0.5 }}
                  InputProps={{ sx: { typography: 'h6' } }}
                />
              ) : (
                <Box
                  onClick={handleStartEditName}
                  sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.5,
                    cursor: 'pointer',
                    '&:hover .edit-icon': { opacity: 1 },
                  }}
                >
                  <Typography variant="h6">{experiment.name}</Typography>
                  <EditIcon
                    className="edit-icon"
                    sx={{ fontSize: 'body1.fontSize', opacity: 0, color: 'text.secondary' }}
                  />
                </Box>
              )}
              {editingDescription ? (
                <TextField
                  value={editDescription}
                  onChange={e => setEditDescription(e.target.value)}
                  onBlur={handleSaveDescription}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) handleSaveDescription();
                    if (e.key === 'Escape') setEditingDescription(false);
                  }}
                  size="small"
                  autoFocus
                  fullWidth
                  multiline
                  minRows={1}
                  placeholder="Add a description..."
                />
              ) : (
                <Box
                  onClick={handleStartEditDescription}
                  sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.5,
                    cursor: 'pointer',
                    '&:hover .edit-icon': { opacity: 1 },
                  }}
                >
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ fontStyle: experiment.description ? 'normal' : 'italic' }}
                  >
                    {experiment.description || 'Add a description...'}
                  </Typography>
                  <EditIcon
                    className="edit-icon"
                    sx={{ fontSize: 'caption.fontSize', opacity: 0, color: 'text.secondary' }}
                  />
                </Box>
              )}
              <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                <Chip
                  size="small"
                  label={experiment.visibility}
                  color={isShared ? 'primary' : 'default'}
                  variant="outlined"
                />
                <Chip
                  size="small"
                  label={`${experiment.versions_count} version${
                    experiment.versions_count === 1 ? '' : 's'
                  }`}
                />
                {environmentsForExperiment.map(name => (
                  <Chip
                    key={name}
                    size="small"
                    color="success"
                    label={`environment: ${name}`}
                    onDelete={() => handleUnbindEnvironment(name)}
                  />
                ))}
              </Stack>
            </Box>
            <Stack direction="row" spacing={1}>
              <Tooltip
                title={
                  isShared
                    ? 'Make this experiment private — fails if an environment points at it'
                    : 'Share with the project so it can be promoted to an environment'
                }
              >
                <Button
                  startIcon={isShared ? <PublicOffIcon /> : <PublicIcon />}
                  onClick={handleVisibilityToggle}
                  variant="outlined"
                >
                  {isShared ? 'Make private' : 'Share'}
                </Button>
              </Tooltip>
              <Tooltip
                title={
                  isShared
                    ? 'Promote a version to a project environment'
                    : 'Share the experiment first to promote it to an environment'
                }
              >
                <span>
                  <Button
                    startIcon={<PromoteIcon />}
                    onClick={() => handlePromote()}
                    variant="contained"
                    disabled={!isShared || experiment.versions.length === 0}
                  >
                    Promote
                  </Button>
                </span>
              </Tooltip>
              <Tooltip title="Delete experiment">
                <IconButton onClick={handleDelete} color="error">
                  <DeleteIcon />
                </IconButton>
              </Tooltip>
            </Stack>
          </Stack>
        </Paper>

        <Paper variant="outlined">
          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tabs
              value={tab}
              onChange={(_, v) => setTab(v)}
              aria-label="experiment sections"
            >
              <Tab label="Edit values" />
              <Tab
                label={`Version history (${experiment.versions.length})`}
              />
            </Tabs>
          </Box>

          <TabPanel value={tab} index={0}>
            <Stack spacing={2}>
              {schema.fields.length === 0 ? (
                <Alert severity="info">
                  This project has no parameter schema yet. Define one
                  on the project page before saving experiment values.
                </Alert>
              ) : (
                <>
                  <Stack spacing={2}>
                    {schema.fields.map(field => (
                      <TypedValueEditor
                        key={field.name}
                        field={field}
                        value={draft[field.name] ?? null}
                        onChange={value =>
                          updateDraft(field.name, value)
                        }
                      />
                    ))}
                  </Stack>
                  <Divider />
                  <Box
                    sx={{
                      display: 'flex',
                      gap: 2,
                      alignItems: 'flex-end',
                    }}
                  >
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Saving with identical values is a no-op (the
                        server returns the existing version). Use the
                        message field to label what changed.
                      </Typography>
                    </Box>
                    <Button
                      variant="contained"
                      startIcon={<SaveIcon />}
                      onClick={handleSaveVersion}
                      disabled={saving || schema.fields.length === 0}
                    >
                      {saving ? 'Saving...' : 'Save as new version'}
                    </Button>
                  </Box>
                </>
              )}
            </Stack>
          </TabPanel>

          <TabPanel value={tab} index={1}>
            <VersionHistory
              versions={experiment.versions}
              schema={schema}
              projectEnvironments={environments}
              experimentId={experiment.id}
              canPromote={isShared}
              onPromoteVersion={version => handlePromote(version)}
            />
          </TabPanel>
        </Paper>
      </Stack>

      <LatestResultsPanel
        experimentId={experiment.id}
        sessionToken={sessionToken}
      />

      {experiment && environments && (
        <PromoteEnvironmentDialog
          open={promoteOpen}
          onClose={() => setPromoteOpen(false)}
          sessionToken={sessionToken}
          projectId={experiment.project_id}
          experimentId={experiment.id}
          experimentName={experiment.name}
          versions={experiment.versions}
          currentEnvironments={environments}
          defaultVersion={
            promotePrefill.version ??
            experiment.versions[experiment.versions.length - 1]?.version
          }
          defaultEnvironment={promotePrefill.environment}
          onPromoted={async () => {
            setPromoteOpen(false);
            await refresh();
          }}
        />
      )}
    </PageContainer>
  );
}
