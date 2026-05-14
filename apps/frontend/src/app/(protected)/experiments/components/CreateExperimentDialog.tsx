'use client';

import * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
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
  ExperimentRead,
  ExperimentVisibility,
} from '@/utils/api-client/interfaces/parameters';
import { Project } from '@/utils/api-client/interfaces/project';
import { useNotifications } from '@/components/common/NotificationContext';

interface CreateExperimentDialogProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  projects: Project[];
  defaultProjectId?: string;
  onCreated: (experiment: ExperimentRead) => void;
}

/**
 * Modal for creating a new experiment.
 *
 * Visibility defaults to ``private`` so a freshly created sandbox
 * never accidentally shows up in teammates' lists. Promoting a
 * private experiment to ``shared`` is a separate explicit action on
 * the detail page.
 */
export default function CreateExperimentDialog({
  open,
  onClose,
  sessionToken,
  projects,
  defaultProjectId,
  onCreated,
}: CreateExperimentDialogProps) {
  const notifications = useNotifications();

  const [projectId, setProjectId] = useState<string>('');
  const [name, setName] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [visibility, setVisibility] =
    useState<ExperimentVisibility>('private');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName('');
    setDescription('');
    setVisibility('private');
    setProjectId(defaultProjectId ?? (projects[0]?.id as string) ?? '');
  }, [open, defaultProjectId, projects]);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  const canSubmit =
    !!projectId && name.trim().length > 0 && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const client = apiFactory.getParametersClient();
      const created = await client.createProjectExperiment(projectId, {
        name: name.trim(),
        description: description.trim() || undefined,
        visibility,
      });
      notifications.show('Experiment created', { severity: 'success' });
      onCreated(created);
    } catch (err) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to create experiment',
        { severity: 'error' }
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>New experiment</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <FormControl fullWidth size="small">
            <InputLabel>Project</InputLabel>
            <Select
              label="Project"
              value={projectId}
              onChange={e => setProjectId(e.target.value)}
            >
              {projects.map(p => (
                <MenuItem key={String(p.id)} value={String(p.id)}>
                  {p.name}
                </MenuItem>
              ))}
            </Select>
            <FormHelperText>
              Each experiment lives inside one project and uses that
              project's parameter schema.
            </FormHelperText>
          </FormControl>
          <TextField
            label="Name"
            value={name}
            onChange={e => setName(e.target.value)}
            size="small"
            fullWidth
            autoFocus
          />
          <TextField
            label="Description (optional)"
            value={description}
            onChange={e => setDescription(e.target.value)}
            size="small"
            fullWidth
            multiline
            minRows={2}
          />
          <FormControl fullWidth size="small">
            <InputLabel>Visibility</InputLabel>
            <Select
              label="Visibility"
              value={visibility}
              onChange={e =>
                setVisibility(e.target.value as ExperimentVisibility)
              }
            >
              <MenuItem value="private">Private (only me)</MenuItem>
              <MenuItem value="shared">Shared (whole project)</MenuItem>
            </Select>
            <FormHelperText>
              Only shared experiments can be promoted onto a project
              label (default, production, staging).
            </FormHelperText>
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
          disabled={!canSubmit}
        >
          {submitting ? 'Creating...' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
