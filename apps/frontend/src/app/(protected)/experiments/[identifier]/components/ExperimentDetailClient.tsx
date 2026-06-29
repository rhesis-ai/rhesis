'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  FormHelperText,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  PageLayout,
  type BreadcrumbItem,
} from '@/components/layout/PageLayout';
import DetailMetadataStrip from '@/components/common/DetailMetadataStrip';
import DetailTabNav from '@/components/common/DetailTabNav';
import { DetailTabPanel } from '@/components/common/DetailTabPanel';
import { Fab, FabGroup } from '@/components/common/Fab';
import BaseDrawer from '@/components/common/BaseDrawer';
import RunDrawer from '@/components/common/RunDrawer';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentDetail,
  ParameterSchema,
  ParameterValue,
  ExperimentVersion,
  ProjectEnvironments,
} from '@/utils/api-client/interfaces/parameters';
import { EditIcon, PlayArrowIcon } from '@/components/icons';
import { Capability } from '@/constants/capabilities';
import { can } from '@/utils/affordances';
import { Can } from '@/components/common/Can';
import { useNotifications } from '@/components/common/NotificationContext';
import TypedValueEditor from './TypedValueEditor';
import PromoteEnvironmentDialog from './PromoteEnvironmentDialog';
import ExperimentOverviewTab from './ExperimentOverviewTab';
import ExperimentVersionsGrid from './ExperimentVersionsGrid';
import ExperimentRunsTab from './ExperimentRunsTab';
import ExperimentParametersTab from './ExperimentParametersTab';
import { formatDate } from '@/utils/date';

const TAB_KEYS = ['overview', 'parameters', 'versions', 'runs'] as const;

const TAB_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  overview: 'Overview',
  parameters: 'Parameters',
  versions: 'Versions',
  runs: 'Experiment Runs',
};

interface ExperimentDetailClientProps {
  experimentId: string;
  sessionToken: string;
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

export default function ExperimentDetailClient({
  experimentId,
  sessionToken,
}: ExperimentDetailClientProps) {
  const notifications = useNotifications();
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);

  const [experiment, setExperiment] = useState<ExperimentDetail | null>(null);
  const [schema, setSchema] = useState<ParameterSchema | null>(null);
  const [environments, setEnvironments] = useState<ProjectEnvironments | null>(
    null
  );
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Configuration tab state
  const [draft, setDraft] = useState<Record<string, ParameterValue | null>>({});
  const [message, setMessage] = useState<string>('');
  const [saving, setSaving] = useState<boolean>(false);

  // Versions grid selection (pre-seeds RunDrawer)
  const [selectedVersionHashes, setSelectedVersionHashes] = useState<
    Set<string>
  >(new Set());

  // Rename drawer
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState('');

