'use client';

import * as React from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import CircularProgress from '@mui/material/CircularProgress';
import type { TestSet } from '@/utils/api-client/interfaces/test-set';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import type { ImportAdaptiveTestSetResponse } from '@/utils/api-client/interfaces/adaptive-testing';

function isAdaptiveTestingTestSet(testSet: TestSet): boolean {
  const behaviors = testSet.attributes?.metadata?.behaviors;
  return Array.isArray(behaviors) && behaviors.includes('Adaptive Testing');
}

interface ImportAdaptiveTestSetDialogProps {
  open: boolean;
  onClose: () => void;
  onImported: (result: ImportAdaptiveTestSetResponse) => void;
  sessionToken: string;
}

export default function ImportAdaptiveTestSetDialog({
  open,
  onClose,
  onImported,
  sessionToken,
}: ImportAdaptiveTestSetDialogProps) {
  const [testSets, setTestSets] = React.useState<TestSet[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [selectedTestSet, setSelectedTestSet] = React.useState<TestSet | null>(
    null
  );
  const [inputValue, setInputValue] = React.useState<string>('');
  const [isSearching, setIsSearching] = React.useState(false);
  const notifications = useNotifications();
  const searchTimeoutRef = React.useRef<
    ReturnType<typeof setTimeout> | undefined
  >(undefined);

  const createSearchFilter = React.useCallback(
    (search: string): string | undefined => {
      if (!search || search.trim() === '') {
        return undefined;
      }
      return `contains(tolower(name), tolower('${search.replace(/'/g, "''")}'))`;
    },
    []
  );

  const fetchTestSets = React.useCallback(
    async (searchValue: string, isInitialLoad = false) => {
      if (!open) return;

      if (isInitialLoad) {
        setLoading(true);
      } else {
        setIsSearching(true);
      }

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const testSetsClient = clientFactory.getTestSetsClient();

        const searchFilter = createSearchFilter(searchValue);
        const queryParams: {
          sort_by: string;
          sort_order: 'asc' | 'desc';
          limit: number;
          $filter?: string;
        } = {
          sort_by: 'name',
          sort_order: 'asc',
          limit: 100,
        };

        if (searchFilter) {
          queryParams.$filter = searchFilter;
        }

        const response = await testSetsClient.getTestSets(queryParams);
        const filtered = response.data.filter(
          ts => !isAdaptiveTestingTestSet(ts)
        );
        setTestSets(filtered);
      } catch (_error) {
        notifications.show('Failed to load test sets', {
          severity: 'error',
          autoHideDuration: 6000,
        });
      } finally {
        if (isInitialLoad) {
          setLoading(false);
        } else {
          setIsSearching(false);
        }
      }
    },
    [sessionToken, open, notifications, createSearchFilter]
  );

  React.useEffect(() => {
    if (open) {
      setInputValue('');
      setSelectedTestSet(null);
      setSubmitting(false);
      void fetchTestSets('', true);
    }
  }, [open, fetchTestSets]);

  const handleClose = () => {
    if (submitting) {
      return;
    }
    setSelectedTestSet(null);
    setInputValue('');
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    onClose();
  };

  const handleConfirm = async () => {
    if (!selectedTestSet) return;

    setSubmitting(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const adaptiveClient = clientFactory.getAdaptiveTestingClient();
      const result = await adaptiveClient.importAdaptiveTestSetFromSource(
        String(selectedTestSet.id)
      );
      onImported(result);
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : 'Failed to import test set';
      notifications.show(message, {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '100%',
          maxWidth: '500px',
          m: 0,
        },
      }}
    >
      <DialogTitle>Import test set</DialogTitle>
      <DialogContent>
        <Autocomplete
          options={testSets}
          getOptionLabel={option => option.name}
          loading={loading}
          value={selectedTestSet}
          inputValue={inputValue}
          onChange={(_, newValue) => {
            setSelectedTestSet(newValue);
          }}
          onInputChange={(_, newInputValue, reason) => {
            setInputValue(newInputValue);

            if (searchTimeoutRef.current) {
              clearTimeout(searchTimeoutRef.current);
            }

            if (newInputValue === '' || reason === 'reset') {
              void fetchTestSets('', false);
              return;
            }

            if (newInputValue.length < 2) {
              return;
            }

            searchTimeoutRef.current = setTimeout(() => {
              void fetchTestSets(newInputValue, false);
            }, 500);
          }}
          isOptionEqualToValue={(option, value) => option.id === value.id}
          filterOptions={x => x}
          renderOption={(props, option) => (
            <li {...props} key={String(option.id)}>
              {option.name}
            </li>
          )}
          renderInput={params => (
            <TextField
              {...params}
              label="Search test sets"
              placeholder="Type to search…"
              variant="outlined"
              margin="normal"
              fullWidth
              InputProps={{
                ...params.InputProps,
                endAdornment: (
                  <React.Fragment>
                    {loading || isSearching ? (
                      <CircularProgress color="inherit" size={20} />
                    ) : null}
                    {params.InputProps.endAdornment}
                  </React.Fragment>
                ),
              }}
            />
          )}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={() => void handleConfirm()}
          variant="contained"
          disabled={!selectedTestSet || submitting}
        >
          {submitting ? 'Importing…' : 'Import'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
