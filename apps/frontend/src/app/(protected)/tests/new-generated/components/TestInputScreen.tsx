'use client';

import React, { useState, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  TextField,
  Paper,
  Chip,
  Tooltip,
} from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CircularProgress from '@mui/material/CircularProgress';
import SourceSelector from './shared/SourceSelector';
import ProjectSelector from './shared/ProjectSelector';
import ActionBar from '@/components/common/ActionBar';
import { SourceData } from '@/utils/api-client/interfaces/test-set';

interface TestInputScreenProps {
  onContinue: (
    description: string,
    sources: SourceData[],
    projectId: string | null
  ) => void;
  initialDescription?: string;
  selectedSourceIds: string[];
  onSourcesChange: (sources: SourceData[]) => void;
  selectedProjectId: string | null;
  onProjectChange: (projectId: string | null) => void;
  isLoading?: boolean;
  onBack?: () => void;
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
  const [sourcesData, setSourcesData] = useState<SourceData[]>([]);
  const [cursorPosition, setCursorPosition] = useState<number>(0);
  const textFieldRef = useRef<HTMLTextAreaElement>(null);

  const handleSourcesChange = useCallback(
    (sources: SourceData[]) => {
      setSourcesData(sources);
      onSourcesChange(sources);
    },
    [onSourcesChange]
  );

  // Track cursor position when user interacts with textarea
  const handleSelect = useCallback(
    (e: React.SyntheticEvent<HTMLDivElement>) => {
      const target = e.target as HTMLTextAreaElement;
      if (target.selectionStart !== undefined) {
        setCursorPosition(target.selectionStart);
      }
    },
    []
  );

  const handleScaffoldClick = useCallback(
    (scaffoldText: string) => {
      setDescription(prev => {
        const position = cursorPosition;
        const before = prev.slice(0, position);
        const after = prev.slice(position);

        // Add newline before if inserting in middle and previous char isn't newline
        let textToInsert = scaffoldText;
        if (
          before.length > 0 &&
          !before.endsWith('\n') &&
          !before.endsWith(' ')
        ) {
          textToInsert = '\n' + scaffoldText;
        }

        const newText = before + textToInsert + after;

        // Update cursor position to end of inserted text
        const newPosition = before.length + textToInsert.length;
        setCursorPosition(newPosition);

        // Focus the textarea and set cursor position after state update
        setTimeout(() => {
          if (textFieldRef.current) {
            textFieldRef.current.focus();
            textFieldRef.current.setSelectionRange(newPosition, newPosition);
          }
        }, 0);

        return newText;
      });
    },
    [cursorPosition]
  );

  const handleContinue = useCallback(() => {
    if (description.trim()) {
      onContinue(description, sourcesData, selectedProjectId);
    }
  }, [description, sourcesData, selectedProjectId, onContinue]);

  const canContinue = description.trim().length > 0;

  return (
    <Box sx={{ flexGrow: 1 }}>
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

        {/* Source Selection */}
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
          />
        </Box>

        {/* Description Input */}
        <Box sx={{ mb: 3 }}>
          <Typography
            variant="subtitle2"
            color="text.secondary"
            gutterBottom
            sx={{ mb: 1 }}
          >
            Describe what you want to test
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={5}
            placeholder="For example: 'I want to test our customer support chatbot for accuracy, helpfulness, and handling of edge cases like refunds and complaints.'"
            value={description}
            onChange={e => setDescription(e.target.value)}
            onSelect={handleSelect}
            onClick={handleSelect}
            onKeyUp={handleSelect}
            inputRef={textFieldRef}
            variant="outlined"
          />
        </Box>

        {/* Scaffold Chips */}
        <Box>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {SCAFFOLD_CATEGORIES.map(category => (
              <Box key={category.title}>
                <Typography
                  variant="caption"
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
                            bgcolor: 'primary.lighter',
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
        </Box>
      </Paper>

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
