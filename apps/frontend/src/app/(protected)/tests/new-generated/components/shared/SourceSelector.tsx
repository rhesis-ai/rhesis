'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  CircularProgress,
  Alert,
  Chip,
  SelectChangeEvent,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Source } from '@/utils/api-client/interfaces/source';
import DescriptionIcon from '@mui/icons-material/Description';
import CloseIcon from '@mui/icons-material/Close';

import { SourceData } from '@/utils/api-client/interfaces/test-set';

interface SourceSelectorProps {
  selectedSourceIds: string[];
  onSourcesChange: (sources: SourceData[]) => void;
}

/**
 * SourceSelector Component
 * Allows users to select existing sources from their library
 * Displays selected sources as chips below the dropdown
 */
export default function SourceSelector({
  selectedSourceIds,
  onSourcesChange,
}: SourceSelectorProps) {
  const [sources, setSources] = useState<Source[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { data: session } = useSession();

  useEffect(() => {
    loadSources();
  }, [session]);

  const loadSources = async () => {
    if (!session?.session_token) {
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      const apiFactory = new ApiClientFactory(session.session_token);
      const sourcesClient = apiFactory.getSourcesClient();

      // Fetch all sources
      const sourcesResponse = await sourcesClient.getSources({
        limit: 100,
        skip: 0,
      });

      // Handle both array and paginated response formats
      const sourcesData = Array.isArray(sourcesResponse)
        ? sourcesResponse
        : sourcesResponse?.data || [];

      setSources(sourcesData);
    } catch (err) {
      console.error('Error loading sources:', err);
      setError('Failed to load sources. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (event: SelectChangeEvent<string>) => {
    const value = event.target.value;
    if (value && !selectedSourceIds.includes(value)) {
      const source = getSourceById(value);
      if (source && source.id) {
        // Create SourceData object with only ID - backend will fetch full data
        const sourceData: SourceData = {
          id: source.id,
        };
        const currentSources = selectedSourceIds.map(id => {
          const s = getSourceById(id);
          if (!s || !s.id) return null;
          // Only send ID - backend will fetch full data from database
          return {
            id: s.id,
          };
        });
        const newSources = [
          ...(currentSources.filter(Boolean) as SourceData[]),
          sourceData,
        ];
        onSourcesChange(newSources);
      }
    }
  };

  const handleRemove = (sourceId: string) => {
    const remainingIds = selectedSourceIds.filter(id => id !== sourceId);

    // Only send IDs - backend will fetch full data from database
    const newSources = remainingIds.map(id => {
      const s = getSourceById(id);
      if (!s || !s.id) return null;
      return {
        id: s.id,
      };
    });
    onSourcesChange(newSources.filter(Boolean) as SourceData[]);
  };

  const getSourceById = (sourceId: string): Source | undefined => {
    return sources.find(source => source.id === sourceId);
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, py: 2 }}>
        <CircularProgress size={20} />
        <Typography variant="body2" color="text.secondary">
          Loading sources...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (sources.length === 0) {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        No sources available. Please upload sources in the Sources section
        first.
      </Alert>
    );
  }

  return (
    <Box>
      <FormControl fullWidth>
        <InputLabel id="source-selector-label">Select Sources</InputLabel>
        <Select
          labelId="source-selector-label"
          id="source-selector"
          value=""
          label="Select Sources"
          onChange={handleChange}
        >
          <MenuItem value="">
            <em>None</em>
          </MenuItem>
          {sources
            .filter(source => !selectedSourceIds.includes(source.id))
            .map(source => (
              <MenuItem key={source.id} value={source.id}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <DescriptionIcon fontSize="small" color="action" />
                  <Box>
                    <Typography variant="body2">{source.title}</Typography>
                    {source.description && (
                      <Typography variant="caption" color="text.secondary">
                        {source.description}
                      </Typography>
                    )}
                  </Box>
                </Box>
              </MenuItem>
            ))}
        </Select>
      </FormControl>

      {/* Display selected sources as chips */}
      {selectedSourceIds.length > 0 && (
        <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {selectedSourceIds.map(sourceId => {
            const source = getSourceById(sourceId);
            return (
              <Chip
                key={sourceId}
                icon={<DescriptionIcon />}
                label={source?.title || 'Unknown Source'}
                onDelete={() => handleRemove(sourceId)}
                deleteIcon={<CloseIcon />}
                variant="outlined"
                sx={{
                  '& .MuiChip-deleteIcon': {
                    fontSize: 18,
                  },
                }}
              />
            );
          })}
        </Box>
      )}

      {selectedSourceIds.length > 0 && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ mt: 1, display: 'block' }}
        >
          {selectedSourceIds.length} source
          {selectedSourceIds.length > 1 ? 's' : ''} selected
        </Typography>
      )}
    </Box>
  );
}
