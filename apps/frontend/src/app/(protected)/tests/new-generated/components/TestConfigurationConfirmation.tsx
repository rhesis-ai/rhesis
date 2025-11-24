'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Button,
  TextField,
  Paper,
  Chip,
  Alert,
  AlertTitle,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import BoltIcon from '@mui/icons-material/Bolt';
import { ConfigChips, TestSetSize, ChipConfig, TestType } from './shared/types';
import TestSetSizeSelector from './shared/TestSetSizeSelector';
import ActionBar from '@/components/common/ActionBar';
import { SourceData } from '@/utils/api-client/interfaces/test-set';

interface TestConfigurationConfirmationProps {
  testType: TestType;
  configChips: ConfigChips;
  testSetSize: TestSetSize;
  testSetName: string;
  sources?: SourceData[];
  onBack: () => void;
  onGenerate: () => void;
  onTestSetSizeChange: (size: TestSetSize) => void;
  onTestSetNameChange: (name: string) => void;
  isGenerating: boolean;
}

/**
 * TestConfigurationConfirmation Component
 * Final confirmation screen before generating tests
 */
export default function TestConfigurationConfirmation({
  testType,
  configChips,
  testSetSize,
  testSetName,
  sources = [],
  onBack,
  onGenerate,
  onTestSetSizeChange,
  onTestSetNameChange,
  isGenerating,
}: TestConfigurationConfirmationProps) {
  // Count active chips across all categories
  const activeChipsCount = Object.values(configChips).reduce(
    (total, chips) =>
      total + chips.filter((chip: ChipConfig) => chip.active).length,
    0
  );

  return (
    <Box sx={{ flexGrow: 1, bgcolor: 'background.default' }}>
      {/* Main Content */}
      <Box
        sx={{
          pt: 3,
          pb: 3,
        }}
      >
        <Paper sx={{ p: 3, mb: 4 }}>
          {/* Test Set Naming */}
          <Box sx={{ mb: 4 }}>
            <Typography variant="subtitle1" gutterBottom fontWeight="bold">
              Name Your Test Set (Optional)
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Give your test set a descriptive name to make it easier to find
              and reuse later.
            </Typography>
            <TextField
              fullWidth
              placeholder="e.g., 'Return policy validation'"
              value={testSetName}
              onChange={e => onTestSetNameChange(e.target.value)}
              variant="outlined"
            />
          </Box>

          {/* Main Content Grid */}
          <Grid container spacing={4}>
            {/* Left Column - Configuration Summary */}
            <Grid
              size={{
                xs: 12,
                lg: 6,
              }}
            >
              <Box>
                <Typography variant="subtitle1">
                  Configuration Summary
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  {activeChipsCount} active configuration
                  {activeChipsCount !== 1 ? 's' : ''}
                </Typography>

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
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 1,
                      }}
                    >
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
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 1,
                      }}
                    >
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
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 1,
                      }}
                    >
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
                  <Box sx={{ mb: 3 }}>
                    <Typography
                      variant="subtitle2"
                      color="text.secondary"
                      gutterBottom
                    >
                      Context Sources
                    </Typography>
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 1,
                      }}
                    >
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
              </Box>
            </Grid>

            {/* Right Column - Test Set Size Selection */}
            <Grid
              size={{
                xs: 12,
                lg: 6,
              }}
            >
              <Box>
                <TestSetSizeSelector
                  selectedSize={testSetSize}
                  onSizeChange={onTestSetSizeChange}
                />
              </Box>
            </Grid>
          </Grid>

          {/* Info Alert */}
          <Alert severity="info" sx={{ mt: 4 }}>
            <AlertTitle>What happens next?</AlertTitle>
            When you click &quot;Generate Tests&quot;, we&apos;ll create your
            test suite based on the configuration above. The generation process
            typically takes 2-5 minutes depending on the test set size.
            You&apos;ll be notified when it&apos;s ready.
          </Alert>
        </Paper>
      </Box>
      {/* Action Bar */}
      <ActionBar
        leftButton={{
          label: 'Back',
          onClick: onBack,
          variant: 'outlined',
          disabled: isGenerating,
          startIcon: <ArrowBackIcon />,
        }}
        rightButton={{
          label: isGenerating ? 'Generating...' : 'Generate Tests',
          onClick: onGenerate,
          disabled: isGenerating || activeChipsCount === 0,
          endIcon: <BoltIcon />,
          color: 'warning',
          sx: {
            bgcolor: 'warning.main',
            '&:hover': {
              bgcolor: 'warning.dark',
            },
          },
        }}
      />
    </Box>
  );
}
