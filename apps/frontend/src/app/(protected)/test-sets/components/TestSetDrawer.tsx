'use client';

import React from 'react';
import BaseDrawer from '@/components/common/BaseDrawer';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import {
  TextField,
  Typography,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { UUID } from 'crypto';

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
  const [testSetTypes, setTestSetTypes] = React.useState<TypeLookup[]>([]);
  const [selectedTestSetTypeId, setSelectedTestSetTypeId] = React.useState<
    string | undefined
  >(testSet?.test_set_type_id);
  const [nameError, setNameError] = React.useState<string>('');

  React.useEffect(() => {
    if (open) {
      setName(testSet?.name || '');
      setDescription(testSet?.description || '');
      setShortDescription(testSet?.short_description || '');
      if (testSet) {
        setSelectedTestSetTypeId(testSet.test_set_type_id);
      } else {
        setSelectedTestSetTypeId(undefined);
      }
      setNameError('');
      setError(undefined);
    }
  }, [open, testSet]);

  React.useEffect(() => {
    const fetchTestSetTypes = async () => {
      if (!sessionToken) return;

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const typeLookupClient = clientFactory.getTypeLookupClient();

        const types = await typeLookupClient.getTypeLookups({
          $filter: "type_name eq 'TestType'",
          sort_by: 'type_value',
          sort_order: 'asc',
        });

        setTestSetTypes(types);

        if (!testSet && types.length > 0) {
          const singleTurnType = types.find(
            t => t.type_value === 'Single-Turn'
          );
          if (singleTurnType) {
            setSelectedTestSetTypeId(singleTurnType.id);
          } else {
            setSelectedTestSetTypeId(types[0].id);
          }
        }
      } catch (err) {
        console.error('Failed to fetch test set types:', err);
      }
    };

    fetchTestSetTypes();
  }, [sessionToken, testSet]);

  const handleSave = async () => {
    if (!sessionToken) return;

    setNameError('');
    setError(undefined);

    const trimmedName = name.trim();

    if (!trimmedName) {
      setNameError('Test set name is required');
      return;
    }

    if (trimmedName.length < 2) {
      setNameError('Test set name must be at least 2 characters');
      return;
    }

    try {
      setLoading(true);

      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();

      const testSetData = {
        name: trimmedName,
        description: description.trim(),
        short_description: shortDescription.trim(),
        priority: 1, // Default to Medium priority
        visibility: 'organization' as const,
        is_published: false,
        attributes: {},
        test_set_type_id: selectedTestSetTypeId as UUID | undefined,
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
        <Stack spacing={2}>
          <Typography variant="subtitle2" color="text.secondary">
            Test Set Details
          </Typography>

          <Stack spacing={2}>
            <TextField
              label="Name"
              value={name}
              onChange={e => {
                setName(e.target.value);
                if (nameError) setNameError('');
              }}
              required
              fullWidth
              disabled={loading}
              error={!!nameError}
              helperText={nameError || 'A clear, descriptive name for this test set'}
            />

            <FormControl fullWidth disabled={loading}>
              <InputLabel>Test Set Type</InputLabel>
              <Select
                value={selectedTestSetTypeId || ''}
                onChange={e => setSelectedTestSetTypeId(e.target.value)}
                label="Test Set Type"
                required
              >
                {testSetTypes.map(type => (
                  <MenuItem key={type.id} value={type.id}>
                    {type.type_value}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              label="Short Description"
              value={shortDescription}
              onChange={e => setShortDescription(e.target.value)}
              fullWidth
              disabled={loading}
            />

            <TextField
              label="Description"
              value={description}
              onChange={e => setDescription(e.target.value)}
              multiline
              rows={4}
              fullWidth
              disabled={loading}
            />
          </Stack>
        </Stack>
      </Stack>
    </BaseDrawer>
  );
}
