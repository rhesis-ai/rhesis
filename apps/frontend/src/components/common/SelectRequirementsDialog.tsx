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
import { RequirementClient } from '@/utils/api-client/requirement-client';
import type { RequirementWithMetrics } from '@/utils/api-client/interfaces/requirement';
import type { UUID } from 'crypto';

interface SelectRequirementsDialogProps {
  open: boolean;
  onClose: () => void;
  onSelect: (requirementId: UUID) => void;
  excludeRequirementIds?: UUID[];
}

export default function SelectRequirementsDialog({
  open,
  onClose,
  onSelect,
  excludeRequirementIds = [],
}: SelectRequirementsDialogProps) {
  const [requirements, setRequirements] = React.useState<RequirementWithMetrics[]>([]);
  const [filteredRequirements, setFilteredRequirements] = React.useState<
    RequirementWithMetrics[]
  >([]);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const fetchRequirements = React.useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const requirementClient = new RequirementClient();
      const requirementsList = await requirementClient.getRequirementsWithMetrics({
        skip: 0,
        limit: 100,
        sort_by: 'name',
        sort_order: 'asc',
      });

      // Filter out excluded requirements
      const availableRequirements = requirementsList.filter(
        requirement => !excludeRequirementIds.includes(requirement.id)
      );

      setRequirements(availableRequirements);
      setFilteredRequirements(availableRequirements);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch requirements'
      );
    } finally {
      setIsLoading(false);
    }
  }, [excludeRequirementIds]);

  // Fetch requirements when dialog opens
  React.useEffect(() => {
    if (open) {
      fetchRequirements();
      setSearchQuery('');
    }
  }, [open, fetchRequirements]);

  // Filter requirements based on search query
  React.useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredRequirements(requirements);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = requirements.filter(
      requirement =>
        requirement.name?.toLowerCase().includes(query) ||
        requirement.description?.toLowerCase().includes(query)
    );

    setFilteredRequirements(filtered);
  }, [searchQuery, requirements]);

  const handleSelect = (requirementId: UUID) => {
    onSelect(requirementId);
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
          Add to Requirement
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Select a requirement to assign this metric to
        </Typography>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ mb: 2 }}>
          <TextField
            fullWidth
            placeholder="Search requirements..."
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
            <Typography>Loading requirements...</Typography>
          </Box>
        ) : error ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="error">{error}</Typography>
          </Box>
        ) : filteredRequirements.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="text.secondary">
              {requirements.length === 0
                ? 'No requirements available'
                : 'No requirements match your search'}
            </Typography>
          </Box>
        ) : (
          <Stack spacing={1.5} sx={{ maxHeight: '400px', overflowY: 'auto' }}>
            {filteredRequirements.map(requirement => (
              <Paper
                key={requirement.id}
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
                onClick={() => handleSelect(requirement.id as UUID)}
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
                      {requirement.name}
                    </Typography>
                    {requirement.description && (
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
                        {requirement.description}
                      </Typography>
                    )}
                    {requirement.metrics && requirement.metrics.length > 0 && (
                      <Chip
                        label={`${requirement.metrics.length} ${requirement.metrics.length === 1 ? 'Metric' : 'Metrics'}`}
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