  // Modals / drawers
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);
  const [runDrawerOpen, setRunDrawerOpen] = useState(false);
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [promotePrefill, setPromotePrefill] = useState<{
    version?: string;
    environment?: string;
  }>({});

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const refresh = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent === true;
      if (!silent) setLoading(true);
      setError(null);
      try {
        const client = apiFactory.getParametersClient();
        const detail = await client.getExperiment(experimentId);
        setExperiment(detail);
        const schemaResp = await client.getSchema(detail.project_id);
        setSchema(schemaResp);
        const envResp = await client.getEnvironments(detail.project_id);
        setEnvironments(envResp);
        const latest = detail.versions[detail.versions.length - 1];
        setDraft(valuesFromVersion(latest, schemaResp));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load experiment');
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [apiFactory, experimentId]
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  const updateDraft = useCallback(
    (name: string, value: ParameterValue | null) => {
      setDraft(prev => ({ ...prev, [name]: value }));
    },
    []
  );

  const handleSaveVersion = useCallback(async (): Promise<boolean> => {
    if (!experiment || !schema) return false;
    setSaving(true);
    try {
      const payloadValues: Record<string, unknown> = {};
      for (const [name, value] of Object.entries(draft)) {
        if (value !== null) payloadValues[name] = value;
      }
      const client = apiFactory.getParametersClient();
      await client.createExperimentVersion(experiment.id, {
        values: payloadValues,
        message: message.trim() || undefined,
      });
      notifications.show('Version saved', { severity: 'success' });
      setMessage('');
      await refresh({ silent: true });
      return true;
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to save version',
        { severity: 'error' }
      );
      return false;
    } finally {
      setSaving(false);
    }
  }, [apiFactory, draft, experiment, message, notifications, refresh, schema]);

  const handleRenameOpen = useCallback(() => {
    if (!experiment) return;
    setRenameValue(experiment.name);
    setRenameOpen(true);
  }, [experiment]);

  const handleRenameSubmit = useCallback(async () => {
    if (!experiment) return;
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === experiment.name) {
      setRenameOpen(false);
      return;
    }
    try {
      const client = apiFactory.getParametersClient();
      const updated = await client.patchExperiment(experiment.id, {
        name: trimmed,
      });
      setExperiment(prev =>
        prev ? { ...prev, ...(updated as Partial<ExperimentDetail>) } : null
      );
      notifications.show('Experiment renamed', { severity: 'success' });
      setRenameOpen(false);
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to rename experiment',
        { severity: 'error' }
      );
    }
  }, [apiFactory, experiment, notifications, renameValue]);

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

  const breadcrumbs: BreadcrumbItem[] = useMemo(() => {
    if (!experiment) return [];
    return [
      { label: 'Experiments', href: '/experiments' },
      { label: experiment.name || 'Experiment' },
    ];
  }, [experiment]);

  if (loading) {
    return (
      <PageLayout title="Experiment" breadcrumbs={[]}>
        <Box sx={{ display: 'flex', alignItems: 'center', p: 3, gap: 2 }}>
          <CircularProgress size={20} />
          <Typography color="text.secondary">Loading experiment...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (error || !experiment || !schema) {
    return (
      <PageLayout title="Experiment" breadcrumbs={[]}>
        <Alert severity="error">{error ?? 'Experiment not found'}</Alert>
      </PageLayout>
    );
  }

  const isShared = experiment.visibility === 'shared';

  const metadataItems = [
    ...(experiment.created_at
      ? [
          {
            label: 'Created',
            value: formatDate(experiment.created_at),
          },
        ]
      : []),
    {
      label: 'Versions',
      value: String(experiment.versions_count ?? experiment.versions.length),
    },
    {
      label: 'Visibility',
      value: experiment.visibility,
    },
  ];

  const canUpdate = can(experiment, Capability.Experiment.UPDATE);

  const pageTitle = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Typography
        variant="h4"
        component="h1"
        sx={{ fontWeight: 700, color: theme => theme.palette.greyscale.title }}
      >
        {experiment.name}
      </Typography>
      {canUpdate && (
        <Tooltip title="Rename experiment">
          <IconButton
            size="small"
            onClick={handleRenameOpen}
            aria-label="Rename experiment"
          >
            <EditIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  );

  return (
    <PageLayout
      title={pageTitle}
      breadcrumbs={breadcrumbs}
      description={experiment.description ?? undefined}
      metadata={<DetailMetadataStrip items={metadataItems} />}
      actions={
        <FabGroup>
          <Can capability={Capability.TestRun.CREATE}>
            <Fab
              icon={<PlayArrowIcon />}
              tooltip="Run Experiment"
              onClick={() => setRunDrawerOpen(true)}
            />
          </Can>
        </FabGroup>
      }
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <DetailTabNav
          tabs={TAB_KEYS.map((key, index) => ({
            key,
            label: TAB_LABELS[key],
            id: `experiment-tab-${index}`,
            'aria-controls': `experiment-tabpanel-${index}`,
          }))}
          activeIndex={activeTab}
          onChange={handleTabChange}
          aria-label="Experiment detail sections"
        />

        <DetailTabPanel value={activeTab} index={0} prefix="experiment">
          <ExperimentOverviewTab
            experiment={experiment}
            environments={environments}
            sessionToken={sessionToken}
            onUpdated={updated => setExperiment(updated)}
            onUnbindEnvironment={handleUnbindEnvironment}
          />
        </DetailTabPanel>

        <DetailTabPanel value={activeTab} index={1} prefix="experiment">
          <ExperimentParametersTab
            schema={schema}
            projectId={experiment.project_id}
            projectName={experiment.project?.name}
          />
        </DetailTabPanel>

        <DetailTabPanel value={activeTab} index={2} prefix="experiment">
          <ExperimentVersionsGrid
            experiment={experiment}
            schema={schema}
            projectEnvironments={environments}
            canPromote={isShared}
            onPromoteVersion={version => handlePromote(version)}
            onRunVersion={versionHash => {
              setSelectedVersionHashes(new Set([versionHash]));
              setRunDrawerOpen(true);
            }}
            onAddConfiguration={
              canUpdate ? () => setConfigDrawerOpen(true) : undefined
            }
          />
        </DetailTabPanel>

        <DetailTabPanel value={activeTab} index={3} prefix="experiment">
          <ExperimentRunsTab
            experimentId={experiment.id}
            sessionToken={sessionToken}
            onRunExperiment={() => setRunDrawerOpen(true)}
          />
        </DetailTabPanel>
      </Box>

      {experiment && (
        <RunDrawer
          mode="runExperiment"
          open={runDrawerOpen}
          onClose={() => {
            setRunDrawerOpen(false);
            setSelectedVersionHashes(new Set());
          }}
          sessionToken={sessionToken}
          data={{
            experiment,
            initialVersionHashes:
              selectedVersionHashes.size > 0
                ? selectedVersionHashes
                : undefined,
          }}
          onSuccess={async () => {
            setRunDrawerOpen(false);
            setSelectedVersionHashes(new Set());
            await refresh({ silent: true });
          }}
        />
      )}

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

      <BaseDrawer
        open={configDrawerOpen}
        onClose={() => setConfigDrawerOpen(false)}
        title="Add configuration"
        onSave={async () => {
          const ok = await handleSaveVersion();
          if (ok) setConfigDrawerOpen(false);
        }}
        saveButtonText={saving ? 'Saving...' : 'Save as new version'}
        saveDisabled={saving || schema.fields.length === 0}
        loading={saving}
      >
        <Stack spacing={3}>
          {schema.fields.map(field => (
            <TypedValueEditor
              key={field.name}
              field={field}
              value={draft[field.name] ?? null}
              onChange={value => updateDraft(field.name, value)}
            />
          ))}
          <Box>
            <TextField
              label="Message (optional)"
              placeholder="Describe what changed, e.g. 'bumped temperature to 1.4'"
              value={message}
              onChange={e => setMessage(e.target.value)}
              fullWidth
              disabled={saving}
            />
            <FormHelperText>
              Saving identical values is a no-op; the server returns the
              existing version.
            </FormHelperText>
          </Box>
        </Stack>
      </BaseDrawer>

      <BaseDrawer
        open={renameOpen}
        onClose={() => setRenameOpen(false)}
        title="Rename Experiment"
        onSave={() => void handleRenameSubmit()}
        saveDisabled={
          !renameValue.trim() || renameValue.trim() === experiment.name
        }
        saveButtonText="Save"
      >
        <TextField
          autoFocus
          fullWidth
          label="Name"
          value={renameValue}
          onChange={e => setRenameValue(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              void handleRenameSubmit();
            }
          }}
        />
      </BaseDrawer>
    </PageLayout>
  );
}
