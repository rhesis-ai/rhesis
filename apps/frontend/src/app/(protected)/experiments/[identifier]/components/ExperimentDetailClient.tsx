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
  FormHelperText,
  Grid,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { DeleteModal } from '@/components/common/DeleteModal';
import EditIcon from '@mui/icons-material/EditOutlined';
import CancelIcon from '@mui/icons-material/CancelOutlined';
import CheckIcon from '@mui/icons-material/CheckOutlined';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { PageContainer, Breadcrumb } from '@toolpad/core/PageContainer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentDetail,
  ExperimentUpdate,
  ExperimentVisibility,
  ExperimentVersion,
  ParameterSchema,
  ParameterValue,
  ProjectEnvironments,
} from '@/utils/api-client/interfaces/parameters';
import {
  ArrowOutwardIcon,
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
import ProjectParameters from '@/app/(protected)/projects/[identifier]/components/ProjectParameters';

interface ExperimentDetailClientProps {
  experimentId: string;
  sessionToken: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  keepMounted?: boolean;
  value: number;
}

function TabPanel({
  children,
  value,
  index,
  keepMounted = false,
}: TabPanelProps) {
  const isActive = value === index;

  return (
    <div
      role="tabpanel"
      hidden={!isActive}
      id={`experiment-tabpanel-${index}`}
      aria-labelledby={`experiment-tab-${index}`}
    >
      {(isActive || keepMounted) && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const EXPERIMENT_TABS = [
  {
    label: 'Experiment',
    description:
      'Edit the parameters defined by the project schema and save them as a new immutable experiment version.',
  },
  {
    label: 'Parameters',
    description:
      'Configure the parameter schema for this project. Changes apply to all experiments.',
  },
  {
    label: 'Details',
    description:
      'Review and update the experiment metadata, visibility, and promoted environments.',
  },
] as const;

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
  const searchParams = useSearchParams();
  const notifications = useNotifications();
  const openVersion = searchParams.get('version');

  const [experiment, setExperiment] = useState<ExperimentDetail | null>(null);
  const [schema, setSchema] = useState<ParameterSchema | null>(null);
  const [environments, setEnvironments] = useState<ProjectEnvironments | null>(
    null
  );
  const [draft, setDraft] = useState<Record<string, ParameterValue | null>>({});
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
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const refresh = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent === true;
      // Only flip the full-page loader for the initial load. Save /
      // promote / etc. call ``refresh({ silent: true })`` so the page
      // shell stays mounted — otherwise the loading branch returns a
      // placeholder, which unmounts ``LatestResultsPanel`` and forces
      // it to refetch on remount (visible as a grid flicker).
      if (!silent) {
        setLoading(true);
      }
      setError(null);
      try {
        const client = apiFactory.getParametersClient();
        const detail = await client.getExperiment(experimentId);
        setExperiment(detail);
        const schemaResp = await client.getSchema(detail.project_id);
        setSchema(schemaResp);
        const environmentsResp = await client.getEnvironments(
          detail.project_id
        );
        setEnvironments(environmentsResp);
        const latest = detail.versions[detail.versions.length - 1];
        setDraft(valuesFromVersion(latest, schemaResp));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load experiment');
      } finally {
        if (!silent) {
          setLoading(false);
        }
      }
    },
    [apiFactory, experimentId]
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!loading && schema && schema.fields.length === 0) {
      setTab(1);
    }
  }, [loading, schema]);

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
      await refresh({ silent: true });
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to save version',
        { severity: 'error' }
      );
    } finally {
      setSaving(false);
    }
  }, [apiFactory, draft, experiment, message, notifications, refresh, schema]);

  const handleVisibilityToggle = useCallback(
    async (target?: ExperimentVisibility) => {
      if (!experiment) return;
      const next =
        target ?? (experiment.visibility === 'shared' ? 'private' : 'shared');
      if (next === experiment.visibility) return;
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
    },
    [apiFactory, experiment, notifications]
  );

  const handleDeleteRequest = useCallback(() => {
    setDeleteOpen(true);
  }, []);

  const handleDeleteCancel = useCallback(() => {
    if (isDeleting) return;
    setDeleteOpen(false);
  }, [isDeleting]);

  const handleDeleteConfirm = useCallback(async () => {
    if (!experiment) return;
    setIsDeleting(true);
    try {
      const client = apiFactory.getParametersClient();
      await client.deleteExperiment(experiment.id);
      notifications.show('Experiment deleted', { severity: 'success' });
      setDeleteOpen(false);
      router.push('/experiments');
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to delete experiment',
        { severity: 'error' }
      );
    } finally {
      setIsDeleting(false);
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

  // Details form draft values. The visible Details tab intentionally uses
  // the same always-editable form-control pattern as the Edit values tab.
  const [editingName, setEditingName] = useState(false);
  const [editingDescription, setEditingDescription] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [isUpdatingDetails, setIsUpdatingDetails] = useState(false);

  useEffect(() => {
    if (!experiment) return;
    if (!editingName) {
      setEditName(experiment.name);
    }
    if (!editingDescription) {
      setEditDescription(experiment.description ?? '');
    }
  }, [editingDescription, editingName, experiment]);

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

  const handleCancelEditName = useCallback(() => {
    setEditingName(false);
    setEditName(experiment?.name ?? '');
  }, [experiment]);

  const handleCancelEditDescription = useCallback(() => {
    setEditingDescription(false);
    setEditDescription(experiment?.description ?? '');
  }, [experiment]);

  const handleSaveName = useCallback(async () => {
    if (!experiment) return;
    const trimmed = editName.trim();
    if (!trimmed || trimmed === experiment.name) {
      setEditingName(false);
      return;
    }
    setIsUpdatingDetails(true);
    try {
      const client = apiFactory.getParametersClient();
      const updated = await client.patchExperiment(experiment.id, {
        name: trimmed,
      });
      setExperiment(updated);
      notifications.show('Name updated', { severity: 'success' });
      setEditingName(false);
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to update name',
        { severity: 'error' }
      );
    } finally {
      setIsUpdatingDetails(false);
    }
  }, [apiFactory, editName, experiment, notifications]);

  const handleSaveDescription = useCallback(async () => {
    if (!experiment) return;
    const trimmed = editDescription.trim();
    if (trimmed === (experiment.description || '')) {
      setEditingDescription(false);
      return;
    }
    setIsUpdatingDetails(true);
    try {
      const client = apiFactory.getParametersClient();
      const updated = await client.patchExperiment(experiment.id, {
        description: trimmed || null,
      });
      setExperiment(updated);
      notifications.show('Description updated', { severity: 'success' });
      setEditingDescription(false);
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to update description',
        { severity: 'error' }
      );
    } finally {
      setIsUpdatingDetails(false);
    }
  }, [apiFactory, editDescription, experiment, notifications]);

  const detailsDirty = useMemo(() => {
    if (!experiment) return false;
    return (
      editName.trim() !== experiment.name ||
      editDescription.trim() !== (experiment.description ?? '')
    );
  }, [editDescription, editName, experiment]);

  const handleDiscardDetails = useCallback(() => {
    if (!experiment) return;
    setEditName(experiment.name);
    setEditDescription(experiment.description ?? '');
  }, [experiment]);

  const handleSaveDetails = useCallback(async () => {
    if (!experiment) return;
    const trimmedName = editName.trim();
    const trimmedDescription = editDescription.trim();

    if (!trimmedName) {
      notifications.show('Experiment name is required', {
        severity: 'warning',
      });
      return;
    }

    const patch: ExperimentUpdate = {};
    if (trimmedName !== experiment.name) {
      patch.name = trimmedName;
    }
    if (trimmedDescription !== (experiment.description ?? '')) {
      patch.description = trimmedDescription || null;
    }
    if (Object.keys(patch).length === 0) return;

    setIsUpdatingDetails(true);
    try {
      const client = apiFactory.getParametersClient();
      const updated = await client.patchExperiment(experiment.id, patch);
      setExperiment(updated);
      notifications.show('Experiment details updated', {
        severity: 'success',
      });
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to update experiment details',
        { severity: 'error' }
      );
    } finally {
      setIsUpdatingDetails(false);
    }
  }, [apiFactory, editDescription, editName, experiment, notifications]);

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
      <Box sx={{ flexGrow: 1, pt: 3 }}>
        <Grid container spacing={3}>
          <Grid size={12}>
            {tab === -1 && (
              <Paper elevation={2} sx={{ p: 3, mb: 4 }}>
                {/* Action Buttons */}
                <Box
                  sx={{
                    display: 'flex',
                    gap: 2,
                    mb: 3,
                    alignItems: 'center',
                  }}
                >
                  <Tooltip
                    title={
                      isShared
                        ? 'Promote a version to a project environment'
                        : 'Share the experiment first to promote it to an environment'
                    }
                  >
                    <span>
                      <Button
                        variant="contained"
                        color="primary"
                        startIcon={<PromoteIcon />}
                        onClick={() => handlePromote()}
                        disabled={!isShared || experiment.versions.length === 0}
                      >
                        Promote
                      </Button>
                    </span>
                  </Tooltip>
                  <Tooltip
                    title={
                      isShared
                        ? 'Make this experiment private — fails if an environment points at it'
                        : 'Share with the project so it can be promoted to an environment'
                    }
                  >
                    <Button
                      variant="outlined"
                      startIcon={isShared ? <PublicOffIcon /> : <PublicIcon />}
                      onClick={() => handleVisibilityToggle()}
                    >
                      {isShared ? 'Make Private' : 'Share'}
                    </Button>
                  </Tooltip>
                  <Box sx={{ flex: 1 }} />
                  <Tooltip title="Delete experiment">
                    <Button
                      variant="text"
                      onClick={handleDeleteRequest}
                      aria-label="Delete experiment"
                      sx={{
                        minWidth: 'auto',
                        px: 1,
                        color: 'text.secondary',
                      }}
                    >
                      <DeleteIcon />
                    </Button>
                  </Tooltip>
                </Box>

                {/* Experiment Details */}
                <Box sx={{ mb: 3, position: 'relative' }}>
                  <Typography variant="h6" sx={{ mb: 2 }}>
                    Experiment Details
                  </Typography>

                  {/* Name Field */}
                  <Typography
                    variant="subtitle1"
                    sx={{ mb: 1, fontWeight: 'medium' }}
                  >
                    Name
                  </Typography>
                  {editingName ? (
                    <TextField
                      fullWidth
                      value={editName}
                      onChange={e => setEditName(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSaveName();
                        }
                      }}
                      sx={{ mb: 2 }}
                      autoFocus
                      disabled={isUpdatingDetails}
                    />
                  ) : (
                    <Box sx={{ position: 'relative', mb: 3 }}>
                      <Typography
                        component="pre"
                        variant="body2"
                        sx={{
                          whiteSpace: 'pre-wrap',
                          fontFamily: 'monospace',
                          bgcolor: 'action.hover',
                          color: 'text.primary',
                          borderRadius: theme =>
                            theme.shape.borderRadius * 0.25,
                          padding: 1,
                          paddingRight: theme => theme.spacing(10),
                          wordBreak: 'break-word',
                          minHeight: 'calc(2 * 1.4375em + 2 * 8px)',
                          display: 'flex',
                          alignItems: 'center',
                        }}
                      >
                        {experiment.name}
                      </Typography>
                      <Button
                        startIcon={<EditIcon />}
                        onClick={handleStartEditName}
                        sx={{
                          position: 'absolute',
                          top: 8,
                          right: 8,
                          zIndex: 1,
                          backgroundColor: theme =>
                            theme.palette.mode === 'dark'
                              ? 'rgba(0, 0, 0, 0.6)'
                              : 'rgba(255, 255, 255, 0.8)',
                          '&:hover': {
                            backgroundColor: theme =>
                              theme.palette.mode === 'dark'
                                ? 'rgba(0, 0, 0, 0.8)'
                                : 'rgba(255, 255, 255, 0.9)',
                          },
                        }}
                      >
                        Edit
                      </Button>
                    </Box>
                  )}
                  {editingName && (
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'flex-end',
                        gap: 1,
                        mb: 3,
                      }}
                    >
                      <Button
                        variant="outlined"
                        color="error"
                        startIcon={<CancelIcon />}
                        onClick={handleCancelEditName}
                        disabled={isUpdatingDetails}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="contained"
                        color="primary"
                        startIcon={<CheckIcon />}
                        onClick={handleSaveName}
                        disabled={isUpdatingDetails || !editName.trim()}
                      >
                        Confirm
                      </Button>
                    </Box>
                  )}

                  {/* Description Field */}
                  <Typography
                    variant="subtitle1"
                    sx={{ mb: 1, fontWeight: 'medium' }}
                  >
                    Description
                  </Typography>
                  {editingDescription ? (
                    <TextField
                      fullWidth
                      multiline
                      rows={4}
                      value={editDescription}
                      onChange={e => setEditDescription(e.target.value)}
                      sx={{ mb: 1 }}
                      autoFocus
                      disabled={isUpdatingDetails}
                    />
                  ) : (
                    <Box sx={{ position: 'relative' }}>
                      <Typography
                        component="pre"
                        variant="body2"
                        sx={{
                          whiteSpace: 'pre-wrap',
                          fontFamily: 'monospace',
                          bgcolor: 'action.hover',
                          color: 'text.primary',
                          borderRadius: theme =>
                            theme.shape.borderRadius * 0.25,
                          padding: 1,
                          minHeight: 'calc(4 * 1.4375em + 2 * 8px)',
                          paddingRight: theme => theme.spacing(10),
                          wordBreak: 'break-word',
                        }}
                      >
                        {experiment.description || ' '}
                      </Typography>
                      <Button
                        startIcon={<EditIcon />}
                        onClick={handleStartEditDescription}
                        sx={{
                          position: 'absolute',
                          top: 8,
                          right: 8,
                          zIndex: 1,
                          backgroundColor: theme =>
                            theme.palette.mode === 'dark'
                              ? 'rgba(0, 0, 0, 0.6)'
                              : 'rgba(255, 255, 255, 0.8)',
                          '&:hover': {
                            backgroundColor: theme =>
                              theme.palette.mode === 'dark'
                                ? 'rgba(0, 0, 0, 0.8)'
                                : 'rgba(255, 255, 255, 0.9)',
                          },
                        }}
                      >
                        Edit
                      </Button>
                    </Box>
                  )}
                </Box>

                {editingDescription && (
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'flex-end',
                      gap: 1,
                      mb: 3,
                    }}
                  >
                    <Button
                      variant="outlined"
                      color="error"
                      startIcon={<CancelIcon />}
                      onClick={handleCancelEditDescription}
                      disabled={isUpdatingDetails}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="contained"
                      color="primary"
                      startIcon={<CheckIcon />}
                      onClick={handleSaveDescription}
                      disabled={isUpdatingDetails}
                    >
                      Confirm
                    </Button>
                  </Box>
                )}

                {/* Visibility */}
                <Box sx={{ mb: 3 }}>
                  <Typography
                    variant="subtitle1"
                    sx={{ mb: 1, fontWeight: 'medium' }}
                  >
                    Visibility
                  </Typography>
                  <Chip
                    label={experiment.visibility}
                    color={isShared ? 'primary' : 'default'}
                    variant="outlined"
                    size="medium"
                    sx={{ fontWeight: 'medium' }}
                  />
                </Box>

                {/* Active Environments */}
                {environmentsForExperiment.length > 0 && (
                  <Box sx={{ mb: 1 }}>
                    <Typography
                      variant="subtitle1"
                      sx={{ mb: 1, fontWeight: 'medium' }}
                    >
                      Active Environments
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {environmentsForExperiment.map(name => (
                        <Chip
                          key={name}
                          color="success"
                          variant="outlined"
                          size="medium"
                          label={name}
                          onDelete={() => handleUnbindEnvironment(name)}
                        />
                      ))}
                    </Box>
                  </Box>
                )}
              </Paper>
            )}

            {/* Experiment tabs -- mirrors the project detail page
                tab control so this and ``LatestResultsPanel`` below it
                share the same outlined-Paper-plus-description-hint look. */}
            <Paper variant="outlined" sx={{ mb: 4 }}>
              <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                <Tabs
                  value={tab}
                  onChange={(_, v) => setTab(v)}
                  aria-label="experiment sections"
                >
                  {EXPERIMENT_TABS.map(t => (
                    <Tab key={t.label} label={t.label} />
                  ))}
                </Tabs>
              </Box>

              <TabPanel value={tab} index={2}>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 2 }}
                >
                  {EXPERIMENT_TABS[2].description}
                </Typography>
                <Paper elevation={2} sx={{ p: 2 }}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      mb: 2,
                    }}
                  >
                    <Typography
                      variant="subtitle1"
                      sx={{ fontWeight: 'medium' }}
                    >
                      Overview
                    </Typography>
                    <Tooltip title="Delete experiment">
                      <Button
                        variant="text"
                        color="error"
                        onClick={handleDeleteRequest}
                        aria-label="Delete experiment"
                        sx={{ minWidth: 'auto', px: 1 }}
                      >
                        <DeleteIcon />
                      </Button>
                    </Tooltip>
                  </Box>
                  <Stack spacing={2}>
                    <TextField
                      label="Name"
                      value={editName}
                      onChange={e => setEditName(e.target.value)}
                      size="small"
                      fullWidth
                      disabled={isUpdatingDetails}
                      error={!editName.trim()}
                      helperText={
                        !editName.trim() ? 'Name is required' : undefined
                      }
                    />
                    <TextField
                      label="Description"
                      value={editDescription}
                      onChange={e => setEditDescription(e.target.value)}
                      size="small"
                      fullWidth
                      multiline
                      minRows={3}
                      disabled={isUpdatingDetails}
                    />
                  </Stack>

                  <Box sx={{ mb: 3, mt: 3 }}>
                    <Typography
                      variant="subtitle1"
                      sx={{ mb: 1, fontWeight: 'medium' }}
                    >
                      Project
                    </Typography>
                    <Button
                      component={Link}
                      href={`/projects/${experiment.project_id}?tab=parameters`}
                      target="_blank"
                      rel="noopener noreferrer"
                      size="small"
                      sx={{
                        borderRadius: theme => theme.shape.borderRadius,
                        backgroundColor: 'background.paper',
                        color: 'text.secondary',
                        border: '1px solid',
                        borderColor: 'divider',
                        px: 2,
                        py: 0.5,
                        '&:hover': {
                          backgroundColor: 'action.hover',
                          color: 'text.primary',
                          borderColor: 'primary.main',
                        },
                      }}
                      endIcon={<ArrowOutwardIcon fontSize="small" />}
                    >
                      {experiment.project?.name ?? experiment.project_id}
                    </Button>
                  </Box>

                  <Box sx={{ mb: 3, mt: 3 }}>
                    <Typography
                      variant="subtitle1"
                      sx={{ mb: 1, fontWeight: 'medium' }}
                    >
                      Visibility
                    </Typography>
                    <ToggleButtonGroup
                      value={experiment.visibility}
                      exclusive
                      size="small"
                      onChange={(_, value: ExperimentVisibility | null) => {
                        if (value) {
                          handleVisibilityToggle(value);
                        }
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
                          '&:hover': {
                            bgcolor: 'primary.dark',
                          },
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

                  {environmentsForExperiment.length > 0 && (
                    <Box>
                      <Typography
                        variant="subtitle1"
                        sx={{ mb: 1, fontWeight: 'medium' }}
                      >
                        Active Environments
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {environmentsForExperiment.map(name => (
                          <Chip
                            key={name}
                            color="success"
                            variant="outlined"
                            size="medium"
                            label={name}
                            onDelete={() => handleUnbindEnvironment(name)}
                          />
                        ))}
                      </Box>
                    </Box>
                  )}
                  <Divider sx={{ my: 3 }} />
                  <Box
                    sx={{
                      display: 'flex',
                      gap: 1,
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                    }}
                  >
                    {detailsDirty && (
                      <Button
                        variant="outlined"
                        color="error"
                        startIcon={<CancelIcon />}
                        onClick={handleDiscardDetails}
                        disabled={isUpdatingDetails}
                      >
                        Discard
                      </Button>
                    )}
                    <Button
                      variant="contained"
                      startIcon={<SaveIcon />}
                      onClick={handleSaveDetails}
                      disabled={
                        !detailsDirty || isUpdatingDetails || !editName.trim()
                      }
                    >
                      {isUpdatingDetails ? 'Saving...' : 'Save changes'}
                    </Button>
                  </Box>
                </Paper>
              </TabPanel>

              <TabPanel value={tab} index={0}>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 2 }}
                >
                  {EXPERIMENT_TABS[0].description}
                </Typography>
                <Paper elevation={2} sx={{ p: 2 }}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      mb: 2,
                    }}
                  >
                    <Typography
                      variant="subtitle1"
                      sx={{ fontWeight: 'medium' }}
                    >
                      Define values
                    </Typography>
                    <Button
                      component={Link}
                      href={`/projects/${experiment.project_id}?tab=parameters`}
                      target="_blank"
                      rel="noopener noreferrer"
                      size="small"
                      sx={{
                        borderRadius: theme => theme.shape.borderRadius,
                        backgroundColor: 'background.paper',
                        color: 'text.secondary',
                        border: '1px solid',
                        borderColor: 'divider',
                        px: 2,
                        py: 0.5,
                        '&:hover': {
                          backgroundColor: 'action.hover',
                          color: 'text.primary',
                          borderColor: 'primary.main',
                        },
                      }}
                      endIcon={<ArrowOutwardIcon fontSize="small" />}
                    >
                      {experiment.project?.name ?? experiment.project_id}
                    </Button>
                  </Box>
                  <Stack spacing={2}>
                    {schema.fields.length === 0 ? (
                      <Alert severity="info">
                        This project has no parameter schema yet. Define one on
                        the project page before saving experiment values.
                      </Alert>
                    ) : (
                      <>
                        <Stack spacing={2}>
                          {schema.fields.map(field => (
                            <TypedValueEditor
                              key={field.name}
                              field={field}
                              value={draft[field.name] ?? null}
                              onChange={value => updateDraft(field.name, value)}
                            />
                          ))}
                        </Stack>
                        <Divider />
                        <Box>
                          <Box
                            sx={{
                              display: 'flex',
                              gap: 2,
                              alignItems: 'center',
                            }}
                          >
                            <TextField
                              label="Message (optional)"
                              placeholder="Describe what changed, e.g. 'bumped temperature to 1.4'"
                              value={message}
                              onChange={e => setMessage(e.target.value)}
                              size="small"
                              fullWidth
                              disabled={saving}
                              sx={{ flex: 1 }}
                            />
                            <Button
                              variant="contained"
                              startIcon={<SaveIcon />}
                              onClick={handleSaveVersion}
                              disabled={saving || schema.fields.length === 0}
                            >
                              {saving ? 'Saving...' : 'Save'}
                            </Button>
                          </Box>
                          <FormHelperText>
                            Saving identical values is a no-op; the server
                            returns the existing version.
                          </FormHelperText>
                        </Box>
                      </>
                    )}
                  </Stack>
                </Paper>
              </TabPanel>

              <TabPanel value={tab} index={1} keepMounted>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 2 }}
                >
                  {EXPERIMENT_TABS[1].description}
                </Typography>
                <ProjectParameters
                  projectId={experiment.project_id}
                  sessionToken={sessionToken}
                  title="Define schema"
                  headerAction={
                    <Button
                      component={Link}
                      href={`/projects/${experiment.project_id}?tab=parameters`}
                      target="_blank"
                      rel="noopener noreferrer"
                      size="small"
                      sx={{
                        borderRadius: theme => theme.shape.borderRadius,
                        backgroundColor: 'background.paper',
                        color: 'text.secondary',
                        border: '1px solid',
                        borderColor: 'divider',
                        px: 2,
                        py: 0.5,
                        '&:hover': {
                          backgroundColor: 'action.hover',
                          color: 'text.primary',
                          borderColor: 'primary.main',
                        },
                      }}
                      endIcon={<ArrowOutwardIcon fontSize="small" />}
                    >
                      {experiment.project?.name ?? experiment.project_id}
                    </Button>
                  }
                />
              </TabPanel>
            </Paper>

            <LatestResultsPanel
              experimentId={experiment.id}
              experiment={experiment}
              sessionToken={sessionToken}
              renderVersionHistory={(outcomes, selectionProps) => (
                <VersionHistory
                  versions={experiment.versions}
                  schema={schema}
                  projectEnvironments={environments}
                  experimentId={experiment.id}
                  canPromote={isShared}
                  onPromoteVersion={version => handlePromote(version)}
                  openVersion={openVersion}
                  outcomes={outcomes}
                  {...selectionProps}
                />
              )}
            />
          </Grid>
        </Grid>
      </Box>

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
            await refresh({ silent: true });
          }}
        />
      )}

      <DeleteModal
        open={deleteOpen}
        onClose={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        title="Delete Experiment"
        itemType="experiment"
        itemName={experiment.name}
        message={
          <>
            Are you sure you want to delete the experiment &quot;
            {experiment.name}&quot;? All {experiment.versions_count} version
            {experiment.versions_count === 1 ? '' : 's'} will be removed.
            Existing test runs that used this experiment are kept; their
            parameter snapshots remain intact.
          </>
        }
        warningMessage={
          environmentsForExperiment.length > 0
            ? `This experiment is currently promoted to ${
                environmentsForExperiment.length === 1
                  ? 'environment'
                  : 'environments'
              } ${environmentsForExperiment.join(', ')}. ${
                environmentsForExperiment.length === 1 ? 'It' : 'They'
              } will be unbound as part of the delete.`
            : undefined
        }
      />
    </PageContainer>
  );
}
