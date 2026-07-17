'use client';

import * as React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, TextField } from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import {
  drawerFieldsSx,
  drawerOutlinedFieldSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ENVIRONMENT_NAME_MAX_LENGTH,
  validateEnvironmentName,
} from '@/utils/api-client/interfaces/parameters';
import { useNotifications } from '@/components/common/NotificationContext';

interface ProjectAddEnvironmentDrawerProps {
  open: boolean;
  onClose: () => void;
  projectId: string;
  existingNames: Set<string>;
  onCreated: () => void;
}

export default function ProjectAddEnvironmentDrawer({
  open,
  onClose,
  projectId,
  existingNames,
  onCreated,
}: ProjectAddEnvironmentDrawerProps) {
  const notifications = useNotifications();
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);

  const resetForm = useCallback(() => {
    setName('');
  }, []);

  useEffect(() => {
    if (!open) resetForm();
  }, [open, resetForm]);

  const nameError = useMemo<string | null>(() => {
    const trimmed = name.trim();
    if (!trimmed) return 'Name is required';
    if (existingNames.has(trimmed)) {
      return (
        `"${trimmed}" already exists — use the Promote button on ` +
        `that row to change what it points at.`
      );
    }
    return validateEnvironmentName(trimmed);
  }, [name, existingNames]);

  const handleSave = async () => {
    const trimmed = name.trim();
    if (nameError || !trimmed) return;

    setSaving(true);
    try {
      const client = new ApiClientFactory().getParametersClient();
      await client.registerEnvironment(projectId, { name: trimmed });
      notifications.show(
        `Environment "${trimmed}" created. Use Promote to bind it.`,
        { severity: 'success' }
      );
      onCreated();
      onClose();
    } catch (err) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to create environment',
        { severity: 'error' }
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="New environment"
      onSave={handleSave}
      saveButtonText="Create environment"
      saveDisabled={!!nameError}
      loading={saving}
    >
      <Box sx={drawerSectionSx}>
        <FormSectionDivider
          headline="Environment"
          descriptiveText="Register a custom environment name. You can promote a shared experiment onto it from the grid after it is created."
        />
        <Box sx={drawerFieldsSx}>
          <TextField
            label="Environment name"
            placeholder="e.g. staging-eu"
            value={name}
            onChange={e => setName(e.target.value)}
            error={!!nameError && name.trim().length > 0}
            helperText={name.trim().length > 0 ? nameError : ' '}
            inputProps={{ maxLength: ENVIRONMENT_NAME_MAX_LENGTH }}
            autoFocus
            fullWidth
            sx={drawerOutlinedFieldSx}
          />
        </Box>
      </Box>
    </BaseDrawer>
  );
}
