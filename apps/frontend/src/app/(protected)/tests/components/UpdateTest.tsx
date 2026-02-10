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
  PriorityLevel,
  TestDetail,
  TestUpdate,
} from '@/utils/api-client/interfaces/tests';
import { PromptUpdate } from '@/utils/api-client/interfaces/prompt';
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

interface UpdateTestProps {
  sessionToken: string;
  onSuccess?: () => void;
  onError?: (error: string) => void;
  submitRef?: React.MutableRefObject<(() => Promise<void>) | undefined>;
  test: TestDetail; // Required for update
}

const PRIORITY_OPTIONS: PriorityLevel[] = ['Low', 'Medium', 'High', 'Urgent'];

const isValidUUID = (str: string): boolean => {
  const uuidRegex =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidRegex.test(str);
};

export default function UpdateTest({
  sessionToken,
  onSuccess,
  onError,
  submitRef,
  test,
}: UpdateTestProps) {
  const [_loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<TestFormData>({
    behavior_id: test.behavior?.id || test.behavior?.name || undefined,
    topic_id: test.topic?.name || test.topic?.id || undefined,
    category_id: test.category?.name || test.category?.id || undefined,
    priorityLevel: test.priorityLevel || 'Medium',
    prompt_content: test.prompt?.content || '',
    assignee_id: test.assignee?.id || undefined,
    owner_id: test.owner?.id || undefined,
    status_id: test.status?.id || undefined,
  });

  // Options for dropdowns
  const [behaviors, setBehaviors] = useState<AutocompleteOption[]>([]);
  const [topics, setTopics] = useState<AutocompleteOption[]>([]);
  const [categories, setCategories] = useState<AutocompleteOption[]>([]);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [statuses, setStatuses] = useState<Status[]>([]);

  // Initialize form data from test when provided
  useEffect(() => {
    if (test) {
      setFormData(prevData => {
        const newData = {
          behavior_id: test.behavior?.id || test.behavior?.name || undefined,
          topic_id: test.topic?.name || test.topic?.id || undefined,
          category_id: test.category?.name || test.category?.id || undefined,
          priorityLevel: test.priorityLevel || 'Medium',
          prompt_content: test.prompt?.content || '',
          assignee_id: test.assignee?.id || undefined,
          owner_id: test.owner?.id || undefined,
          status_id: test.status?.id,
        };

        return newData;
      });
    }
  }, [test, setFormData]);

  // Add effect to update formData when test changes
  useEffect(() => {
    if (test.status?.id) {
      setFormData(prev => ({ ...prev, status_id: test.status?.id }));
    }
  }, [test.status]);

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
  }, [
    sessionToken,
    onError,
    setBehaviors,
    setTopics,
    setCategories,
    setStatuses,
    setUsers,
    formData.status_id,
    test.status,
  ]);

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

  // Helper function to create a new behavior if needed
  const validateEntityName = (name: string): string => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      throw new Error('Entity name cannot be empty');
    }
    if (trimmedName.length < 2) {
      throw new Error('Entity name must be at least 2 characters long');
    }
    return trimmedName;
  };

  const getOrCreateBehavior = useCallback(
    async (name: string) => {
      const behaviorName = validateEntityName(name);
      const apiFactory = new ApiClientFactory(sessionToken);
      const behaviorClient = apiFactory.getBehaviorClient();

      // First check if it's a UUID
      if (isValidUUID(name)) {
        const existingBehavior = behaviors.find(b => b.id === name);
        if (existingBehavior) {
          return existingBehavior.name;
        }
      }

      // Then check by name
      const existingBehavior = behaviors.find(
        b => b.name.toLowerCase() === behaviorName.toLowerCase()
      );
      if (existingBehavior) {
        return existingBehavior.name;
      }

      try {
        // Create new behavior
        const newBehavior = await behaviorClient.createBehavior({
          name: behaviorName,
        });

        // Add to local state
        setBehaviors(prev => [
          ...prev,
          { id: newBehavior.id, name: newBehavior.name },
        ]);
        return newBehavior.name;
      } catch (error) {
        throw new Error(
          `Failed to create behavior: ${(error as Error).message}`
        );
      }
    },
    [sessionToken, behaviors, setBehaviors]
  );

  // Helper function to create a new topic if needed
  const getOrCreateTopic = useCallback(
    async (name: string) => {
      const topicName = validateEntityName(name);
      const apiFactory = new ApiClientFactory(sessionToken);
      const topicClient = apiFactory.getTopicClient();

      // First check if it's a UUID
      if (isValidUUID(name)) {
        const existingTopic = topics.find(t => t.id === name);
        if (existingTopic) {
          return existingTopic.name;
        }
      }

      // Then check by name
      const existingTopic = topics.find(
        t => t.name.toLowerCase() === topicName.toLowerCase()
      );
      if (existingTopic) {
        return existingTopic.name;
      }

      try {
        // Create new topic
        const newTopic = await topicClient.createTopic({
          name: topicName,
        });

        // Add to local state
        setTopics(prev => [...prev, { id: newTopic.id, name: newTopic.name }]);
        return newTopic.name;
      } catch (error) {
        throw new Error(`Failed to create topic: ${(error as Error).message}`);
      }
    },
    [sessionToken, topics, setTopics]
  );

  // Helper function to create a new category if needed
  const getOrCreateCategory = useCallback(
    async (name: string) => {
      const categoryName = validateEntityName(name);
      const apiFactory = new ApiClientFactory(sessionToken);
      const categoryClient = apiFactory.getCategoryClient();

      // First check if it's a UUID
      if (isValidUUID(name)) {
        const existingCategory = categories.find(c => c.id === name);
        if (existingCategory) {
          return existingCategory.name;
        }
      }

      // Then check by name
      const existingCategory = categories.find(
        c => c.name.toLowerCase() === categoryName.toLowerCase()
      );
      if (existingCategory) {
        return existingCategory.name;
      }

      try {
        // Create new category
        const newCategory = await categoryClient.createCategory({
          name: categoryName,
        });

        // Add to local state
        setCategories(prev => [
          ...prev,
          { id: newCategory.id, name: newCategory.name },
        ]);
        return newCategory.name;
      } catch (error) {
        throw new Error(
          `Failed to create category: ${(error as Error).message}`
        );
      }
    },
    [sessionToken, categories, setCategories]
  );

  const handleSubmit = useCallback(async () => {
    try {
      setLoading(true);

      // Validate required fields
      if (!formData.prompt_content?.trim()) {
        throw new Error('Prompt content is required');
      }

      const apiFactory = new ApiClientFactory(sessionToken);
      const testsClient = apiFactory.getTestsClient();
      const promptsClient = apiFactory.getPromptsClient();

      // First update the prompt if content has changed
      if (formData.prompt_content !== test.prompt?.content) {
        const promptUpdate: PromptUpdate = {
          content: formData.prompt_content.trim(),
          language_code: 'en', // Maintain existing language code
        };

        await promptsClient.updatePrompt(test.prompt_id, promptUpdate);
      }

      // Convert priority from string to numeric value
      const priorityMap: Record<PriorityLevel, number> = {
        Low: 0,
        Medium: 1,
        High: 2,
        Urgent: 3,
      };
      const numericPriority: number = formData.priorityLevel
        ? priorityMap[formData.priorityLevel]
        : 1;

      // Validate and process behavior
      if (!formData.behavior_id) {
        throw new Error('Behavior is required');
      }
      const behaviorName = await getOrCreateBehavior(formData.behavior_id);

      // Validate and process topic
      if (!formData.topic_id) {
        throw new Error('Topic is required');
      }
      const topicName = await getOrCreateTopic(formData.topic_id);

      // Validate and process category
      if (!formData.category_id) {
        throw new Error('Category is required');
      }
      const categoryName = await getOrCreateCategory(formData.category_id);

      // Get IDs for the selected entities
      const selectedBehavior = behaviors.find(
        b => b.name.toLowerCase() === behaviorName.toLowerCase()
      );
      const selectedTopic = topics.find(
        t => t.name.toLowerCase() === topicName.toLowerCase()
      );
      const selectedCategory = categories.find(
        c => c.name.toLowerCase() === categoryName.toLowerCase()
      );

      if (
        !selectedBehavior?.id ||
        !selectedTopic?.id ||
        !selectedCategory?.id
      ) {
        throw new Error('Failed to retrieve IDs for selected entities');
      }

      // Update the test using updateTest
      const updateData: TestUpdate = {
        behavior_id: selectedBehavior.id,
        topic_id: selectedTopic.id,
        category_id: selectedCategory.id,
        priority: numericPriority,
        assignee_id: formData.assignee_id || null,
        owner_id: formData.owner_id || null,
        status_id: formData.status_id || null,
      };

      await testsClient.updateTest(test.id, updateData);
      onSuccess?.();
    } catch (err) {
      onError?.((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [
    formData,
    test,
    sessionToken,
    onSuccess,
    onError,
    behaviors,
    topics,
    categories,
    getOrCreateBehavior,
    getOrCreateTopic,
    getOrCreateCategory,
    setLoading,
  ]);

  // Expose handleSubmit to parent component via ref
  useEffect(() => {
    if (submitRef) {
      submitRef.current = handleSubmit;
    }
  }, [submitRef, handleSubmit]);

  return (
    <Stack spacing={2}>
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
          const { key, ...otherProps } = props;
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
          const { key, ...otherProps } = props;
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
