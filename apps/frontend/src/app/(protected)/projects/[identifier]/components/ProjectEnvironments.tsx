'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import Link from 'next/link';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentRead,
  EnvironmentPointer,
  ProjectEnvironments as ProjectEnvironmentsShape,
  WELL_KNOWN_ENVIRONMENTS,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { CloseIcon, AddIcon } from '@/components/icons';
import { useNotifications } from '@/components/common/NotificationContext';

interface ProjectEnvironmentsProps {
  projectId: string;
  sessionToken: string;
}

interface EnvironmentRow {
  name: string;
  pointer: EnvironmentPointer | null;
  isWellKnown: boolean;
}

/**
 * Project-scoped environments block.
 *
 * Always renders the three well-known environments (default, production,
 * staging) so the user understands these names exist as first-class
 * citizens even when no experiment is bound. Bound custom environments
 * appear below in a separate group.
 *
 * Promoting an environment is a single click that opens an autocomplete
 * picker over the project's shared experiments. Unbinding removes
 * the entry; the well-known names continue to render unbound.
 */
export default function ProjectEnvironments({
  projectId,
  sessionToken,
}: ProjectEnvironmentsProps) {
  const notifications = useNotifications();

  const [bindings, setBindings] = useState<ProjectEnvironmentsShape | null>(null);
  const [experiments, setExperiments] = useState<ExperimentRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pickerEnvironmentName, setPickerEnvironmentName] = useState<string | null>(null);
  const [picker, setPicker] = useState<{
    experimentId?: string;
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
      const [bindingsResp, expsResp] = await Promise.all([
        client.getEnvironments(projectId),
        client.listProjectExperiments(projectId, { limit: 200 }),
      ]);
      setBindings(bindingsResp);
      setExperiments(expsResp);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load environments');
    } finally {
      setLoading(false);
    }
  }, [apiFactory, projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const rows: EnvironmentRow[] = useMemo(() => {
    const out: EnvironmentRow[] = WELL_KNOWN_ENVIRONMENTS.map(name => ({
      name,
      pointer: bindings?.environments[name] ?? null,
      isWellKnown: true,
    }));
    if (bindings) {
      for (const [name, pointer] of Object.entries(bindings.environments)) {
        if (WELL_KNOWN_ENVIRONMENTS.includes(name)) continue;
        out.push({ name, pointer, isWellKnown: false });
      }
    }
    return out;
  }, [bindings]);

  const sharedExperiments = useMemo(
    () =>
      experiments.filter(
        e => e.visibility === 'shared' && e.versions_count > 0
      ),
    [experiments]
  );

  const experimentName = useCallback(
    (id: string) => experiments.find(e => e.id === id)?.name ?? id,
    [experiments]
  );

  const handleUnbind = useCallback(
    async (name: string) => {
      try {
        const client = apiFactory.getParametersClient();
        const next = await client.deleteEnvironment(projectId, name);
        setBindings(next);
        notifications.show(`Environment "${name}" unbound`, {
          severity: 'success',
        });
      } catch (e) {
        notifications.show(
          e instanceof Error ? e.message : 'Failed to unbind environment',
          { severity: 'error' }
        );
      }
    },
    [apiFactory, projectId, notifications]
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', p: 2, gap: 2 }}>
        <CircularProgress size={20} />
        <Typography color="text.secondary">Loading environments...</Typography>
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ mb: 2 }}
      >
        Environments are movable pointers at one (experiment, version) pair.
        SDK consumers and test runs that ask for an environment resolve to
        whatever it points at. The three well-known names render
        below even when unbound.
      </Typography>

      {sharedExperiments.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          No shared experiments yet. Create an experiment, save a
          version, and share it before promoting it onto an environment.
        </Alert>
      )}

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Environment</TableCell>
              <TableCell>Currently bound to</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map(row => (
              <TableRow key={row.name}>
                <TableCell>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip
                      size="small"
                      label={row.name}
                      color={row.pointer ? 'success' : 'default'}
                      variant={row.pointer ? 'filled' : 'outlined'}
                    />
                    {row.isWellKnown && (
                      <Typography variant="caption" color="text.secondary">
                        well-known
                      </Typography>
                    )}
                  </Stack>
                </TableCell>
                <TableCell>
                  {row.pointer ? (
                    <Stack
                      direction="row"
                      spacing={1}
                      alignItems="center"
                    >
                      <Link
                        href={`/experiments/${row.pointer.experiment_id}`}
                        style={{ textDecoration: 'none' }}
                      >
                        <Typography
                          variant="body2"
                          color="primary"
                          sx={{ '&:hover': { textDecoration: 'underline' } }}
                        >
                          {experimentName(row.pointer.experiment_id)}
                        </Typography>
                      </Link>
                      <Chip
                        size="small"
                        label={shortVersion(row.pointer.version)}
                        sx={{ fontFamily: 'monospace' }}
                      />
                    </Stack>
                  ) : (
                    <Typography variant="caption" color="text.secondary">
                      Unbound — no experiment promoted yet
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
                  <Stack
                    direction="row"
                    spacing={1}
                    justifyContent="flex-end"
                  >
                    <Tooltip
                      title={
                        sharedExperiments.length === 0
                          ? 'No shared experiments to promote'
                          : 'Promote a shared experiment to this environment'
                      }
                    >
                      <span>
                        <Button
                          size="small"
                          startIcon={<AddIcon />}
                          disabled={sharedExperiments.length === 0}
                          onClick={() => {
                            setPickerEnvironmentName(row.name);
                            setPicker({});
                          }}
                        >
                          Promote here
                        </Button>
                      </span>
                    </Tooltip>
                    {row.pointer && (
                      <Tooltip title="Unbind environment">
                        <IconButton
                          size="small"
                          onClick={() => handleUnbind(row.name)}
                        >
                          <CloseIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {pickerEnvironmentName && (
        <PromoteFromProjectDialog
          open={!!pickerEnvironmentName}
          environmentName={pickerEnvironmentName}
          projectId={projectId}
          sessionToken={sessionToken}
          experiments={sharedExperiments}
          onClose={() => setPickerEnvironmentName(null)}
          onPromoted={async () => {
            setPickerEnvironmentName(null);
            await refresh();
          }}
        />
      )}
    </Box>
  );
}

interface PromoteFromProjectDialogProps {
  open: boolean;
  environmentName: string;
  projectId: string;
  sessionToken: string;
  experiments: ExperimentRead[];
  onClose: () => void;
  onPromoted: () => void;
}

import {
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
} from '@mui/material';

function PromoteFromProjectDialog({
  open,
  environmentName,
  projectId,
  sessionToken,
  experiments,
  onClose,
  onPromoted,
}: PromoteFromProjectDialogProps) {
  const notifications = useNotifications();
  const [experimentId, setExperimentId] = useState<string>(
    experiments[0]?.id ?? ''
  );
  const [version, setVersion] = useState<string>(
    experiments[0]?.latest_version ?? ''
  );
  const [submitting, setSubmitting] = useState(false);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const selectedExperiment = experiments.find(e => e.id === experimentId);

  // When the experiment changes, pull its versions list so the
  // version dropdown is accurate. We could pre-load all versions
  // for all experiments but it's cheaper to fetch on-demand.
  const [versions, setVersions] = useState<{ version: string }[]>([]);
  useEffect(() => {
    if (!experimentId) return;
    let cancelled = false;
    (async () => {
      try {
        const client = apiFactory.getParametersClient();
        const detail = await client.getExperiment(experimentId);
        if (cancelled) return;
        setVersions(detail.versions);
        setVersion(
          detail.versions[detail.versions.length - 1]?.version ?? ''
        );
      } catch (_e) {
        // Best-effort; the dropdown just stays empty.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [experimentId, apiFactory]);

  const handleSubmit = async () => {
    if (!experimentId || !version) return;
    setSubmitting(true);
    try {
      const client = apiFactory.getParametersClient();
      await client.putEnvironment(projectId, environmentName, {
        experiment_id: experimentId,
        version,
      });
      notifications.show(
        `Environment "${environmentName}" now points at ${
          selectedExperiment?.name ?? experimentId
        } ${shortVersion(version)}`,
        { severity: 'success' }
      );
      onPromoted();
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to promote environment',
        { severity: 'error' }
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Promote to {environmentName}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <FormControl fullWidth size="small">
            <InputLabel>Experiment (shared only)</InputLabel>
            <Select
              label="Experiment (shared only)"
              value={experimentId}
              onChange={e => setExperimentId(e.target.value)}
            >
              {experiments.map(e => (
                <MenuItem key={e.id} value={e.id}>
                  {e.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth size="small">
            <InputLabel>Version</InputLabel>
            <Select
              label="Version"
              value={version}
              onChange={e => setVersion(e.target.value)}
            >
              {[...versions].reverse().map(v => (
                <MenuItem key={v.version} value={v.version}>
                  {shortVersion(v.version)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={!experimentId || !version || submitting}
        >
          {submitting ? 'Promoting...' : 'Promote'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
