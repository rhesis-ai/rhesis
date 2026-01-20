'use client';

import * as React from 'react';
import { Box, Grid, Typography, useTheme, TextField, Skeleton, Paper } from '@mui/material';
import BaseFreesoloAutocomplete, {
  AutocompleteOption,
} from '@/components/common/BaseFreesoloAutocomplete';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail, TypeLookup } from '@/utils/api-client/interfaces/tests';
import { useNotifications } from '@/components/common/NotificationContext';
import TestExecutableField from './TestExecutableField';
import FilePreview from '@/components/common/FilePreview';
import MultiTurnConfigFields from './MultiTurnConfigFields';
import {
  MultiTurnTestConfig,
  isMultiTurnConfig,
} from '@/utils/api-client/interfaces/multi-turn-test-config';
import { UUID } from 'crypto';
import { isMultiTurnTest, isImageTest } from '@/constants/test-types';
import { useRouter } from 'next/navigation';
import { API_ENDPOINTS } from '@/utils/api-client/config';

interface TestDetailDataProps {
  sessionToken: string;
  test: TestDetail;
}

interface TestDetailOption {
  id: UUID;
  name: string;
}

export default function TestDetailData({
  sessionToken,
  test: initialTest,
}: TestDetailDataProps) {
  const theme = useTheme();
  const router = useRouter();
  const [behaviors, setBehaviors] = React.useState<TestDetailOption[]>([]);
  const [types, setTypes] = React.useState<TestDetailOption[]>([]);
  const [topics, setTopics] = React.useState<TestDetailOption[]>([]);
  const [categories, setCategories] = React.useState<TestDetailOption[]>([]);
  const [isUpdating, setIsUpdating] = React.useState(false);
  const [test, setTest] = React.useState<TestDetail>(initialTest);
  const notifications = useNotifications();

  React.useEffect(() => {
    const fetchOptions = async () => {
      if (!sessionToken) return;

      const apiFactory = new ApiClientFactory(sessionToken);

      // Fetch behaviors with sorting
      const behaviorsClient = apiFactory.getBehaviorClient();
      const behaviorsData = await behaviorsClient.getBehaviors({
        sort_by: 'name',
        sort_order: 'asc',
      });
      setBehaviors(
        behaviorsData
          .filter(
            (b: { id: UUID; name: string }) =>
              b.id && b.name && b.name.trim() !== ''
          )
          .map((b: { id: UUID; name: string }) => ({ id: b.id, name: b.name }))
      );

      // Fetch test types using the API client
      try {
        const typeLookupClient = apiFactory.getTypeLookupClient();
        const typesData = await typeLookupClient.getTypeLookups({
          sort_by: 'type_value',
          sort_order: 'asc',
          $filter: "type_name eq 'TestType'",
        });
        setTypes(
          typesData.map((t: { id: UUID; type_value: string }) => ({
            id: t.id,
            name: t.type_value,
          }))
        );
      } catch (error) {
        setTypes([]);
      }

      // Fetch topics with entity_type filter and sorting
      const topicsClient = apiFactory.getTopicClient();
      const topicsData = await topicsClient.getTopics({
        entity_type: 'Test',
        sort_by: 'name',
        sort_order: 'asc',
      });
      setTopics(
        topicsData.map((t: { id: UUID; name: string }) => ({
          id: t.id,
          name: t.name,
        }))
      );

      // Fetch categories with entity_type filter and sorting
      const categoriesClient = apiFactory.getCategoryClient();
      const categoriesData = await categoriesClient.getCategories({
        entity_type: 'Test',
        sort_by: 'name',
        sort_order: 'asc',
      });
      setCategories(
        categoriesData.map((c: { id: UUID; name: string }) => ({
          id: c.id,
          name: c.name,
        }))
      );
    };

    fetchOptions();
  }, [sessionToken]);

  const refreshTest = React.useCallback(async () => {
    if (!sessionToken || isUpdating) return;

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testsClient = apiFactory.getTestsClient();
      const promptsClient = apiFactory.getPromptsClient();

      // Fetch updated test data
      const updatedTest = await testsClient.getTest(test.id);

      // Fetch complete prompt data
      if (updatedTest.prompt_id) {
        const promptData = await promptsClient.getPrompt(updatedTest.prompt_id);
        updatedTest.prompt = promptData;
      }

      setTest(updatedTest);

      // Refresh the server components to update the page title
      router.refresh();
    } catch (error) {}
  }, [sessionToken, test.id, isUpdating, router]);

  const handleUpdate = async (
    field: string,
    value: string | AutocompleteOption | null
  ) => {
    if (!sessionToken || isUpdating) return;

    setIsUpdating(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testsClient = apiFactory.getTestsClient();

      // Prepare the update payload based on the field
      const updatePayload: Record<string, any> = {};

      if (typeof value === 'string') {
        // If it's a string, it's a new value that needs to be created
        // This would require additional API calls to create the entity
        // For now, we'll just log it
        notifications.show(
          `Creating new ${field} is not supported in this version`,
          {
            severity: 'info',
            autoHideDuration: 6000,
          }
        );
      } else if (value) {
        // If it's an object with an id, use that id
        updatePayload[`${field}_id`] = value.id;

        // Update the test
        await testsClient.updateTest(test.id, updatePayload);

        notifications.show(`Successfully updated test ${field}`, {
          severity: 'success',
          autoHideDuration: 6000,
        });

        // Refresh the test data
        await refreshTest();
      } else {
        // If value is null, we're clearing the field
        updatePayload[`${field}_id`] = null;

        // Update the test
        await testsClient.updateTest(test.id, updatePayload);

        notifications.show(`Successfully cleared test ${field}`, {
          severity: 'success',
          autoHideDuration: 6000,
        });

        // Refresh the test data
        await refreshTest();
      }
    } catch (error) {
      notifications.show(`Failed to update test ${field}`, {
        severity: 'error',
        autoHideDuration: 6000,
      });
    } finally {
      setIsUpdating(false);
    }
  };

  // Helper function to get the display value for a field
  const getDisplayValue = (field: string) => {
    switch (field) {
      case 'behavior':
        return test.behavior?.name || '';
      case 'test_type':
        return test.test_type?.type_value || '';
      case 'topic':
        return test.topic?.name || '';
      case 'category':
        return test.category?.name || '';
      default:
        return '';
    }
  };

  // Check if test is multi-turn
  const isMultiTurn = isMultiTurnTest(test.test_type?.type_value);
  
  // Check if test is image type
  const isImage = isImageTest(test.test_type?.type_value);
  
  // State for image loading
  const [imageUrl, setImageUrl] = React.useState<string | null>(null);
  const [imageLoading, setImageLoading] = React.useState(false);
  const [imageError, setImageError] = React.useState<string | null>(null);
  
  // Fetch image for image tests
  React.useEffect(() => {
    if (!isImage || !sessionToken) return;
    
    const fetchImage = async () => {
      setImageLoading(true);
      setImageError(null);
      
      try {
        const response = await fetch(`${API_ENDPOINTS.tests}/${test.id}/image`, {
          headers: {
            'Authorization': `Bearer ${sessionToken}`,
          },
        });
        
        if (!response.ok) {
          if (response.status === 404) {
            setImageError('No image available for this test');
          } else {
            setImageError('Failed to load image');
          }
          return;
        }
        
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setImageUrl(url);
      } catch (error) {
        setImageError('Failed to load image');
      } finally {
        setImageLoading(false);
      }
    };
    
    fetchImage();
    
    // Cleanup blob URL on unmount
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [isImage, sessionToken, test.id]);

  return (
    <Grid container spacing={2}>
      <Grid
        size={{
          xs: 12,
          md: 6,
        }}
      >
        <Box sx={{ mb: 2 }}>
          <BaseFreesoloAutocomplete
            options={behaviors}
            value={getDisplayValue('behavior')}
            onChange={value => {
              // Find the matching behavior option by name
              if (typeof value === 'string') {
                const matchingBehavior = behaviors.find(
                  (behavior: TestDetailOption) => behavior.name === value
                );
                if (matchingBehavior) {
                  handleUpdate('behavior', matchingBehavior);
                } else {
                  handleUpdate('behavior', value);
                }
              } else {
                handleUpdate('behavior', value);
              }
            }}
            label="Behavior"
            popperWidth="100%"
          />
        </Box>
        <Box>
          <TextField
            fullWidth
            label="Type"
            value={getDisplayValue('test_type')}
            InputProps={{
              readOnly: true,
            }}
            size="medium"
            variant="outlined"
          />
        </Box>
      </Grid>
      <Grid
        size={{
          xs: 12,
          md: 6,
        }}
      >
        <Box sx={{ mb: 2 }}>
          <BaseFreesoloAutocomplete
            options={topics}
            value={getDisplayValue('topic')}
            onChange={value => {
              // Find the matching topic option by name
              if (typeof value === 'string') {
                const matchingTopic = topics.find(
                  (topic: TestDetailOption) => topic.name === value
                );
                if (matchingTopic) {
                  handleUpdate('topic', matchingTopic);
                } else {
                  handleUpdate('topic', value);
                }
              } else {
                handleUpdate('topic', value);
              }
            }}
            label="Topic"
            popperWidth="100%"
          />
        </Box>
        <Box>
          <BaseFreesoloAutocomplete
            options={categories}
            value={getDisplayValue('category')}
            onChange={value => {
              // Find the matching category option by name
              if (typeof value === 'string') {
                const matchingCategory = categories.find(
                  (category: TestDetailOption) => category.name === value
                );
                if (matchingCategory) {
                  handleUpdate('category', matchingCategory);
                } else {
                  handleUpdate('category', value);
                }
              } else {
                handleUpdate('category', value);
              }
            }}
            label="Category"
            popperWidth="100%"
          />
        </Box>
      </Grid>
      {/* Conditional rendering based on test type */}
      {isMultiTurn ? (
        /* Multi-Turn Configuration Fields */
        <Grid size={12}>
          <MultiTurnConfigFields
            sessionToken={sessionToken}
            testId={test.id}
            initialConfig={
              isMultiTurnConfig(test.test_configuration)
                ? (test.test_configuration as MultiTurnTestConfig)
                : null
            }
            onUpdate={refreshTest}
          />
        </Grid>
      ) : isImage ? (
        /* Image Test Fields */
        <>
          <Grid size={12}>
            <Box sx={{ mb: 1 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                Generated Image
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', fontStyle: 'italic' }}
              >
                The image generated for this test case
              </Typography>
            </Box>
            <Paper 
              variant="outlined" 
              sx={{ 
                p: 2, 
                display: 'flex', 
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: 200,
                bgcolor: 'background.default',
              }}
            >
              {imageLoading ? (
                <Skeleton variant="rectangular" width={400} height={300} />
              ) : imageError ? (
                <Typography color="text.secondary">{imageError}</Typography>
              ) : imageUrl ? (
                <Box
                  component="img"
                  src={imageUrl}
                  alt={test.test_metadata?.generation_prompt || 'Generated image'}
                  sx={{
                    maxWidth: '100%',
                    maxHeight: 500,
                    objectFit: 'contain',
                    borderRadius: 1,
                  }}
                />
              ) : null}
            </Paper>
          </Grid>
          <Grid size={12}>
            <Box sx={{ mb: 1 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                Generation Prompt
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', fontStyle: 'italic' }}
              >
                The prompt used to generate this image
              </Typography>
            </Box>
            <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.default' }}>
              <Typography variant="body2">
                {test.test_metadata?.generation_prompt || 'No generation prompt available'}
              </Typography>
            </Paper>
          </Grid>
          {test.test_metadata?.expected_output && (
            <Grid size={12}>
              <Box sx={{ mb: 1 }}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  Expected Output
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', fontStyle: 'italic' }}
                >
                  The expected description or characteristics of the generated image
                </Typography>
              </Box>
              <Paper variant="outlined" sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="body2">
                  {test.test_metadata.expected_output}
                </Typography>
              </Paper>
            </Grid>
          )}
        </>
      ) : (
        /* Standard Test Fields */
        <>
          <Grid size={12}>
            <Box sx={{ mb: 1 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                Test Prompt
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', fontStyle: 'italic' }}
              >
                The input prompt that will be sent to the target system
              </Typography>
            </Box>
            <TestExecutableField
              sessionToken={sessionToken}
              testId={test.id}
              promptId={test.prompt_id}
              initialContent={test.prompt?.content || ''}
              onUpdate={refreshTest}
            />
          </Grid>
          <Grid size={12}>
            <Box sx={{ mb: 1 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                gutterBottom
              >
                Expected Response
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', fontStyle: 'italic' }}
              >
                The expected output or behavior from the target system
              </Typography>
            </Box>
            <TestExecutableField
              sessionToken={sessionToken}
              testId={test.id}
              promptId={test.prompt_id}
              initialContent={test.prompt?.expected_response || ''}
              onUpdate={refreshTest}
              fieldName="expected_response"
            />
          </Grid>
        </>
      )}
      {/* Sources Section */}
      {test.test_metadata?.sources && test.test_metadata.sources.length > 0 && (
        <Grid size={12}>
          <Box sx={{ mb: 1 }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Sources
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', fontStyle: 'italic' }}
            >
              The content shown below is the portion of the source that was used
              to generate this test case.
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {test.test_metadata.sources.map((source: any, index: number) => (
              <Box key={`source-${index}`}>
                <FilePreview
                  title={
                    source.name ||
                    source.document ||
                    source.source ||
                    'Unknown Source'
                  }
                  content={source.content || 'No content available'}
                  showCopyButton={true}
                  defaultExpanded={false}
                />
              </Box>
            ))}
          </Box>
        </Grid>
      )}
    </Grid>
  );
}
