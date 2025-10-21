'use client';

import React, { useState, useCallback } from 'react';
import { Box, Typography, TextField, Chip, Paper, Button } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import CircularProgress from '@mui/material/CircularProgress';
import SourceSelector from './shared/SourceSelector';
import EndpointSelector from './shared/EndpointSelector';

interface TestInputScreenProps {
  onContinue: (description: string, sourceIds: string[]) => void;
  initialDescription?: string;
  selectedSourceIds: string[];
  onSourcesChange: (sourceIds: string[]) => void;
  selectedEndpointId: string | null;
  onEndpointChange: (endpointId: string | null) => void;
  isLoading?: boolean;
}

const SUGGESTIONS = [
  'Evaluate our support chatbot for accuracy and helpfulness',
  'Test the compliance of our financial advisor with regulations',
  'Review integrity of our AI therapy application',
  'Evaluate our Gen AI application for any biases',
  'Test our content moderation system for edge cases',
  'Validate our medical diagnosis assistant for safety',
];

/**
 * TestInputScreen Component
 * Collects user description and optional sources for test generation
 */
export default function TestInputScreen({
  onContinue,
  initialDescription = '',
  selectedSourceIds,
  onSourcesChange,
  selectedEndpointId,
  onEndpointChange,
  isLoading = false,
}: TestInputScreenProps) {
  const [description, setDescription] = useState(initialDescription);

  const handleSuggestionClick = useCallback((suggestion: string) => {
    setDescription(suggestion);
  }, []);

  const handleContinue = useCallback(() => {
    if (description.trim()) {
      onContinue(description, selectedSourceIds);
    }
  }, [description, selectedSourceIds, onContinue]);

  const canContinue = description.trim().length > 0;

  return (
    <Box sx={{ flexGrow: 1, bgcolor: 'background.default' }}>
      {/* Main Content */}
      <Box
        sx={{
          pt: 3,
          pb: 3,
        }}
      >
        <Box>
          <Paper sx={{ p: 3, mb: 4 }}>
            {/* Subtitle */}
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Describe what you want to test
            </Typography>

            {/* Main Text Area */}
            <TextField
              fullWidth
              multiline
              rows={4}
              placeholder="Describe what you want to test. Be as specific as possible. For example: 'I want to test our customer support chatbot for accuracy, helpfulness, and handling of edge cases like refunds and complaints.'"
              value={description}
              onChange={e => setDescription(e.target.value)}
              variant="outlined"
              sx={{ mb: 3 }}
            />

            {/* Suggestions */}
            <Box sx={{ mb: 4 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Or try one of these:
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {SUGGESTIONS.slice(0, 4).map((suggestion, index) => (
                  <Chip
                    key={index}
                    label={suggestion}
                    onClick={() => handleSuggestionClick(suggestion)}
                    variant="outlined"
                    sx={{
                      cursor: 'pointer',
                      '&:hover': {
                        bgcolor: 'primary.lighter',
                        borderColor: 'primary.main',
                      },
                    }}
                  />
                ))}
              </Box>
            </Box>

            {/* Endpoint Selection */}
            <Box sx={{ mb: 3 }}>
              <Typography
                variant="body2"
                color="text.secondary"
                gutterBottom
                sx={{ mb: 1 }}
              >
                Select an endpoint to preview test responses (optional)
              </Typography>
              <EndpointSelector
                selectedEndpointId={selectedEndpointId}
                onEndpointChange={onEndpointChange}
              />
            </Box>

            {/* Source Selection */}
            <Box sx={{ mb: 3 }}>
              <Typography
                variant="body2"
                color="text.secondary"
                gutterBottom
                sx={{ mb: 1 }}
              >
                Select sources (documents) to provide context (optional)
              </Typography>
              <SourceSelector
                selectedSourceIds={selectedSourceIds}
                onSourcesChange={onSourcesChange}
              />
            </Box>

            {/* Action Bar */}
            <Box
              sx={{
                mt: 4,
                pt: 3,
                borderTop: 1,
                borderColor: 'divider',
                display: 'flex',
                justifyContent: 'flex-end',
              }}
            >
              <Button
                variant="contained"
                size="large"
                endIcon={
                  isLoading ? (
                    <CircularProgress size={20} color="inherit" />
                  ) : (
                    <ArrowForwardIcon />
                  )
                }
                onClick={handleContinue}
                disabled={!canContinue || isLoading}
              >
                {isLoading
                  ? 'Loading configuration...'
                  : 'Continue to Configuration'}
              </Button>
            </Box>
          </Paper>
        </Box>
      </Box>
    </Box>
  );
}
