'use client';

import { Paper, Typography, Grid, Box, TextField, Chip, Button } from '@mui/material';
import { useState, useMemo } from 'react';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { formatDate } from '@/utils/date';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import TestRunTags from './TestRunTags';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import styles from '@/styles/TestRunDetailsSection.module.css';
import { styled } from '@mui/material/styles';

const ListItem = styled('li')(({ theme }) => ({
  margin: theme.spacing(0.5),
}));

const ChipContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  justifyContent: 'flex-start',
  flexWrap: 'wrap',
  listStyle: 'none',
  padding: theme.spacing(1),
  margin: theme.spacing(1, 0),
  minHeight: '48px',
  alignItems: 'center',
  border: `1px solid ${theme.palette.divider}`,
  borderRadius: theme.shape.borderRadius,
}));

interface TestRunDetailsSectionProps {
  testRun: TestRunDetail;
  sessionToken: string;
}

export default function TestRunDetailsSection({ testRun, sessionToken }: TestRunDetailsSectionProps) {
  const [isRetrying, setIsRetrying] = useState(false);
  const notifications = useNotifications();
  
  const startedAt = testRun.attributes?.started_at;
  const metadata = testRun.test_configuration?.test_set?.attributes?.metadata;

  // Ensure consistent empty arrays to prevent hydration mismatches
  const behaviorsList = useMemo(() => {
    return Array.isArray(metadata?.behaviors) ? metadata.behaviors : [];
  }, [metadata?.behaviors]);
  
  const topicsList = useMemo(() => {
    return Array.isArray(metadata?.topics) ? metadata.topics : [];
  }, [metadata?.topics]);
  
  const categoriesList = useMemo(() => {
    return Array.isArray(metadata?.categories) ? metadata.categories : [];
  }, [metadata?.categories]);

  const handleRetry = async () => {
    if (!testRun.test_configuration_id) return;
    
    setIsRetrying(true);
    try {
      const testConfigClient = new ApiClientFactory(sessionToken).getTestConfigurationsClient();
      await testConfigClient.executeTestConfiguration(testRun.test_configuration_id);
      
      notifications.show('Test run retry initiated successfully', { severity: 'success' });
    } catch (error) {
      console.error('Error retrying test run:', error);
      notifications.show('Failed to retry test run', { severity: 'error' });
    } finally {
      setIsRetrying(false);
    }
  };

  const renderSingleChip = (value: string | undefined | null, color: "primary" | "secondary" | "default" = "primary") => {
    if (!value) return 'N/A';
    return (
      <Chip
        label={value}
        size="small"
        color={color}
      />
    );
  };

  const renderChipArray = (items: string[], label: string) => (
    <Box sx={{ mt: 2, mb: 1 }}>
      <Box
        component="fieldset"
        sx={{
          display: 'flex',
          justifyContent: 'flex-start',
          flexWrap: 'wrap',
          alignItems: 'center',
          border: '1px solid',
          borderColor: 'rgba(0, 0, 0, 0.25)',
          borderRadius: 1,
          margin: 0,
        }}
      >
        <Box
          component="legend"
          sx={{
            fontSize: '0.75rem',
            color: 'text.secondary',
            px: 0.5,
            ml: -0.5,
          }}
        >
          {label}
        </Box>
        {items.length === 0 ? (
          <Typography variant="body2" color="textSecondary" sx={{ fontStyle: 'italic' }}>
            No {label.toLowerCase()} specified
          </Typography>
        ) : (
          items.map((item, index) => (
            <Box key={`${item}-${index}`} sx={{ m: 0.25 }}>
              <Chip
                label={item}
                size="small"
                color="primary"
              />
            </Box>
          ))
        )}
      </Box>
    </Box>
  );

  return (
    <Paper className={styles.detailsSection}>
      <Box className={styles.header}>
        <Typography 
          variant="h6" 
          className={styles.title}
        >
          Test Run Details
        </Typography>
        {testRun.test_configuration_id && (
          <Button
            variant="contained"
            color="primary"
            startIcon={<PlayArrowIcon />}
            onClick={handleRetry}
            disabled={isRetrying}
            size="small"
          >
            {isRetrying ? 'Retrying...' : 'Re-run Test Run'}
          </Button>
        )}
      </Box>
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

            {renderChipArray(behaviorsList, 'Behaviors')}
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

            {renderChipArray(topicsList, 'Topics')}

            {renderChipArray(categoriesList, 'Categories')}
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