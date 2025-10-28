'use client';

import React, { useState, useCallback } from 'react';
import { Box, Typography, TextField, Chip, Paper, Button } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CircularProgress from '@mui/material/CircularProgress';
import SourceSelector from './shared/SourceSelector';
import ProjectSelector from './shared/ProjectSelector';
import ActionBar from '@/components/common/ActionBar';

interface TestInputScreenProps {
  onContinue: (
    description: string,
    sourceIds: string[],
    projectId: string | null
  ) => void;
  initialDescription?: string;
  selectedSourceIds: string[];
  onSourcesChange: (sourceIds: string[]) => void;
  selectedProjectId: string | null;
  onProjectChange: (projectId: string | null) => void;
  isLoading?: boolean;
  onBack?: () => void;
}

const SUGGESTIONS = [
  {
    label: 'Bias Detection',
    prompt:
      'Test for potential biases across different demographic groups, including gender, age, race, and socioeconomic background, to ensure fair and equitable treatment for all users',
  },
  {
    label: 'Accuracy & Reliability',
    prompt:
      'Evaluate accuracy and reliability by testing for factual correctness, consistency across similar queries, and ability to cite credible sources without hallucinations or false information',
  },
  {
    label: 'Regulatory Compliance',
    prompt:
      'Test compliance with relevant regulations and data protection standards, including proper handling of sensitive information and adherence to privacy requirements such as GDPR',
  },
  {
    label: 'Safety & Ethics',
    prompt:
      'Assess safety by testing responses to harmful, unethical, or dangerous requests, ensuring appropriate refusals and safeguards are in place to protect users',
  },
  {
    label: 'Performance & Edge Cases',
    prompt:
      'Evaluate performance under various conditions including edge cases, ambiguous inputs, multilingual queries, and high-complexity scenarios to ensure robust behavior',
  },
  {
    label: 'Security Vulnerabilities',
    prompt:
      'Test for security vulnerabilities including prompt injection attacks, jailbreak attempts, and unauthorized information disclosure or data leakage that could compromise the system',
  },
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
  selectedProjectId,
  onProjectChange,
  isLoading = false,
  onBack,
}: TestInputScreenProps) {
  const [description, setDescription] = useState(initialDescription);

  const handleSuggestionClick = useCallback((suggestion: string) => {
    setDescription(suggestion);
  }, []);

  const handleContinue = useCallback(() => {
    if (description.trim()) {
      onContinue(description, selectedSourceIds, selectedProjectId);
    }
  }, [description, selectedSourceIds, selectedProjectId, onContinue]);

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
            {/* Project Selection */}
            <Box sx={{ mb: 3 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
                sx={{ mb: 1 }}
              >
                Select project (optional)
              </Typography>
              <ProjectSelector
                selectedProjectId={selectedProjectId}
                onProjectChange={onProjectChange}
              />
            </Box>

            {/* Subtitle */}
            <Typography
              variant="subtitle2"
              color="text.secondary"
              sx={{ mb: 3 }}
            >
              Describe what you want to test
            </Typography>

            {/* Main Text Area */}
            <TextField
              fullWidth
              multiline
              rows={4}
              placeholder="For example: 'I want to test our customer support chatbot for accuracy, helpfulness, and handling of edge cases like refunds and complaints.'"
              value={description}
              onChange={e => setDescription(e.target.value)}
              variant="outlined"
              sx={{ mb: 3 }}
            />

            {/* Suggestions */}
            <Box sx={{ mb: 4 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                Or try one of these:
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {SUGGESTIONS.slice(0, 4).map((suggestion, index) => (
                  <Chip
                    key={index}
                    label={suggestion.label}
                    onClick={() => handleSuggestionClick(suggestion.prompt)}
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

            {/* Source Selection */}
            <Box sx={{ mb: 3 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
                sx={{ mb: 1 }}
              >
                Select documents to provide context (optional)
              </Typography>
              <SourceSelector
                selectedSourceIds={selectedSourceIds}
                onSourcesChange={onSourcesChange}
              />
            </Box>
          </Paper>
        </Box>
      </Box>

      {/* Action Bar */}
      <ActionBar
        leftButton={
          onBack
            ? {
                label: 'Back',
                onClick: onBack,
                variant: 'outlined',
                startIcon: <ArrowBackIcon />,
              }
            : undefined
        }
        rightButton={{
          label: isLoading ? 'Loading configuration...' : 'Continue',
          onClick: handleContinue,
          disabled: !canContinue || isLoading,
          endIcon: isLoading ? (
            <CircularProgress size={20} color="inherit" />
          ) : (
            <ArrowForwardIcon />
          ),
        }}
      />
    </Box>
  );
}
