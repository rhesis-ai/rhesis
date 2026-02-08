import * as React from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import Autocomplete from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import CircularProgress from '@mui/material/CircularProgress';
import { useNotifications } from '@/components/common/NotificationContext';

interface TestSetSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelect: (testSet: TestSet) => void;
  sessionToken: string;
}

export default function TestSetSelectionDialog({
  open,
  onClose,
  onSelect,
  sessionToken,
}: TestSetSelectionDialogProps) {
  const [testSets, setTestSets] = React.useState<TestSet[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [selectedTestSet, setSelectedTestSet] = React.useState<TestSet | null>(
    null
  );
  const [inputValue, setInputValue] = React.useState<string>('');
  const [isSearching, setIsSearching] = React.useState(false);
  const notifications = useNotifications();
  const searchTimeoutRef = React.useRef<NodeJS.Timeout | undefined>(undefined);

  // Create OData filter for search
  const createSearchFilter = React.useCallback(
    (search: string): string | undefined => {
      if (!search || search.trim() === '') {
        return undefined;
      }
      // Use case-insensitive contains search on the name field
      return `contains(tolower(name), tolower('${search.replace(/'/g, "''")}'))`;
    },
    []
  );

  const fetchTestSets = React.useCallback(
    async (searchValue: string, isInitialLoad = false) => {
      if (!open) return;

      // For initial load, use loading state. For search, use isSearching state
      if (isInitialLoad) {
        setLoading(true);
      } else {
        setIsSearching(true);
      }

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const testSetsClient = clientFactory.getTestSetsClient();

        const filter = createSearchFilter(searchValue);
        const queryParams: {
          sort_by: string;
          sort_order: 'asc' | 'desc';
          limit: number;
          $filter?: string;
        } = {
          sort_by: 'name',
          sort_order: 'asc',
          limit: 100, // Maximum allowed by backend
        };

        if (filter) {
          queryParams.$filter = filter;
        }

        const sets = await testSetsClient.getTestSets(queryParams);
        setTestSets(sets.data);
      } catch (error) {
        // Error fetching test sets

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

  // Initial load when dialog opens
  React.useEffect(() => {
    if (open) {
      setInputValue('');
      fetchTestSets('', true);
    }
  }, [open, fetchTestSets]);

  const handleClose = () => {
    setSelectedTestSet(null);
    setInputValue('');
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    onClose();
  };

  const handleConfirm = async () => {
    if (selectedTestSet) {
      try {
        await onSelect(selectedTestSet);

        // Show success notification
        notifications.show(
          `Test successfully added to "${selectedTestSet.name}"`,
          {
            severity: 'success',
            autoHideDuration: 4000,
          }
        );

        handleClose();
      } catch (error) {
        // Check if the error message contains our target string
        const errorMessage = error instanceof Error ? error.message : '';
        if (
          errorMessage.includes(
            'One or more tests are already associated with this test set'
          )
        ) {
          notifications.show(
            'One or more tests are already associated with this test set',
            {
              severity: 'warning',
              autoHideDuration: 6000,
            }
          );
        } else {
          notifications.show('Failed to associate test with test set', {
            severity: 'error',
            autoHideDuration: 6000,
          });
        }
      }
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
      <DialogTitle>Select Test Set</DialogTitle>
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
            // Update the input value for all reasons
            setInputValue(newInputValue);

            // Clear any pending search timeout
            if (searchTimeoutRef.current) {
              clearTimeout(searchTimeoutRef.current);
            }

            // If search is cleared or reset, immediately show all results
            if (newInputValue === '' || reason === 'reset') {
              fetchTestSets('', false);
              return;
            }

            // Only search for 2+ characters
            if (newInputValue.length < 2) {
              return;
            }

            // Debounce the search
            searchTimeoutRef.current = setTimeout(() => {
              fetchTestSets(newInputValue, false);
            }, 500);
          }}
          isOptionEqualToValue={(option, value) => option.id === value.id}
          filterOptions={x => x} // Disable client-side filtering since we're doing server-side search
          renderOption={(props, option) => (
            <li {...props} key={option.id}>
              {option.name}
            </li>
          )}
          renderInput={params => (
            <TextField
              {...params}
              label="Search Test Sets"
              placeholder="Type to search test sets..."
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
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          disabled={!selectedTestSet}
        >
          Confirm
        </Button>
      </DialogActions>
    </Dialog>
  );
}
