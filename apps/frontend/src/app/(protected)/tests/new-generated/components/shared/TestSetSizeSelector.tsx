'use client';

import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Radio,
  Chip,
  Stack,
} from '@mui/material';
import { TestSetSize, TestSetSizeConfig } from './types';

interface TestSetSizeSelectorProps {
  selectedSize: TestSetSize;
  onSizeChange: (size: TestSetSize) => void;
}

const SIZE_CONFIGS: TestSetSizeConfig[] = [
  {
    id: 'small',
    label: 'Small',
    description: 'Quick validation and initial testing',
    testCount: '25-50 tests',
    estimatedCost: '',
  },
  {
    id: 'medium',
    label: 'Medium',
    description: 'Comprehensive testing for most use cases',
    testCount: '75-150 tests',
    estimatedCost: '',
    recommended: true,
  },
  {
    id: 'large',
    label: 'Large',
    description: 'Extensive testing for production systems',
    testCount: '200+ tests',
    estimatedCost: '',
  },
];

/**
 * TestSetSizeSelector Component
 * Allows user to select test set size
 */
export default function TestSetSizeSelector({
  selectedSize,
  onSizeChange,
}: TestSetSizeSelectorProps) {
  return (
    <Box>
      <Typography variant="subtitle1" gutterBottom>
        Select Test Set Size
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Choose the number of tests to generate based on your needs
      </Typography>

      <Stack spacing={1.5}>
        {SIZE_CONFIGS.map(config => {
          const isSelected = selectedSize === config.id;

          return (
            <Card
              key={config.id}
              sx={{
                cursor: 'pointer',
                border: 2,
                borderColor: isSelected ? 'primary.main' : 'divider',
                bgcolor: isSelected ? 'primary.lighter' : 'background.paper',
                transition: 'all 0.2s',
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
                      onChange={() => onSizeChange(config.id)}
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

                  <Box sx={{ textAlign: 'right' }}>
                    <Typography variant="body2" fontWeight="bold">
                      {config.testCount}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          );
        })}
      </Stack>
    </Box>
  );
}
