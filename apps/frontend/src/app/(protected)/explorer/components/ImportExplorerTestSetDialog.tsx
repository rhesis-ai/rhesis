'use client';

import * as React from 'react';
import {
  Box,
  TextField,
  List,
  ListItemButton,
  ListItemText,
  InputAdornment,
  CircularProgress,
  Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import BaseDrawer from '@/components/common/BaseDrawer';
import type { TestSet } from '@/utils/api-client/interfaces/test-set';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import type { ImportExplorerTestSetResponse } from '@/utils/api-client/interfaces/explorer';

function isExplorerTestSet(testSet: TestSet): boolean {
  const behaviors = testSet.attributes?.metadata?.behaviors;
  return Array.isArray(behaviors) && behaviors.includes('Adaptive Testing');
}

interface ImportExplorerTestSetDialogProps {
  open: boolean;
  onClose: () => void;
  onImported: (result: ImportExplorerTestSetResponse) => void;
}

export default function ImportExplorerTestSetDialog({
  open,
  onClose,
  onImported,
}: ImportExplorerTestSetDialogProps) {
  const [testSets, setTestSets] = React.useState<TestSet[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [selectedTestSet, setSelectedTestSet] = React.useState<TestSet | null>(
    null
  );
  const [searchValue, setSearchValue] = React.useState('');
  const [isSearching, setIsSearching] = React.useState(false);
  const notifications = useNotifications();
  const searchTimeoutRef = React.useRef<
    ReturnType<typeof setTimeout> | undefined
  >(undefined);

  const fetchTestSets = React.useCallback(
    async (search: string, isInitialLoad = false) => {
      if (!open) return;

      if (isInitialLoad) {
        setLoading(true);
      } else {
        setIsSearching(true);
      }

      try {
        const clientFactory = new ApiClientFactory();
        const testSetsClient = clientFactory.getTestSetsClient();

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

        if (search.trim()) {
          const escaped = search.trim().replace(/'/g, "''");
          queryParams.$filter = `contains(tolower(name), tolower('${escaped}'))`;
        }

        const response = await testSetsClient.getTestSets(queryParams);
        setTestSets(response.data.filter(ts => !isExplorerTestSet(ts)));
      } catch {
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
    [open, notifications]
  );

  React.useEffect(() => {
    if (open) {
      setSearchValue('');
      setSelectedTestSet(null);
      setSubmitting(false);
      void fetchTestSets('', true);
    }
  }, [open, fetchTestSets]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchValue(value);
    setSelectedTestSet(null);

    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    if (!value.trim()) {
      void fetchTestSets('', false);
      return;
    }

    searchTimeoutRef.current = setTimeout(() => {
      void fetchTestSets(value, false);
    }, 400);
  };

  const handleClose = () => {
    if (submitting) return;
    setSelectedTestSet(null);
    setSearchValue('');
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    onClose();
  };

  const handleConfirm = async () => {
    if (!selectedTestSet) return;

    setSubmitting(true);
    try {
      const clientFactory = new ApiClientFactory();
      const explorerClient = clientFactory.getExplorerClient();
      const result = await explorerClient.importExplorerTestSetFromSource(
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
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title="Load test set"
      onSave={() => void handleConfirm()}
      saveButtonText="Load"
      saveDisabled={!selectedTestSet}
      loading={submitting}
      anchor="right"
    >
      {/* Search — separate child so it gets the 30 px side padding from the drawer paper */}
      <TextField
        fullWidth
        size="small"
        placeholder="Search test sets…"
        value={searchValue}
        onChange={handleSearchChange}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              {loading || isSearching ? (
                <CircularProgress size={16} />
              ) : (
                <SearchIcon fontSize="small" />
              )}
            </InputAdornment>
          ),
        }}
      />

      {/* Results — separate child so the 40 px BaseDrawer gap sits between search and list */}
      {loading ? (
        <Box />
      ) : testSets.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {searchValue.trim()
            ? 'No test sets match your search.'
            : 'No test sets available.'}
        </Typography>
      ) : (
        <List
          disablePadding
          sx={{
            border: theme => `1px solid ${theme.palette.divider}`,
            borderRadius: 1,
            overflow: 'hidden',
          }}
        >
          {testSets.map((ts, idx) => (
            <ListItemButton
              key={String(ts.id)}
              selected={selectedTestSet?.id === ts.id}
              onClick={() => setSelectedTestSet(ts)}
              divider={idx < testSets.length - 1}
              sx={{
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'primary.contrastText',
                  '&:hover': { bgcolor: 'primary.dark' },
                },
              }}
            >
              <ListItemText
                primary={ts.name}
                secondary={ts.description ?? undefined}
                secondaryTypographyProps={{
                  noWrap: true,
                  sx: {
                    color:
                      selectedTestSet?.id === ts.id
                        ? 'primary.contrastText'
                        : 'text.secondary',
                    opacity: 0.8,
                  },
                }}
              />
            </ListItemButton>
          ))}
        </List>
      )}
    </BaseDrawer>
  );
}
