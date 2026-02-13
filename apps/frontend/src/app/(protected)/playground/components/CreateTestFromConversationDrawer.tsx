'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Stack,
  TextField,
  FormControl,
  Typography,
  Box,
  CircularProgress,
  Divider,
} from '@mui/material';
import BaseFreesoloAutocomplete, {
  AutocompleteOption,
} from '@/components/common/BaseFreesoloAutocomplete';
import BaseDrawer, {
  filterUniqueValidOptions,
} from '@/components/common/BaseDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ConversationTestExtractionResponse,
  ConversationMessage,
  TestBulkCreate,
} from '@/utils/api-client/interfaces/tests';

interface CreateTestFromConversationDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  /** Conversation messages to extract the test from */
  messages: ConversationMessage[];
  /** "Single-Turn" or "Multi-Turn" */
  testType: 'Single-Turn' | 'Multi-Turn';
  /** Endpoint ID from the playground */
  endpointId?: string;
  /** Called after the test is successfully created */
  onSuccess?: () => void;
}

interface TestFormData {
  behavior: string;
  topic: string;
  category: string;
  // Single-turn
  prompt_content?: string;
  expected_response?: string;
  // Multi-turn
  goal?: string;
  instructions?: string;
  restrictions?: string;
  scenario?: string;
  max_turns?: number;
}

