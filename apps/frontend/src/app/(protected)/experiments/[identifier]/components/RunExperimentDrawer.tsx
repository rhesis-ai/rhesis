'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import BaseDrawer from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { ExperimentDetail, shortVersion } from '@/utils/api-client/interfaces/parameters';
import { useNotifications } from '@/components/common/NotificationContext';
import { getApiErrorMessage } from '@/utils/error-utils';
import {
  executeBatchedTestRuns,
  type SelectedExperiment,
} from '@/utils/test-run-batch';

interface RunExperimentDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  experiment: ExperimentDetail;
  selectedVersionHashes: Set<string>;
  onVersionRemove: (hash: string) => void;
  onSuccess?: () => void;
}

export default function RunExperimentDrawer({
  open,
  onClose,
  sessionToken,
  experiment,
  selectedVersionHashes,
  onVersionRemove,
  onSuccess,
}: RunExperimentDrawerProps) {
  const notifications = useNotifications();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  // Endpoint state
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [endpoint, setEndpoint] = useState<Endpoint | null>(null);

  // Test set multi-select with server-side search
  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [selectedTestSets, setSelectedTestSets] = useState<TestSet[]>([]);
  const [testSetInput, setTestSetInput] = useState('');
  const [testSetSearching, setTestSetSearching] = useState(false);
  const searchTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  // Load endpoints filtered by experiment's project
  useEffect(() => {
    if (!open) return;
    let mounted = true;

    async function load() {
      try {
        const endpointsClient = apiFactory.getEndpointsClient();
        const res = await endpointsClient.getEndpoints();
        if (!mounted) return;
        const all = Array.isArray(res?.data) ? res.data : [];
        setEndpoints(
          all.filter(e => e.project_id === experiment.project_id)
        );
      } catch {
        if (mounted) setEndpoints([]);
      }
    }

    load();
    return () => { mounted = false; };
  }, [open, apiFactory, experiment.project_id]);

  // Reset state when drawer opens/closes
  useEffect(() => {
    if (open) {
      setEndpoint(null);
      setSelectedTestSets([]);
      setTestSetInput('');
      setError(undefined);
    }
  }, [open]);

  // Fetch test sets with optional OData search filter
  const fetchTestSets = useCallback(
    async (search: string) => {
      setTestSetSearching(true);
      try {
        const testSetsClient = apiFactory.getTestSetsClient();
        const params: Record<string, unknown> = {
          sort_by: 'name',
          sort_order: 'asc' as const,
          limit: 100,
        };
        if (search.trim().length >= 2) {
          const escaped = search.replace(/'/g, "''");
          params.$filter =
            `contains(tolower(name), tolower('${escaped}'))`;
        }
        const res = await testSetsClient.getTestSets(params);
        setTestSets(Array.isArray(res?.data) ? res.data : []);
      } catch {
        setTestSets([]);
      } finally {
        setTestSetSearching(false);
      }
    },
    [apiFactory]
  );

  // Initial test set load when drawer opens
  useEffect(() => {
    if (open) fetchTestSets('');
  }, [open, fetchTestSets]);

  const handleTestSetInputChange = useCallback(
    (_: unknown, value: string, reason: string) => {
      setTestSetInput(value);
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
      if (value === '' || reason === 'reset') {
        fetchTestSets('');
        return;
      }
      if (value.length < 2) return;
      searchTimeoutRef.current = setTimeout(() => fetchTestSets(value), 500);
    },
    [fetchTestSets]
  );

  // Build SelectedExperiment entries from selected version hashes
  const versionHashes = useMemo(
    () => Array.from(selectedVersionHashes),
    [selectedVersionHashes]
  );

  const totalRuns = selectedTestSets.length * versionHashes.length;

  const handleExecute = async () => {
    if (!endpoint || selectedTestSets.length === 0 || versionHashes.length === 0) return;

    try {
      setLoading(true);
      setError(undefined);

      const testSetsClient = apiFactory.getTestSetsClient();
      const experiments: SelectedExperiment[] = versionHashes.map(hash => ({
        experiment_id: experiment.id,
        experiment_name: experiment.name,
        version: hash,
      }));

      const outcome = await executeBatchedTestRuns({
        testSetsClient,
        testSetIds: selectedTestSets.map(ts => ts.id as string),
        endpointId: endpoint.id as string,
        selectedExperiments: experiments,
        baseAttributes: {},
      });

      const runCount = outcome.members.length;
      notifications.show(
        runCount > 1
          ? `Queued ${runCount} test runs`
          : 'Test execution queued successfully',
        { severity: 'success' }
      );

      onSuccess?.();
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to execute test runs'));
    } finally {
      setLoading(false);
    }
  };

  const canExecute =
    endpoint !== null &&
    selectedTestSets.length > 0 &&
    versionHashes.length > 0;

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Run Experiment"
      loading={loading}
      error={error}
      onSave={handleExecute}
      saveDisabled={!canExecute}
      saveButtonText="Execute Now"
    >
      <Stack spacing={3}>
        {/* Experiment + selected versions */}
        <Stack spacing={1}>
          <Typography variant="subtitle2" color="text.secondary">
            Experiment
          </Typography>
          <Typography variant="body1" fontWeight={600}>
            {experiment.name}
          </Typography>

          <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 1 }}>
            Selected Versions
          </Typography>
          {versionHashes.length === 0 ? (
            <Alert severity="warning">
              No versions selected. Close the drawer and select versions first.
            </Alert>
          ) : (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {versionHashes.map(hash => (
                <Chip
                  key={hash}
                  label={shortVersion(hash)}
                  size="small"
                  sx={{ fontFamily: 'monospace' }}
                  onDelete={() => onVersionRemove(hash)}
                  deleteIcon={
                    <IconButton size="small">
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  }
                />
              ))}
            </Box>
          )}
        </Stack>

        {/* Endpoint selector */}
        <Stack spacing={1}>
          <Typography variant="subtitle2" color="text.secondary">
            Endpoint
          </Typography>
          <Autocomplete
            options={endpoints}
            value={endpoint}
            onChange={(_, v) => setEndpoint(v)}
            getOptionLabel={opt => `${opt.name} (${opt.environment})`}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            fullWidth
            renderInput={params => (
              <TextField
                {...params}
                label="Select Endpoint"
                required
                helperText={
                  endpoints.length === 0
                    ? `No endpoints found for project "${experiment.project_name ?? experiment.project?.name ?? ''}"`
                    : undefined
                }
              />
            )}
          />
        </Stack>

        {/* Test set multi-selector */}
        <Stack spacing={1}>
          <Typography variant="subtitle2" color="text.secondary">
            Test Sets
          </Typography>
          <Autocomplete
            multiple
            options={testSets}
            value={selectedTestSets}
            onChange={(_, v) => setSelectedTestSets(v)}
            inputValue={testSetInput}
            onInputChange={handleTestSetInputChange}
            getOptionLabel={opt => opt.name || 'Unnamed Test Set'}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            filterOptions={x => x}
            loading={testSetSearching}
            fullWidth
            renderInput={params => (
              <TextField
                {...params}
                label="Search Test Sets"
                placeholder="Type to search..."
                required
                slotProps={{
                  input: {
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {testSetSearching && (
                          <CircularProgress color="inherit" size={20} />
                        )}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  },
                }}
              />
            )}
          />
        </Stack>

        {/* Run count summary */}
        {canExecute && (
          <Alert severity="info">
            This will create {totalRuns} test run{totalRuns !== 1 ? 's' : ''}
            {' '}({selectedTestSets.length} test set{selectedTestSets.length !== 1 ? 's' : ''}
            {' '}&times; {versionHashes.length} version{versionHashes.length !== 1 ? 's' : ''})
          </Alert>
        )}
      </Stack>
    </BaseDrawer>
  );
}
