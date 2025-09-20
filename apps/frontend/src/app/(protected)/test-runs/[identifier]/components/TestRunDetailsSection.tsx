'use client';

import { Typography, Grid, Box, TextField, Chip, Button } from '@mui/material';
import { useState, useMemo, useEffect } from 'react';
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
  const [endpointName, setEndpointName] = useState<string | null>(null);
  const notifications = useNotifications();
  
  const startedAt = testRun.attributes?.started_at;
  const metadata = testRun.test_configuration?.test_set?.attributes?.metadata;

  // Fetch test configuration details to get endpoint name
  useEffect(() => {
    async function fetchTestConfiguration() {
      if (testRun.test_configuration_id) {
        try {
          const testConfigClient = new ApiClientFactory(sessionToken).getTestConfigurationsClient();
          const testConfig = await testConfigClient.getTestConfiguration(testRun.test_configuration_id);
          setEndpointName(testConfig.endpoint?.name || null);
        } catch (error) {
          console.error('Error fetching test configuration:', error);
          // Fallback to existing endpoint name if available
          setEndpointName(testRun.test_configuration?.endpoint?.name || null);
        }
      }
    }
    
    fetchTestConfiguration();
  }, [testRun.test_configuration_id, sessionToken, testRun.test_configuration?.endpoint?.name]);

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

  const renderSingleChip = (value: string | undefined | null, color: "info" | "default" = "default") => {
    if (!value) return 'N/A';
    return (
      <Chip
        label={value}
        size="small"
        color={color}
        variant="outlined"
      />
    );
  };

  const renderChipArray = (items: string[], label: string, maxChips?: number) => {
    const shouldTruncate = maxChips && items.length > maxChips;
    const displayItems = shouldTruncate ? items.slice(0, maxChips) : items;
    const remainingCount = shouldTruncate ? items.length - maxChips : 0;

    return (
      <TextField
        fullWidth
        label={label}
        value=""
        margin="normal"
        InputProps={{
          readOnly: true,
          startAdornment: (
            <Box sx={{ 
              display: 'flex', 
              flexWrap: 'wrap', 
              gap: 0.5,
              py: 0.5,
              pr: 1,
              width: '100%'
            }}>
              {items.length === 0 ? (
                <Typography variant="body2" color="textSecondary" sx={{ fontStyle: 'italic', py: 0.5 }}>
                  No {label.toLowerCase()} specified
                </Typography>
              ) : (
                <>
                  {displayItems.map((item, index) => (
                    <Chip
                      key={`${item}-${index}`}
                      label={item}
                      size="small"
                      variant="outlined"
                    />
                  ))}
                  {shouldTruncate && (
                    <Chip
                      key="remaining"
                      label={`+${remainingCount}`}
                      size="small"
                      variant="outlined"
                    />
                  )}
                </>
              )}
            </Box>
          )
        }}
        sx={{
          '& .MuiInputBase-root': {
            minHeight: '54px',
            alignItems: 'flex-start',
            paddingTop: '14px',
            paddingBottom: '14px',
          },
          '& .MuiInputBase-input': {
            display: 'none'
          }
        }}
      />
    );
  };

  return (
    <Box>
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
              value={testRun.attributes?.completed_at ? formatDate(testRun.attributes.completed_at) : 'Not Completed'}
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
              label="Endpoint"
              value=""
              margin="normal"
              InputProps={{
                readOnly: true,
                startAdornment: renderSingleChip(endpointName)
              }}
            />
            <TextField
              fullWidth
              label="Environment"
              value=""
              margin="normal"
              InputProps={{
                readOnly: true,
                startAdornment: renderSingleChip(testRun.attributes?.environment || 'development')
              }}
            />

            {renderChipArray(topicsList, 'Topics', 20)}

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
    </Box>
  );
} 