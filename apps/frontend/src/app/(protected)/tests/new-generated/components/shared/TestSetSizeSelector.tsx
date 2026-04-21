'use client';

import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Radio,
  RadioGroup,
  Chip,
  Stack,
  Slider,
  useTheme,
} from '@mui/material';
import { TestSetSize } from './types';

interface TestSetSizeSelectorProps {
  selectedSize: TestSetSize;
  onSizeChange: (size: TestSetSize) => void;
  customCount: number;
  onCustomCountChange: (count: number) => void;
}

const MAX_TESTS = 200;
const MIN_TESTS = 1;

interface SizeConfig {
  id: TestSetSize;
  label: string;
  description: string;
  testCount: string;
  recommended?: boolean;
}

const SIZE_CONFIGS: SizeConfig[] = [
  {
    id: 'small',
    label: 'Small',
    description: 'Quick validation and initial testing',
    testCount: '50 tests',
    recommended: true,
  },
  {
    id: 'medium',
    label: 'Medium',
    description: 'Comprehensive testing for most use cases',
    testCount: '100 tests',
  },
  {
    id: 'large',
    label: 'Large',
    description: 'Extensive testing for production systems',
    testCount: '200 tests',
  },
  {
    id: 'custom',
    label: 'Custom',
    description: 'Choose a specific number of tests',
    testCount: '',
  },
];

export default function TestSetSizeSelector({
  selectedSize,
  onSizeChange,
  customCount,
  onCustomCountChange,
}: TestSetSizeSelectorProps) {
  const theme = useTheme();

  return (
    <Box>
      <Typography variant="subtitle1" gutterBottom>
        Select Test Set Size
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Choose the number of tests to generate based on your needs
      </Typography>

      <RadioGroup
        value={selectedSize}
        onChange={e => onSizeChange(e.target.value as TestSetSize)}
      >
        <Stack spacing={1.5}>
          {SIZE_CONFIGS.map(config => {
            const isSelected = selectedSize === config.id;
            const isCustom = config.id === 'custom';

            return (
              <Card
                key={config.id}
                sx={{
                  cursor: 'pointer',
                  border: 2,
                  borderColor: isSelected ? 'primary.main' : 'divider',
                  bgcolor: isSelected
                    ? 'background.light2'
                    : 'background.paper',
                  transition: theme.transitions.create(
                    ['border-color', 'background-color', 'box-shadow'],
                    { duration: theme.transitions.duration.short }
                  ),
                  '&:hover': {
                    borderColor: 'primary.light',
                    boxShadow: 2,
                  },
                }}
                onClick={() => onSizeChange(config.id)}
              >
                <CardContent sx={{ p: 2 }}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Radio
                        checked={isSelected}
                        value={config.id}
                        sx={{ p: 0 }}
                      />
                      <Box>
                        <Box
                          sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                        >
                          <Typography variant="subtitle1" fontWeight="bold">
                            {config.label}
                          </Typography>
                          {config.recommended && (
                            <Chip
                              label="Recommended"
                              size="small"
                              color="primary"
                              variant="outlined"
                            />
                          )}
                        </Box>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ mt: 0.5 }}
                        >
                          {config.description}
                        </Typography>
                      </Box>
                    </Box>

                    {!isCustom && (
                      <Box sx={{ textAlign: 'right' }}>
                        <Typography variant="body2" fontWeight="bold">
                          {config.testCount}
                        </Typography>
                      </Box>
                    )}
                    {isCustom && !isSelected && (
                      <Box sx={{ textAlign: 'right' }}>
                        <Typography variant="body2" fontWeight="bold">
                          {MIN_TESTS}&ndash;{MAX_TESTS} tests
                        </Typography>
                      </Box>
                    )}
                  </Box>

                  {isCustom && isSelected && (
                    <Box sx={{ mt: 2, px: 1 }}>
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
                          {customCount} tests
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {MAX_TESTS}
                        </Typography>
                      </Box>
                      <Slider
                        value={customCount}
                        onChange={(_e, value) =>
                          onCustomCountChange(value as number)
                        }
                        min={MIN_TESTS}
                        max={MAX_TESTS}
                        step={1}
                        valueLabelDisplay="auto"
                        onClick={e => e.stopPropagation()}
                      />
                    </Box>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </Stack>
      </RadioGroup>
    </Box>
  );
}
