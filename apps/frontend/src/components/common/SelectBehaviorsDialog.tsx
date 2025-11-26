'use client';

import * as React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  CircularProgress,
  Stack,
  InputAdornment,
  Paper,
  Chip,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { PsychologyIcon } from '@/components/icons';
import { BehaviorClient } from '@/utils/api-client/behavior-client';
import type { BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';
import type { UUID } from 'crypto';

interface SelectBehaviorsDialogProps {
  open: boolean;
  onClose: () => void;
  onSelect: (behaviorId: UUID) => void;
  sessionToken: string;
  excludeBehaviorIds?: UUID[];
}

export default function SelectBehaviorsDialog({
  open,
  onClose,
  onSelect,
  sessionToken,
  excludeBehaviorIds = [],
}: SelectBehaviorsDialogProps) {
  const [behaviors, setBehaviors] = React.useState<BehaviorWithMetrics[]>([]);
  const [filteredBehaviors, setFilteredBehaviors] = React.useState<
    BehaviorWithMetrics[]
  >([]);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Fetch behaviors when dialog opens
  React.useEffect(() => {
    if (open) {
      fetchBehaviors();
      setSearchQuery('');
    }
  }, [open]);

  const fetchBehaviors = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const behaviorClient = new BehaviorClient(sessionToken);
      const behaviorsList = await behaviorClient.getBehaviorsWithMetrics({
        limit: 100,
        sort_by: 'name',
        sort_order: 'asc',
      });

      // Filter out excluded behaviors
      const availableBehaviors = behaviorsList.filter(
        behavior => !excludeBehaviorIds.includes(behavior.id)
      );

      setBehaviors(availableBehaviors);
      setFilteredBehaviors(availableBehaviors);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch behaviors'
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Filter behaviors based on search query
  React.useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredBehaviors(behaviors);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = behaviors.filter(
      behavior =>
        behavior.name.toLowerCase().includes(query) ||
        behavior.description?.toLowerCase().includes(query)
    );

    setFilteredBehaviors(filtered);
  }, [searchQuery, behaviors]);

  const handleSelect = (behaviorId: UUID) => {
    onSelect(behaviorId);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          maxHeight: '80vh',
        },
      }}
    >
      <DialogTitle>
        <Typography variant="h6" component="div">
          Add to Behavior
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Select a behavior to assign this metric to
        </Typography>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ mb: 2 }}>
          <TextField
            fullWidth
            placeholder="Search behaviors..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
            autoFocus
          />
        </Box>

        {isLoading ? (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              py: 4,
            }}
          >
            <CircularProgress size={24} sx={{ mr: 1 }} />
            <Typography>Loading behaviors...</Typography>
          </Box>
        ) : error ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="error">{error}</Typography>
          </Box>
        ) : filteredBehaviors.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="text.secondary">
              {behaviors.length === 0
                ? 'No behaviors available'
                : 'No behaviors match your search'}
            </Typography>
          </Box>
        ) : (
          <Stack spacing={1.5} sx={{ maxHeight: '400px', overflowY: 'auto' }}>
            {filteredBehaviors.map(behavior => (
              <Paper
                key={behavior.id}
                elevation={0}
                sx={{
                  p: 2,
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: 'divider',
                  transition: 'all 0.2s',
                  '&:hover': {
                    borderColor: 'primary.main',
                    backgroundColor: 'action.hover',
                    transform: 'translateY(-1px)',
                    boxShadow: 1,
                  },
                }}
                onClick={() => handleSelect(behavior.id as UUID)}
              >
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 1.5,
                  }}
                >
                  <PsychologyIcon
                    sx={{ color: 'primary.main', mt: 0.5 }}
                    fontSize="medium"
                  />
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography
                      variant="subtitle2"
                      sx={{
                        fontWeight: 600,
                        mb: 0.5,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {behavior.name}
                    </Typography>
                    {behavior.description && (
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{
                          mb: 1,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {behavior.description}
                      </Typography>
                    )}
                    {behavior.metrics && behavior.metrics.length > 0 && (
                      <Chip
                        label={`${behavior.metrics.length} ${behavior.metrics.length === 1 ? 'Metric' : 'Metrics'}`}
                        size="small"
                        variant="outlined"
                      />
                    )}
                  </Box>
                </Box>
              </Paper>
            ))}
          </Stack>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
}

