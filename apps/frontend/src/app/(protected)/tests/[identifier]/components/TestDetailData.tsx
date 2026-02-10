'use client';

/* eslint-disable react/no-array-index-key -- Test sample display */

import * as React from 'react';
import { Box, Grid, Typography, useTheme, TextField } from '@mui/material';
import BaseFreesoloAutocomplete, {
  AutocompleteOption,
} from '@/components/common/BaseFreesoloAutocomplete';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { useNotifications } from '@/components/common/NotificationContext';
import TestExecutableField from './TestExecutableField';
import FilePreview from '@/components/common/FilePreview';
import MultiTurnConfigFields from './MultiTurnConfigFields';
import {
  MultiTurnTestConfig,
  isMultiTurnConfig,
} from '@/utils/api-client/interfaces/multi-turn-test-config';
import { UUID } from 'crypto';
import { isMultiTurnTest } from '@/constants/test-types';
import { useRouter } from 'next/navigation';
import { formatDate } from '@/utils/date';

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
  const _theme = useTheme();
  const router = useRouter();
  const [behaviors, setBehaviors] = React.useState<TestDetailOption[]>([]);
  const [_types, setTypes] = React.useState<TestDetailOption[]>([]);
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
      } catch (_error) {
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
    } catch (_error) {}
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
    } catch (_error) {
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
        <Box sx={{ mb: 2 }}>
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
        <Box>
          <TextField
            fullWidth
            label="Created"
            value={formatDate(test.created_at)}
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