export default function CreateTestFromConversationDrawer({
  open,
  onClose,
  sessionToken,
  messages,
  testType,
  endpointId,
  onSuccess,
}: CreateTestFromConversationDrawerProps) {
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  const [formData, setFormData] = useState<TestFormData>({
    behavior: '',
    topic: '',
    category: '',
  });

  // Options for autocomplete fields
  const [behaviors, setBehaviors] = useState<AutocompleteOption[]>([]);
  const [topics, setTopics] = useState<AutocompleteOption[]>([]);
  const [categories, setCategories] = useState<AutocompleteOption[]>([]);

  // Load dropdown options
  useEffect(() => {
    if (!open) return;

    const loadOptions = async () => {
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const [behaviorsData, topicsData, categoriesData] = await Promise.all([
          apiFactory
            .getBehaviorClient()
            .getBehaviors({ sort_by: 'name', sort_order: 'asc' }),
          apiFactory.getTopicClient().getTopics({
            sort_by: 'name',
            sort_order: 'asc',
            entity_type: 'Test',
          }),
          apiFactory.getCategoryClient().getCategories({
            sort_by: 'name',
            sort_order: 'asc',
            entity_type: 'Test',
          }),
        ]);

        setBehaviors(filterUniqueValidOptions(behaviorsData));
        setTopics(filterUniqueValidOptions(topicsData));
        setCategories(filterUniqueValidOptions(categoriesData));
      } catch (err) {
        console.error('Failed to load options:', err);
      }
    };

    loadOptions();
  }, [open, sessionToken]);

  // Extract test metadata from conversation when drawer opens
  useEffect(() => {
    if (!open || messages.length === 0) return;

    const extract = async () => {
      setExtracting(true);
      setError(undefined);
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const testsClient = apiFactory.getTestsClient();

        const extraction = await testsClient.extractTestFromConversation({
          messages,
          endpoint_id: endpointId,
          test_type: testType,
        });

        applyExtraction(extraction);
      } catch (err) {
        const msg =
          err instanceof Error
            ? err.message
            : 'Failed to extract test metadata';
        setError(msg);
      } finally {
        setExtracting(false);
      }
    };

    extract();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const applyExtraction = (extraction: ConversationTestExtractionResponse) => {
    const data: TestFormData = {
      behavior: extraction.behavior || '',
      topic: extraction.topic || '',
      category: extraction.category || '',
    };

    if (extraction.test_type === 'Single-Turn') {
      data.prompt_content = extraction.prompt_content || '';
      data.expected_response = extraction.expected_response || '';
    } else {
      const config = extraction.test_configuration || {};
      data.goal = (config.goal as string) || '';
      data.instructions = (config.instructions as string) || '';
      data.restrictions = (config.restrictions as string) || '';
      data.scenario = (config.scenario as string) || '';
      data.max_turns = (config.max_turns as number) || 5;
    }

    setFormData(data);
  };

  const handleFieldChange = (field: keyof TestFormData) => (value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleAutoCompleteChange =
    (field: keyof TestFormData) =>
    (value: AutocompleteOption | string | null) => {
      if (value === null) {
        setFormData(prev => ({ ...prev, [field]: '' }));
      } else if (typeof value === 'string') {
        setFormData(prev => ({ ...prev, [field]: value }));
      } else if ('inputValue' in value && value.inputValue) {
        setFormData(prev => ({ ...prev, [field]: value.inputValue as string }));
      } else if ('name' in value) {
        setFormData(prev => ({ ...prev, [field]: value.name }));
      }
    };

  const findOptionValue = (options: AutocompleteOption[], name: string) => {
    const match = options.find(
      o => o.name.toLowerCase() === name.toLowerCase()
    );
    return match ? match.id : name;
  };

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(undefined);
    try {
      if (!formData.behavior) throw new Error('Behavior is required');
      if (!formData.topic) throw new Error('Topic is required');
      if (!formData.category) throw new Error('Category is required');

      const apiFactory = new ApiClientFactory(sessionToken);
      const testsClient = apiFactory.getTestsClient();

      const testData: Record<string, unknown> = {
        behavior: formData.behavior,
        category: formData.category,
        topic: formData.topic,
      };

      if (testType === 'Single-Turn') {
        if (!formData.prompt_content?.trim()) {
          throw new Error('Prompt content is required');
        }
        testData.prompt = {
          content: formData.prompt_content,
          language_code: 'en',
          expected_response: formData.expected_response || undefined,
        };
        testData.test_configuration = {};
      } else {
        if (!formData.goal?.trim()) {
          throw new Error('Goal is required for multi-turn tests');
        }
        testData.test_configuration = {
          goal: formData.goal,
          instructions: formData.instructions || '',
          restrictions: formData.restrictions || '',
          scenario: formData.scenario || '',
          max_turns: formData.max_turns || 5,
        };
      }

      const response = await testsClient.createTestsBulk({
        tests: [testData as unknown as TestBulkCreate],
      });

      if (!response.success) {
        throw new Error(response.message);
      }

      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create test');
    } finally {
      setSaving(false);
    }
  }, [formData, sessionToken, testType, onSuccess, onClose]);

  const drawerTitle =
    testType === 'Single-Turn'
      ? 'Create Single-Turn Test'
      : 'Create Multi-Turn Test';

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={drawerTitle}
      loading={saving}
      error={error}
      onSave={extracting ? undefined : handleSave}
      saveDisabled={extracting}
      saveButtonText="Create Test"
    >
      {extracting ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            py: 8,
            gap: 2,
          }}
        >
          <CircularProgress />
          <Typography variant="body2" color="text.secondary">
            Analyzing conversation...
          </Typography>
        </Box>
      ) : (
        <Stack spacing={3}>
          {/* Test details section */}
          <Typography variant="subtitle2" color="text.secondary">
            Test Details
          </Typography>

          <BaseFreesoloAutocomplete
            options={behaviors}
            value={findOptionValue(behaviors, formData.behavior)}
            onChange={handleAutoCompleteChange('behavior')}
            label="Behavior"
            required
          />

          <BaseFreesoloAutocomplete
            options={topics}
            value={findOptionValue(topics, formData.topic)}
            onChange={handleAutoCompleteChange('topic')}
            label="Topic"
            required
          />

          <BaseFreesoloAutocomplete
            options={categories}
            value={findOptionValue(categories, formData.category)}
            onChange={handleAutoCompleteChange('category')}
            label="Category"
            required
          />

          <Divider />

          {/* Content section */}
          <Typography variant="subtitle2" color="text.secondary">
            Content
          </Typography>

          {testType === 'Single-Turn' ? (
            <>
              <FormControl fullWidth>
                <TextField
                  label="Prompt Content"
                  value={formData.prompt_content || ''}
                  onChange={e =>
                    handleFieldChange('prompt_content')(e.target.value)
                  }
                  multiline
                  rows={4}
                  required
                />
              </FormControl>

              <FormControl fullWidth>
                <TextField
                  label="Expected Response"
                  value={formData.expected_response || ''}
                  onChange={e =>
                    handleFieldChange('expected_response')(e.target.value)
                  }
                  multiline
                  rows={4}
                />
              </FormControl>
            </>
          ) : (
            <>
              <FormControl fullWidth>
                <TextField
                  label="Goal"
                  value={formData.goal || ''}
                  onChange={e => handleFieldChange('goal')(e.target.value)}
                  multiline
                  rows={3}
                  required
                />
              </FormControl>

              <FormControl fullWidth>
                <TextField
                  label="Instructions"
                  value={formData.instructions || ''}
                  onChange={e =>
                    handleFieldChange('instructions')(e.target.value)
                  }
                  multiline
                  rows={4}
                />
              </FormControl>

              <FormControl fullWidth>
                <TextField
                  label="Restrictions"
                  value={formData.restrictions || ''}
                  onChange={e =>
                    handleFieldChange('restrictions')(e.target.value)
                  }
                  multiline
                  rows={3}
                />
              </FormControl>

              <FormControl fullWidth>
                <TextField
                  label="Scenario"
                  value={formData.scenario || ''}
                  onChange={e => handleFieldChange('scenario')(e.target.value)}
                  multiline
                  rows={3}
                />
              </FormControl>

              <FormControl fullWidth>
                <TextField
                  label="Max Turns"
                  type="number"
                  value={formData.max_turns ?? 5}
                  onChange={e =>
                    setFormData(prev => ({
                      ...prev,
                      max_turns: parseInt(e.target.value, 10) || 5,
                    }))
                  }
                  slotProps={{
                    htmlInput: { min: 1, max: 50 },
                  }}
                />
              </FormControl>
            </>
          )}
        </Stack>
      )}
    </BaseDrawer>
  );
}
