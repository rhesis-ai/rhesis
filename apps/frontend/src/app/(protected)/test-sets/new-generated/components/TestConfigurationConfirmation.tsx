'use client';

import React from 'react';
import {
  Box,
  Typography,
  TextField,
  Chip,
  Alert,
  AlertTitle,
  Slider,
  Paper,
} from '@mui/material';
import { SectionCard } from '@/components/common/SectionCard';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import BoltIcon from '@mui/icons-material/Bolt';
import { ConfigChips, ChipConfig, TestType } from './shared/types';
import ActionBar from '@/components/common/ActionBar';
import { SourceData } from '@/utils/api-client/interfaces/test-set';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import type { Theme } from '@mui/material/styles';

const MIN_TESTS = 1;
const MAX_TESTS = 200;
const DEFAULT_TESTS = 50;

interface TestConfigurationConfirmationProps {
  testType: TestType;
  configChips: ConfigChips;
  testSetName: string;
  numTests: number;
  sources?: SourceData[];
  onBack: () => void;
  onGenerate: () => void;
  onTestSetNameChange: (name: string) => void;
  onNumTestsChange: (count: number) => void;
  isGenerating: boolean;
}

/**
 * TestConfigurationConfirmation Component
 * Final confirmation screen before generating tests
 */
export default function TestConfigurationConfirmation({
  testType,
  configChips,
  testSetName,
  numTests,
  sources = [],
  onBack,
  onGenerate,
  onTestSetNameChange,
  onNumTestsChange,
  isGenerating,
}: TestConfigurationConfirmationProps) {
  const [nameTouched, setNameTouched] = React.useState(false);

  const activeChipsCount = Object.values(configChips).reduce(
    (total, chips) =>
      total + chips.filter((chip: ChipConfig) => chip.active).length,
    0
  );

  const nameError = nameTouched && testSetName.trim() === '';
  const canGenerate =
    !isGenerating && activeChipsCount > 0 && testSetName.trim() !== '';

  const summaryCardSx = {
    p: 3,
    borderRadius: BORDER_RADIUS.md,
    border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
    boxShadow: ELEVATION.xs,
  };

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
        <SectionCard title="Review & generate">
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Review your configuration and set the number of tests before
            generating.
          </Typography>

          {/* Test Set Name – required */}
          <Box sx={{ mb: 4 }}>
            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
              Name Your Test Set
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Give your test set a descriptive name to make it easier to find
              and reuse later.
            </Typography>
            <TextField
              fullWidth
              required
              placeholder="e.g., 'Return policy validation'"
              value={testSetName}
              onChange={e => onTestSetNameChange(e.target.value)}
              onBlur={() => setNameTouched(true)}
              error={nameError}
              helperText={
                nameError ? 'A test set name is required.' : undefined
              }
              variant="outlined"
            />
          </Box>

          {/* Number of tests slider */}
          <Box sx={{ mb: 4 }}>
            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
              Number of Tests
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose how many tests to generate (1–200).
            </Typography>
            <Paper elevation={0} sx={summaryCardSx}>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  mb: 1,
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  {MIN_TESTS}
                </Typography>
                <Typography variant="body2" fontWeight="bold">
                  {numTests} tests
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {MAX_TESTS}
                </Typography>
              </Box>
              <Slider
                value={numTests}
                onChange={(_e, value) => onNumTestsChange(value as number)}
                min={MIN_TESTS}
                max={MAX_TESTS}
                step={1}
                valueLabelDisplay="auto"
                defaultValue={DEFAULT_TESTS}
              />
            </Paper>
          </Box>

          {/* Configuration Summary */}
          <Box sx={{ mb: 4 }}>
            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
              Configuration Summary
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {activeChipsCount} active configuration
              {activeChipsCount !== 1 ? 's' : ''}
            </Typography>

            <Paper elevation={0} sx={summaryCardSx}>
              {/* Test Type */}
              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  Test Type
                </Typography>
                <Chip
                  label={
                    testType === 'single_turn'
                      ? 'Single-Turn Tests'
                      : 'Multi-Turn Tests'
                  }
                  color={testType === 'single_turn' ? 'primary' : 'secondary'}
                />
              </Box>

              {/* Behavior Chips */}
              {configChips.behavior.some(chip => chip.active) && (
                <Box sx={{ mb: 3 }}>
                  <Typography
                    variant="subtitle2"
                    color="text.secondary"
                    gutterBottom
                  >
                    Behaviors
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {configChips.behavior
                      .filter(chip => chip.active)
                      .map(chip => (
                        <Chip
                          key={chip.id}
                          label={chip.label}
                          color="primary"
                        />
                      ))}
                  </Box>
                </Box>
              )}

              {/* Topic Chips */}
              {configChips.topics.some(chip => chip.active) && (
                <Box sx={{ mb: 3 }}>
                  <Typography
                    variant="subtitle2"
                    color="text.secondary"
                    gutterBottom
                  >
                    Topics
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {configChips.topics
                      .filter(chip => chip.active)
                      .map(chip => (
                        <Chip
                          key={chip.id}
                          label={chip.label}
                          sx={{
                            bgcolor: 'success.main',
                            color: 'success.contrastText',
                          }}
                        />
                      ))}
                  </Box>
                </Box>
              )}

              {/* Category Chips */}
              {configChips.category.some(chip => chip.active) && (
                <Box sx={{ mb: 3 }}>
                  <Typography
                    variant="subtitle2"
                    color="text.secondary"
                    gutterBottom
                  >
                    Categories
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {configChips.category
                      .filter(chip => chip.active)
                      .map(chip => (
                        <Chip
                          key={chip.id}
                          label={chip.label}
                          color="secondary"
                        />
                      ))}
                  </Box>
                </Box>
              )}

              {/* Sources */}
              {sources.length > 0 && (
                <Box>
                  <Typography
                    variant="subtitle2"
                    color="text.secondary"
                    gutterBottom
                  >
                    Context Sources
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {sources.map(doc => (
                      <Chip
                        key={doc.id}
                        label={doc.name || doc.id}
                        sx={{
                          bgcolor: 'info.main',
                          color: 'info.contrastText',
                        }}
                      />
                    ))}
                  </Box>
                </Box>
              )}
            </Paper>
          </Box>

          <Alert severity="info" sx={{ mt: 2 }}>
            <AlertTitle>What happens next?</AlertTitle>
            When you click &quot;Generate Test Set&quot;, we&apos;ll create your
            test set based on the configuration above. The generation process
            typically takes 2&ndash;5 minutes depending on the number of tests.
            You&apos;ll be redirected to the test set detail page right away.
          </Alert>
        </SectionCard>
      </Box>
      {/* Action Bar */}
      <ActionBar
        sx={{ position: 'relative', flexShrink: 0 }}
        leftButton={{
          label: 'Cancel',
          onClick: onBack,
          variant: 'outlined',
          disabled: isGenerating,
          startIcon: <ArrowBackIcon />,
        }}
        rightButton={{
          label: isGenerating ? 'Generating...' : 'Generate Test Set',
          onClick: onGenerate,
          disabled: !canGenerate,
          endIcon: <BoltIcon />,
        }}
      />
    </Box>
  );
}
