'use client';

import { Paper, Typography, Grid, Box, TextField, Chip } from '@mui/material';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { formatDate } from '@/utils/date';
import TestRunTags from './TestRunTags';

interface TestRunDetailsSectionProps {
  testRun: TestRunDetail;
  sessionToken: string;
}

export default function TestRunDetailsSection({ testRun, sessionToken }: TestRunDetailsSectionProps) {
  const startedAt = testRun.attributes?.started_at;
  const metadata = testRun.test_configuration?.test_set?.attributes?.metadata;

  const renderChips = (items: string[] | undefined) => {
    if (!items || items.length === 0) return null;
    return (
      <Box sx={{ 
        display: 'flex', 
        flexDirection: 'row',
        flexWrap: 'wrap', 
        gap: '4px',
        py: 2,
        px: 2,
        '& .MuiChip-root': {
          height: '24px'
        }
      }}>
        {items.map((item) => (
          <Chip
            key={item}
            label={item}
            size="small"
            color="primary"
          />
        ))}
      </Box>
    );
  };

  const renderSingleChip = (value: string | undefined | null, color: "primary" | "secondary" | "default" = "primary") => {
    if (!value) return 'N/A';
    return (
      <Box sx={{ py: 0.5 }}>
        <Chip
          label={value}
          size="small"
          color={color}
        />
      </Box>
    );
  };

  // Common style for TextField with chips
  const chipFieldStyle = {
    '& .MuiInputBase-root': {
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'center',
      padding: '0',
      minHeight: 'unset'
    },
    '& .MuiInputBase-input': {
      padding: '0',
      height: '0'
    },
    '& .MuiInputAdornment-root': {
      margin: '0',
      height: 'auto'
    }
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography 
        variant="h6" 
        gutterBottom 
        sx={{ 
          fontWeight: 'medium',
          mb: 1
        }}
      >
        Test Run Details
      </Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Box>
            <TextField
              fullWidth
              label="Started"
              value={startedAt ? formatDate(startedAt) : 'Not Started'}
              margin="normal"
              InputProps={{
                readOnly: true,
              }}
            />

            <TextField
              fullWidth
              label="Completed"
              value={formatDate(testRun.updated_at)}
              margin="normal"
              InputProps={{
                readOnly: true,
              }}
            />

            <TextField
              fullWidth
              label="Test Set"
              value=""
              margin="normal"
              InputProps={{
                readOnly: true,
                startAdornment: renderSingleChip(testRun.test_configuration?.test_set?.name)
              }}
            />

            <TextField
              fullWidth
              label="Behaviors"
              value=""
              margin="normal"
              sx={chipFieldStyle}
              InputProps={{
                readOnly: true,
                startAdornment: renderChips(metadata?.behaviors) || 'N/A'
              }}
            />
          </Box>
        </Grid>
        <Grid item xs={12} md={6}>
          <Box>
            <TextField
              fullWidth
              label="Application"
              value=""
              margin="normal"
              InputProps={{
                readOnly: true,
                startAdornment: renderSingleChip(testRun.test_configuration?.endpoint?.name)
              }}
            />
            <TextField
              fullWidth
              label="Environment"
              value=""
              margin="normal"
              InputProps={{
                readOnly: true,
                startAdornment: renderSingleChip(testRun.attributes?.environment || 'development', 'secondary')
              }}
            />

            <TextField
              fullWidth
              label="Topics"
              value=""
              margin="normal"
              sx={chipFieldStyle}
              InputProps={{
                readOnly: true,
                startAdornment: renderChips(metadata?.topics) || 'N/A'
              }}
            />

            <TextField
              fullWidth
              label="Categories"
              value=""
              margin="normal"
              sx={chipFieldStyle}
              InputProps={{
                readOnly: true,
                startAdornment: renderChips(metadata?.categories) || 'N/A'
              }}
            />
          </Box>
        </Grid>
        <Grid item xs={12}>
          <Box>
            <TestRunTags
              testRun={testRun}
              sessionToken={sessionToken}
            />
          </Box>
        </Grid>
      </Grid>
    </Paper>
  );
} 