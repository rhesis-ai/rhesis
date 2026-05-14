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
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentVersion,
  ProjectLabels,
  WELL_KNOWN_LABELS,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import { useNotifications } from '@/components/common/NotificationContext';

interface PromoteLabelDialogProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  projectId: string;
  experimentId: string;
  experimentName: string;
  versions: ExperimentVersion[];
  currentLabels: ProjectLabels;
  defaultVersion?: string;
  defaultLabel?: string;
  onPromoted: () => void;
}

/**
 * Promote a (version, label) pair onto the project.
 *
 * Promote is the deployment primitive — moving a label flips what
 * SDK consumers and queue-time test runs resolve. The dialog shows
 * the current binding (if any) for the selected label so the user
 * sees what they're about to overwrite, and offers the well-known
 * names plus any already-bound custom names as autocomplete options
 * (custom names are still freely typeable).
 */
export default function PromoteLabelDialog({
  open,
  onClose,
  sessionToken,
  projectId,
  experimentId,
  experimentName,
  versions,
  currentLabels,
  defaultVersion,
  defaultLabel,
  onPromoted,
}: PromoteLabelDialogProps) {
  const notifications = useNotifications();

  const [version, setVersion] = useState<string>('');
  const [label, setLabel] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setVersion(defaultVersion ?? versions[versions.length - 1]?.version ?? '');
    setLabel(defaultLabel ?? 'default');
  }, [open, defaultVersion, defaultLabel, versions]);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const labelOptions = useMemo(() => {
    const set = new Set<string>([...WELL_KNOWN_LABELS]);
    for (const name of Object.keys(currentLabels.labels)) {
      set.add(name);
    }
    return Array.from(set).sort();
  }, [currentLabels]);

  const currentBinding = currentLabels.labels[label];
  const currentTargetIsDifferent =
    currentBinding &&
    (currentBinding.experiment_id !== experimentId ||
      currentBinding.version !== version);

  const handlePromote = async () => {
    if (!label || !version) return;
    setSubmitting(true);
    try {
      const client = apiFactory.getParametersClient();
      await client.putLabel(projectId, label, {
        experiment_id: experimentId,
        version,
      });
      notifications.show(
        `Label "${label}" now points at ${experimentName} ${shortVersion(version)}`,
        { severity: 'success' }
      );
      onPromoted();
    } catch (e) {
      notifications.show(
        e instanceof Error ? e.message : 'Failed to promote label',
        { severity: 'error' }
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Promote to label</DialogTitle>
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
            options={labelOptions}
            value={label}
            onChange={(_, v) => setLabel(v ?? '')}
            onInputChange={(_, v) => setLabel(v)}
            renderInput={params => (
              <TextField
                {...params}
                label="Label"
                size="small"
                helperText="Pick a well-known name (default, production, staging) or type a custom one."
              />
            )}
          />

          {currentTargetIsDifferent && (
            <Alert severity="warning">
              <strong>{label}</strong> currently points at a different
              version. Promoting will move it.
            </Alert>
          )}
          {label === 'production' && (
            <Alert severity="info">
              Promoting <strong>production</strong> is a deploy. Test
              runs and SDK consumers asking for this label will pick up
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
          disabled={!label || !version || submitting}
        >
          {submitting ? 'Promoting...' : 'Promote'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
