'use client';

import * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  FormControl,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { PublicIcon, PublicOffIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  BuiltInEnvironment,
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
          <ToggleButtonGroup
            value={visibility}
            exclusive
            size="small"
            onChange={(_, value: ExperimentVisibility | null) => {
              if (value) {
                setVisibility(value);
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
          <FormHelperText>
            Only shared experiments can be promoted onto a project environment
            ({BuiltInEnvironment.ALL.join(', ')}).
          </FormHelperText>
        </Box>
      </Stack>
    </BaseDrawer>
  );
}
