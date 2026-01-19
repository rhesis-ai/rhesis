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

  // Fetch test set types on mount
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

        // Set default to Single-Turn if creating a new test set
        if (!testSet && types.length > 0) {
          const singleTurnType = types.find(
            t => t.type_value === 'Single-Turn'
          );
          if (singleTurnType) {
            setSelectedTestSetTypeId(singleTurnType.id);
          } else {
            // Fallback to first type if Single-Turn not found
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

            <FormControl fullWidth>
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
