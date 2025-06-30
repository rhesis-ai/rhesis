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
  const [selectedTestSet, setSelectedTestSet] = React.useState<TestSet | null>(null);
  const notifications = useNotifications();

  React.useEffect(() => {
    const fetchTestSets = async () => {
      if (!open) return;
      
      setLoading(true);
      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const testSetsClient = clientFactory.getTestSetsClient();
        const sets = await testSetsClient.getTestSets({
          sort_by: 'name',
          sort_order: 'asc'
        });
        setTestSets(sets.data);
      } catch (error) {
        console.error('Error fetching test sets:', error);
        notifications.show(
          'Failed to load test sets',
          {
            severity: 'error',
            autoHideDuration: 6000
          }
        );
      } finally {
        setLoading(false);
      }
    };

    fetchTestSets();
  }, [sessionToken, open, notifications]);

  const handleClose = () => {
    setSelectedTestSet(null);
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
            autoHideDuration: 4000
          }
        );
        
        handleClose();
      } catch (error) {
        console.error('Error associating test with test set:', error);
        
        // Check if the error message contains our target string
        const errorMessage = error instanceof Error ? error.message : '';
        if (errorMessage.includes('One or more tests are already associated with this test set')) {
          notifications.show(
            'One or more tests are already associated with this test set',
            {
              severity: 'warning',
              autoHideDuration: 6000
            }
          );
        } else {
          notifications.show(
            'Failed to associate test with test set',
            {
              severity: 'error',
              autoHideDuration: 6000
            }
          );
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
          m: 0
        }
      }}
    >
      <DialogTitle>Select Test Set</DialogTitle>
      <DialogContent>
        <Autocomplete
          options={testSets}
          getOptionLabel={(option) => option.name}
          loading={loading}
          value={selectedTestSet}
          onChange={(_, newValue) => setSelectedTestSet(newValue)}
          isOptionEqualToValue={(option, value) => option.id === value.id}
          renderOption={(props, option) => (
            <li {...props} key={option.id}>
              {option.name}
            </li>
          )}
          renderInput={(params) => (
            <TextField
              {...params}
              label="Test Set"
              variant="outlined"
              margin="normal"
              fullWidth
              InputProps={{
                ...params.InputProps,
                endAdornment: (
                  <React.Fragment>
                    {loading ? <CircularProgress color="inherit" size={20} /> : null}
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