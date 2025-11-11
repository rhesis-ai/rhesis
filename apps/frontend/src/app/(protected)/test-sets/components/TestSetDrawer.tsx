'use client';

import React from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { TextField, Typography, Stack } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface TestSetDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  testSet?: TestSet;
  onSuccess?: () => void;
}

export default function TestSetDrawer({
  open,
  onClose,
  sessionToken,
  testSet,
  onSuccess,
}: TestSetDrawerProps) {
  const [error, setError] = React.useState<string>();
  const [loading, setLoading] = React.useState(false);
  const [name, setName] = React.useState(testSet?.name || '');
  const [description, setDescription] = React.useState(
    testSet?.description || ''
  );
  const [shortDescription, setShortDescription] = React.useState(
    testSet?.short_description || ''
  );

  const handleSave = async () => {
    if (!sessionToken) return;

    try {
      setLoading(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();

      const testSetData = {
        name,
        description,
        short_description: shortDescription,
        priority: 1, // Default to Medium priority
        visibility: 'organization' as const,
        is_published: false,
        attributes: {},
      };

      if (testSet) {
        await testSetsClient.updateTestSet(testSet.id, testSetData);
      } else {
        await testSetsClient.createTestSet(testSetData);
      }

      onSuccess?.();
      onClose();
    } catch (err) {
      setError('Failed to save test set');
    } finally {
      setLoading(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={testSet ? 'Edit Test Set' : 'New Test Set'}
      loading={loading}
      error={error}
      onSave={handleSave}
    >
      <Stack spacing={3}>
        {/* Test Set Details Section */}
        <Stack spacing={2}>
          <Typography variant="subtitle2" color="text.secondary">
            Test Set Details
          </Typography>

          <Stack spacing={2}>
            <TextField
              label="Name"
              value={name}
              onChange={e => setName(e.target.value)}
              required
              fullWidth
            />

            <TextField
              label="Short Description"
              value={shortDescription}
              onChange={e => setShortDescription(e.target.value)}
              fullWidth
            />

            <TextField
              label="Description"
              value={description}
              onChange={e => setDescription(e.target.value)}
              multiline
              rows={4}
              fullWidth
            />
          </Stack>
        </Stack>
      </Stack>
    </BaseDrawer>
  );
}
