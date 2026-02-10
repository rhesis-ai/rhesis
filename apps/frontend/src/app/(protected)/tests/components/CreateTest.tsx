import React, { useState, useEffect, useCallback } from 'react';
import {
  TextField,
  FormControl,
  Stack,
  MenuItem,
  Autocomplete,
  Box,
  Avatar,
  Typography,
  Divider,
} from '@mui/material';
import BaseFreesoloAutocomplete, {
  AutocompleteOption as FreeSoloOption,
} from '@/components/common/BaseFreesoloAutocomplete';
import {
  TestBulkCreateRequest,
  PriorityLevel,
  TestDetail,
} from '@/utils/api-client/interfaces/tests';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { UUID } from 'crypto';
import PersonIcon from '@mui/icons-material/Person';
import { User } from '@/utils/api-client/interfaces/user';
import { filterUniqueValidOptions } from '@/components/common/BaseDrawer';
import { Status } from '@/utils/api-client/interfaces/status';
import { ENTITY_TYPES } from '@/utils/api-client/config';

type AutocompleteOption = FreeSoloOption;

// Extended interface for form data
interface TestFormData {
  behavior_id?: UUID | string;
  topic_id?: UUID | string;
  category_id?: UUID | string;
  priorityLevel?: PriorityLevel;
  prompt_content?: string;
  assignee_id?: UUID;
  owner_id?: UUID;
  status_id?: UUID;
}

interface UserOption extends User {
  displayName: string;
}

interface CreateTestProps {
  sessionToken: string;
  onSuccess?: () => void;
  onError?: (error: string) => void;
  defaultOwnerId?: UUID;
  submitRef?: React.MutableRefObject<(() => Promise<void>) | undefined>;
  test?: TestDetail;
}

const PRIORITY_OPTIONS: PriorityLevel[] = ['Low', 'Medium', 'High', 'Urgent'];

const defaultFormData: TestFormData = {
  behavior_id: undefined,
  topic_id: undefined,
  category_id: undefined,
  priorityLevel: 'Medium',
  prompt_content: '',
  assignee_id: undefined,
  owner_id: undefined,
  status_id: undefined,
};

