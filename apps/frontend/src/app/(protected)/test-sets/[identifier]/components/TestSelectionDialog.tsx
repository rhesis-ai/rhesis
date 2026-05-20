'use client';

import * as React from 'react';
import {
  Autocomplete,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';

interface TestSelectionDialogProps {
  open: boolean;
  onClose: () => void;
  onSelect: (tests: TestDetail[]) => void;
  sessionToken: string;
}

export default function TestSelectionDialog({
  open,
  onClose,
  onSelect,
  sessionToken,
}: TestSelectionDialogProps) {
  const [options, setOptions] = React.useState<TestDetail[]>([]);
  const [selected, setSelected] = React.useState<TestDetail[]>([]);
  const [inputValue, setInputValue] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const searchTimeoutRef = React.useRef<NodeJS.Timeout | undefined>(undefined);

  const search = React.useCallback(
    async (q: string) => {
      setLoading(true);
      try {
        const factory = new ApiClientFactory(sessionToken);
        const client = factory.getTestsClient();
        const escaped = q.replace(/'/g, "''");
        const filter = q.trim()
          ? `contains(tolower(content), tolower('${escaped}'))`
          : undefined;
        const res = await client.getTests({
          limit: 20,
          skip: 0,
          filter,
        });
        setOptions(res.data);
      } catch {
        setOptions([]);
      } finally {
        setLoading(false);
      }
    },
    [sessionToken]
  );

  React.useEffect(() => {
    if (!open) return;
    search('');
  }, [open, search]);

  React.useEffect(() => {
    if (!open) return;
    clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => {
      search(inputValue);
    }, 300);
    return () => clearTimeout(searchTimeoutRef.current);
  }, [inputValue, open, search]);

  const handleClose = () => {
    setSelected([]);
    setInputValue('');
    onClose();
  };

  const handleConfirm = () => {
    if (selected.length > 0) {
      onSelect(selected);
      setSelected([]);
      setInputValue('');
    }
  };

  const getOptionLabel = (option: TestDetail) => {
    const content =
      option.prompt?.content ?? option.test_configuration?.goal ?? '';
    return content.length > 80 ? `${content.substring(0, 80)}…` : content;
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
      <DialogTitle>Assign tests to test set</DialogTitle>
      <DialogContent>
        <Autocomplete<TestDetail, true>
          multiple
          options={options}
          value={selected}
          inputValue={inputValue}
          onInputChange={(_, val) => setInputValue(val)}
          onChange={(_, val) => setSelected(val)}
          getOptionLabel={getOptionLabel}
          isOptionEqualToValue={(a, b) => a.id === b.id}
          loading={loading}
          filterOptions={x => x}
          renderInput={params => (
            <TextField
              {...params}
              autoFocus
              label="Search tests"
              placeholder="Type to search by content…"
              sx={{ mt: 1 }}
              InputProps={{
                ...params.InputProps,
                endAdornment: (
                  <>
                    {loading ? (
                      <CircularProgress color="inherit" size={16} />
                    ) : null}
                    {params.InputProps.endAdornment}
                  </>
                ),
              }}
            />
          )}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleConfirm}
          disabled={selected.length === 0}
        >
          Assign {selected.length > 0 ? `(${selected.length})` : ''}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
