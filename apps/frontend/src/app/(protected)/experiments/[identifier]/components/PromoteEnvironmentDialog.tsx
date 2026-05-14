'use client';

import * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentVersion,
  ProjectEnvironments,
  WELL_KNOWN_ENVIRONMENTS,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { useNotifications } from '@/components/common/NotificationContext';

interface PromoteEnvironmentDialogProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  projectId: string;
  experimentId: string;
  experimentName: string;
  versions: ExperimentVersion[];
  currentEnvironments: ProjectEnvironments;
  defaultVersion?: string;
  defaultEnvironment?: string;
  onPromoted: () => void;
}

/**
 * Promote a (version, environment) pair onto the project.
 *
 * Promote is the deployment primitive — moving an environment flips what
 * SDK consumers and queue-time test runs resolve. The dialog shows
 * the current binding (if any) for the selected environment so the user
 * sees what they're about to overwrite, and offers the well-known
 * names plus any already-bound custom names as autocomplete options
 * (custom names are still freely typeable).
 */
export default function PromoteEnvironmentDialog({
  open,
  onClose,
  sessionToken,
  projectId,
  experimentId,
  experimentName,
  versions,
  currentEnvironments,
  defaultVersion,
  defaultEnvironment,
  onPromoted,
}: PromoteEnvironmentDialogProps) {
  const notifications = useNotifications();

  const [version, setVersion] = useState<string>('');
  const [environment, setEnvironment] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setVersion(defaultVersion ?? versions[versions.length - 1]?.version ?? '');
    setEnvironment(defaultEnvironment ?? 'default');
  }, [open, defaultVersion, defaultEnvironment, versions]);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const environmentOptions = useMemo(() => {
    const set = new Set<string>([...WELL_KNOWN_ENVIRONMENTS]);
    for (const name of Object.keys(currentEnvironments.environments)) {
      set.add(name);
    }
    return Array.from(set).sort();
  }, [currentEnvironments]);

  const currentBinding = currentEnvironments.environments[environment];
  const currentTargetIsDifferent =
    currentBinding &&
    (currentBinding.experiment_id !== experimentId ||
      currentBinding.version !== version);

  const handlePromote = async () => {
    if (!environment || !version) return;
    setSubmitting(true);
    try {
      const client = apiFactory.getParametersClient();
      await client.putEnvironment(projectId, environment, {
        experiment_id: experimentId,
        version,
      });
      notifications.show(
        `Environment "${environment}" now points at ${experimentName} ${shortVersion(version)}`,
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
      <DialogTitle>Promote to environment</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
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
                  {v.message ? ` — ${v.message}` : ''}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Autocomplete
            freeSolo
            options={environmentOptions}
            value={environment}
            onChange={(_, v) => setEnvironment(v ?? '')}
            onInputChange={(_, v) => setEnvironment(v)}
            renderInput={params => (
              <TextField
                {...params}
                label="Environment"
                size="small"
                helperText="Pick a well-known name (default, production, staging) or type a custom one."
              />
            )}
          />

          {currentTargetIsDifferent && (
            <Alert severity="warning">
              <strong>{environment}</strong> currently points at a different
              version. Promoting will move it.
            </Alert>
          )}
          {environment === 'production' && (
            <Alert severity="info">
              Promoting <strong>production</strong> is a deploy. Test
              runs and SDK consumers asking for this environment will pick up
              the new values on their next TTL window.
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={handlePromote}
          variant="contained"
          disabled={!environment || !version || submitting}
        >
          {submitting ? 'Promoting...' : 'Promote'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