export default function CreateTest({
  sessionToken,
  onSuccess,
  onError,
  defaultOwnerId,
  submitRef,
  test,
}: CreateTestProps) {
  const [_loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<TestFormData>(defaultFormData);

  // Reset form to default state
  const resetForm = useCallback(() => {
    setFormData({
      ...defaultFormData,
      owner_id: defaultOwnerId,
    });
  }, [defaultOwnerId]);

  // Options for dropdowns
  const [behaviors, setBehaviors] = useState<AutocompleteOption[]>([]);
  const [topics, setTopics] = useState<AutocompleteOption[]>([]);
  const [categories, setCategories] = useState<AutocompleteOption[]>([]);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [statuses, setStatuses] = useState<Status[]>([]);

  // Initialize form data from test when provided
  useEffect(() => {
    if (test) {
      setFormData({
        behavior_id: test.behavior?.id || test.behavior?.name || undefined,
        topic_id: test.topic?.id || test.topic?.name || undefined,
        category_id: test.category?.id || undefined,
        priorityLevel: test.priorityLevel || 'Medium',
        prompt_content: test.prompt?.content || '',
        assignee_id: test.assignee?.id || undefined,
        owner_id: test.owner?.id || undefined,
        status_id: test.status?.id || undefined,
      });
    } else if (defaultOwnerId) {
      // Only set default owner if no test is provided
      setFormData(prev => ({
        ...prev,
        owner_id: defaultOwnerId,
      }));
    }
  }, [test, defaultOwnerId]);

  // Load options when component mounts
  useEffect(() => {
    const loadOptions = async () => {
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const behaviorClient = apiFactory.getBehaviorClient();
        const topicClient = apiFactory.getTopicClient();
        const categoryClient = apiFactory.getCategoryClient();
        const usersClient = apiFactory.getUsersClient();
        const statusClient = apiFactory.getStatusClient();

        // Load all options in parallel
        const [
          behaviorsData,
          topicsData,
          categoriesData,
          usersData,
          statusesData,
        ] = await Promise.all([
          behaviorClient.getBehaviors({ sort_by: 'name', sort_order: 'asc' }),
          topicClient.getTopics({
            sort_by: 'name',
            sort_order: 'asc',
            entity_type: 'Test',
          }),
          categoryClient.getCategories({
            sort_by: 'name',
            sort_order: 'asc',
            entity_type: 'Test',
          }),
          usersClient.getUsers(),
          statusClient.getStatuses({
            sort_by: 'name',
            sort_order: 'asc',
            entity_type: ENTITY_TYPES.test,
          }),
        ]);

        // Filter out duplicates and invalid entries before setting state
        setBehaviors(filterUniqueValidOptions(behaviorsData));
        setTopics(filterUniqueValidOptions(topicsData));
        setCategories(filterUniqueValidOptions(categoriesData));
        setStatuses(statusesData);

        // Transform users into options with display names
        const transformedUsers = usersData.data.map(user => ({
          ...user,
          displayName:
            user.name ||
            `${user.given_name || ''} ${user.family_name || ''}`.trim() ||
            user.email,
        }));
        setUsers(transformedUsers);
      } catch (err) {
        onError?.((err as Error).message);
      }
    };

    loadOptions();
  }, [sessionToken, onError]);

  // Update form data with autocomplete value (either string or option)
  const handleFieldChange =
    (field: keyof TestFormData) =>
    (value: AutocompleteOption | string | null) => {
      if (value === null) {
        // Cleared value
        setFormData(prev => ({
          ...prev,
          [field]: undefined,
        }));
      } else if (typeof value === 'string') {
        // User entered a string that is not a UUID
        setFormData(prev => ({
          ...prev,
          [field]: value,
        }));
      } else if (value && 'inputValue' in value && value.inputValue) {
        // User selected "Add new" option
        setFormData(prev => ({
          ...prev,
          [field]: value.inputValue,
        }));
      } else if (value && 'id' in value) {
        // User selected an existing option
        setFormData(prev => ({
          ...prev,
          [field]: value.id,
        }));
      }
    };

  const handleChange =
    (field: keyof TestFormData) =>
    (event: React.ChangeEvent<HTMLInputElement | { value: unknown }>) => {
      setFormData(prev => ({
        ...prev,
        [field]: event.target.value,
      }));
    };

  const handleSubmit = useCallback(
    async (e?: React.FormEvent) => {
      if (e) {
        e.preventDefault();
      }
      try {
        setLoading(true);

        // Validate required fields
        if (!formData.prompt_content || formData.prompt_content.trim() === '') {
          throw new Error('Prompt content is required');
        }

        const apiFactory = new ApiClientFactory(sessionToken);
        const testsClient = apiFactory.getTestsClient();

        // Format prompt data
        const promptData = {
          content: formData.prompt_content || '',
          language_code: 'en', // Default to English
        };

        // Convert priority from string to numeric value
        const priorityMap: Record<PriorityLevel, number> = {
          Low: 0,
          Medium: 1,
          High: 2,
          Urgent: 3,
        };
        const numericPriority: number = formData.priorityLevel
          ? priorityMap[formData.priorityLevel]
          : 1; // Default to Medium (1) if undefined

        // Helper function to validate UUID
        const isValidUUID = (str: string) => {
          const uuidRegex =
            /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
          return uuidRegex.test(str);
        };

        // Get behavior name - always use name, not ID
        let behaviorName = '';
        if (formData.behavior_id) {
          if (typeof formData.behavior_id === 'string') {
            const selectedBehavior = behaviors.find(
              b => b.id === formData.behavior_id
            );
            if (selectedBehavior) {
              behaviorName = selectedBehavior.name;
            } else {
              // If not found as UUID, use as direct input
              behaviorName = formData.behavior_id.trim();
            }
          }
        }

        if (!behaviorName) {
          throw new Error('Behavior is required');
        }

        // Get topic name - always use name, not ID
        let topicName = '';
        if (formData.topic_id) {
          if (typeof formData.topic_id === 'string') {
            const selectedTopic = topics.find(t => t.id === formData.topic_id);
            if (selectedTopic) {
              topicName = selectedTopic.name;
            } else {
              // If not found as UUID, use as direct input
              topicName = formData.topic_id.trim();
            }
          }
        }

        if (!topicName) {
          throw new Error('Topic is required');
        }

        // Get category name - always use name, not ID
        let categoryName = '';
        if (formData.category_id) {
          if (typeof formData.category_id === 'string') {
            const selectedCategory = categories.find(
              c => c.id === formData.category_id
            );
            if (selectedCategory) {
              categoryName = selectedCategory.name;
            } else {
              // If not found as UUID, use as direct input
              categoryName = formData.category_id.trim();
            }
          }
        }

        if (!categoryName) {
          throw new Error('Category is required');
        }

        // Create bulk request data
        const bulkRequest: TestBulkCreateRequest = {
          tests: [
            {
              prompt: promptData,
              behavior: behaviorName,
              category: categoryName,
              topic: topicName,
              test_configuration: {},
              priority: numericPriority,
              // Only include IDs if they are valid UUIDs
              ...(formData.assignee_id && isValidUUID(formData.assignee_id)
                ? { assignee_id: formData.assignee_id }
                : {}),
              ...(formData.owner_id && isValidUUID(formData.owner_id)
                ? { owner_id: formData.owner_id }
                : {}),
              ...(formData.status_id
                ? {
                    status: statuses.find(s => s.id === formData.status_id)
                      ?.name,
                  }
                : {}),
            },
          ],
        };

        const response = await testsClient.createTestsBulk(bulkRequest);

        if (!response.success) {
          throw new Error(response.message);
        }

        // Reset form to default state after successful creation
        resetForm();
        onSuccess?.();
      } catch (err) {
        onError?.((err as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [
      formData,
      sessionToken,
      onSuccess,
      onError,
      behaviors,
      topics,
      categories,
      statuses,
      setLoading,
      resetForm,
    ]
  );

  // Expose handleSubmit to parent component via ref
  useEffect(() => {
    if (submitRef) {
      submitRef.current = handleSubmit;
    }
  }, [submitRef, handleSubmit]);

  return (
    <Stack spacing={3}>
      <Typography variant="subtitle2" color="text.secondary">
        Workflow
      </Typography>

      <FormControl fullWidth>
        <TextField
          select
          label="Status"
          value={formData.status_id || ''}
          onChange={event => {
            setFormData(prev => ({
              ...prev,
              status_id: event.target.value as UUID,
            }));
          }}
          required
        >
          {statuses.map(status => (
            <MenuItem key={status.id} value={status.id}>
              {status.name}
            </MenuItem>
          ))}
        </TextField>
      </FormControl>

      <Autocomplete
        options={users}
        value={users.find(user => user.id === formData.assignee_id) || null}
        onChange={(event, newValue) => {
          setFormData(prev => ({
            ...prev,
            assignee_id: newValue?.id,
          }));
        }}
        getOptionLabel={option => option.displayName}
        renderInput={params => (
          <TextField
            {...params}
            label="Assignee"
            InputProps={{
              ...params.InputProps,
              startAdornment: formData.assignee_id && (
                <Box sx={{ display: 'flex', alignItems: 'center', pl: 2 }}>
                  <Avatar
                    src={
                      users.find(u => u.id === formData.assignee_id)?.picture
                    }
                    sx={{ width: 24, height: 24 }}
                  >
                    <PersonIcon />
                  </Avatar>
                </Box>
              ),
            }}
          />
        )}
        renderOption={(props, option) => {
          const { key: _key, ...otherProps } = props;
          return (
            <li key={option.id} {...otherProps}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Avatar src={option.picture} sx={{ width: 32, height: 32 }}>
                  <PersonIcon />
                </Avatar>
                <Typography>{option.displayName}</Typography>
              </Box>
            </li>
          );
        }}
      />

      <Autocomplete
        options={users}
        value={users.find(user => user.id === formData.owner_id) || null}
        onChange={(event, newValue) => {
          setFormData(prev => ({
            ...prev,
            owner_id: newValue?.id,
          }));
        }}
        getOptionLabel={option => option.displayName}
        renderInput={params => (
          <TextField
            {...params}
            label="Owner"
            InputProps={{
              ...params.InputProps,
              startAdornment: formData.owner_id && (
                <Box sx={{ display: 'flex', alignItems: 'center', pl: 2 }}>
                  <Avatar
                    src={users.find(u => u.id === formData.owner_id)?.picture}
                    sx={{ width: 24, height: 24 }}
                  >
                    <PersonIcon />
                  </Avatar>
                </Box>
              ),
            }}
          />
        )}
        renderOption={(props, option) => {
          const { key: _key, ...otherProps } = props;
          return (
            <li key={option.id} {...otherProps}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Avatar src={option.picture} sx={{ width: 32, height: 32 }}>
                  <PersonIcon />
                </Avatar>
                <Typography>{option.displayName}</Typography>
              </Box>
            </li>
          );
        }}
      />

      <Divider sx={{ my: 1 }} />

      <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2 }}>
        Test Details
      </Typography>

      <BaseFreesoloAutocomplete
        options={behaviors}
        value={formData.behavior_id}
        onChange={handleFieldChange('behavior_id')}
        label="Behavior"
        required
      />

      <BaseFreesoloAutocomplete
        options={topics}
        value={formData.topic_id}
        onChange={handleFieldChange('topic_id')}
        label="Topic"
        required
      />

      <BaseFreesoloAutocomplete
        options={categories}
        value={formData.category_id}
        onChange={handleFieldChange('category_id')}
        label="Category"
        required
      />

      <FormControl fullWidth>
        <TextField
          select
          label="Priority"
          value={formData.priorityLevel || 'Medium'}
          onChange={handleChange('priorityLevel')}
          required
        >
          {PRIORITY_OPTIONS.map(option => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </TextField>
      </FormControl>

      <FormControl fullWidth>
        <TextField
          label="Prompt Content"
          value={formData.prompt_content}
          onChange={handleChange('prompt_content')}
          multiline
          rows={4}
          required
        />
      </FormControl>
    </Stack>
  );
}
