'use client';

import React, { useState, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  TextField,
  Chip,
  Tooltip,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CircularProgress from '@mui/material/CircularProgress';
import SourceSelector from './shared/SourceSelector';
import ModelSelector from '@/components/common/ModelSelector';
import ActionBar from '@/components/common/ActionBar';
import { SourceData } from '@/utils/api-client/interfaces/test-set';
import { TestType } from './shared/types';
import type { Model } from '@/utils/api-client/interfaces/model';
import type { Source } from '@/utils/api-client/interfaces/source';

interface TestInputScreenProps {
  testType?: TestType;
  onTestTypeChange?: (type: TestType) => void;
  onContinue: (description: string, sources: SourceData[]) => void;
  initialDescription?: string;
  selectedSourceIds: string[];
  onSourcesChange: (sources: SourceData[]) => void;
  selectedModelId: string | null;
  onModelChange: (modelId: string | null) => void;
  isLoading?: boolean;
  onBack?: () => void;
  /** Pre-fetched models from the parent — avoids a duplicate fetch in ModelSelector. */
  prefetchedModels?: Model[];
  isLoadingModels?: boolean;
  /** Pre-fetched sources from the parent — avoids a duplicate fetch in SourceSelector. */
  prefetchedSources?: Source[];
  isLoadingSources?: boolean;
}

// Scaffold phrases organized by category
const SCAFFOLD_CATEGORIES = [
  {
    title: 'What to test',
    phrases: [
      {
        id: 'evaluate-responses',
        label: 'Evaluate responses for:',
        text: 'Evaluate responses for: ',
        hint: 'accuracy, tone, helpfulness',
      },
      {
        id: 'expected-output',
        label: 'Expected output should:',
        text: 'Expected output should: ',
        hint: 'be concise, include sources',
      },
      { id: 'test-behavior', label: 'Test behavior:', text: 'Test behavior: ' },
    ],
  },
  {
    title: 'Scenarios to cover',
    phrases: [
      {
        id: 'include-scenarios',
        label: 'Include scenarios like:',
        text: 'Include scenarios like: ',
        hint: 'refunds, complaints',
      },
      {
        id: 'test-edge-cases',
        label: 'Test edge cases such as:',
        text: 'Test edge cases such as: ',
        hint: 'empty input, long text',
      },
      {
        id: 'cover-situations',
        label: 'Cover situations where:',
        text: 'Cover situations where: ',
        hint: 'user is frustrated',
      },
      {
        id: 'check-handling',
        label: 'Check handling of:',
        text: 'Check handling of: ',
        hint: 'errors, timeouts',
      },
    ],
  },
  {
    title: 'Constraints & context',
    phrases: [
      {
        id: 'for-users-who',
        label: 'For users who:',
        text: 'For users who: ',
        hint: 'are new, speak other languages',
      },
      {
        id: 'system-must-respect',
        label: 'Application must respect:',
        text: 'Application must respect: ',
        hint: 'privacy, rate limits',
      },
      {
        id: 'must-not',
        label: 'Must not:',
        text: 'Must not: ',
        hint: 'share PII, give medical advice',
      },
      {
        id: 'ensure-compliance',
        label: 'Ensure compliance with:',
        text: 'Ensure compliance with: ',
        hint: 'GDPR, accessibility',
      },
    ],
  },
];

/**
 * TestInputScreen Component
 * Collects user description and optional sources for test generation
 */
export default function TestInputScreen({
  testType = 'Single-Turn',
  onTestTypeChange,
  onContinue,
  initialDescription = '',
  selectedSourceIds,
  onSourcesChange,
  selectedModelId,
  onModelChange,
  isLoading = false,
  onBack,
  prefetchedModels,
  isLoadingModels,
  prefetchedSources,
  isLoadingSources,
}: TestInputScreenProps) {
  const [description, setDescription] = useState(initialDescription);
  const [sourcesData, setSourcesData] = useState<SourceData[]>([]);
  const textFieldRef = useRef<HTMLTextAreaElement>(null);

  const handleSourcesChange = useCallback(
    (sources: SourceData[]) => {
      setSourcesData(sources);
      onSourcesChange(sources);
    },
    [onSourcesChange]
  );

  const handleScaffoldClick = useCallback((scaffoldText: string) => {
    setDescription(prev => {
      const separator =
        prev.length > 0 && !prev.endsWith('\n') && !prev.endsWith(' ')
          ? '\n'
          : '';
      const newText = prev + separator + scaffoldText;

      setTimeout(() => {
        if (textFieldRef.current) {
          textFieldRef.current.focus();
          textFieldRef.current.setSelectionRange(
            newText.length,
            newText.length
          );
        }
      }, 0);

      return newText;
    });
  }, []);

  const handleContinue = useCallback(() => {
    if (description.trim()) {
      onContinue(description, sourcesData);
    }
  }, [description, sourcesData, onContinue]);

  const canContinue = description.trim().length > 0;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
      }}
    >
      {/* Scrollable content area */}
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {/* Test Set Configuration */}
        <SectionCard title="Test Set configuration">
          {onTestTypeChange && (
            <Box sx={{ mb: 3 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
                sx={{ mb: 1 }}
              >
                Test type
              </Typography>
              <ToggleButtonGroup
                value={testType}
                exclusive
                onChange={(_, val) => {
                  if (val) onTestTypeChange(val as TestType);
                }}
                size="small"
              >
                <ToggleButton value="Single-Turn">Single-Turn</ToggleButton>
                <ToggleButton value="Multi-Turn">Multi-Turn</ToggleButton>
              </ToggleButtonGroup>
            </Box>
          )}

          <Box sx={{ mb: 3 }}>
            <Typography
              variant="subtitle2"
              color="text.secondary"
              gutterBottom
              sx={{ mb: 1 }}
            >
              Select sources to provide context (optional)
            </Typography>
            <SourceSelector
              selectedSourceIds={selectedSourceIds}
              onSourcesChange={handleSourcesChange}
              preloadedSources={prefetchedSources}
              isLoadingSources={isLoadingSources}
            />
          </Box>

          <Box>
            <ModelSelector
              label="Generation model"
              purpose="generation"
              value={selectedModelId || ''}
              onChange={modelId => onModelChange(modelId || null)}
              hideItemDescriptions
              preloadedModels={prefetchedModels}
              isLoadingModels={isLoadingModels}
            />
          </Box>
        </SectionCard>

        {/* Describe what you want to test */}
        <SectionCard title="Describe what you want to test">
          <Box sx={{ mb: 3 }}>
            <TextField
              fullWidth
              multiline
              rows={5}
              placeholder="For example: 'I want to test our customer support chatbot for accuracy, helpfulness, and handling of edge cases like refunds and complaints.'"
              value={description}
              onChange={e => setDescription(e.target.value)}
              inputRef={textFieldRef}
              variant="outlined"
            />
          </Box>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {SCAFFOLD_CATEGORIES.map(category => (
              <Box key={category.title}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  sx={{ mb: 1, display: 'block' }}
                >
                  {category.title}
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {category.phrases.map(phrase => (
                    <Tooltip
                      key={phrase.id}
                      title={`${phrase.label} ${phrase.hint}`}
                      arrow
                      enterDelay={400}
                    >
                      <Chip
                        label={phrase.label}
                        onClick={() => handleScaffoldClick(phrase.text)}
                        variant="outlined"
                        size="small"
                        sx={{
                          cursor: 'pointer',
                          '&:hover': {
                            bgcolor: 'background.light2',
                            borderColor: 'primary.main',
                          },
                        }}
                      />
                    </Tooltip>
                  ))}
                </Box>
              </Box>
            ))}
          </Box>
        </SectionCard>
      </Box>
      <ActionBar
        sx={{ position: 'relative', flexShrink: 0 }}
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
