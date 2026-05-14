'use client';

import * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Chip,
  FormControl,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentRead,
  ExperimentVisibility,
} from '@/utils/api-client/interfaces/parameters';
import { Project } from '@/utils/api-client/interfaces/project';
import { useNotifications } from '@/components/common/NotificationContext';

interface CreateExperimentDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  projects: Project[];
  defaultProjectId?: string;
  onCreated: (experiment: ExperimentRead) => void;
}

export default function CreateExperimentDialog({
  open,
  onClose,
  sessionToken,
  projects,
  defaultProjectId,
  onCreated,
}: CreateExperimentDrawerProps) {
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

  const canSubmit = !!projectId && name.trim().length > 0 && !submitting;

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
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="New Experiment"
      loading={submitting}
      onSave={handleSubmit}
      saveDisabled={!canSubmit}
      saveButtonText={submitting ? 'Creating...' : 'Create'}
    >
      <Stack spacing={2.5}>
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
            project&apos;s parameter schema.
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
        <Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Visibility
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip
              label="Private (only me)"
              onClick={() => setVisibility('private')}
              color={visibility === 'private' ? 'primary' : 'default'}
              variant={visibility === 'private' ? 'filled' : 'outlined'}
            />
            <Chip
              label="Shared (whole project)"
              onClick={() => setVisibility('shared')}
              color={visibility === 'shared' ? 'primary' : 'default'}
              variant={visibility === 'shared' ? 'filled' : 'outlined'}
            />
          </Box>
          <FormHelperText>
            Only shared experiments can be promoted onto a project environment
            (default, production, staging).
          </FormHelperText>
        </Box>
      </Stack>
    </BaseDrawer>
  );
}
