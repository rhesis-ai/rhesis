'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Box, Typography, CircularProgress } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ServicesClient } from '@/utils/api-client/services-client';
import { useNotifications } from '@/components/common/NotificationContext';
import {
  FlowStep,
  GenerationMode,
  ConfigChips,
  TestSample,
  MultiTurnTestSample,
  AnyTestSample,
  ChatMessage,
  ChipConfig,
  TestType,
} from './shared/types';
import { Project } from '@/utils/api-client/interfaces/project';
import { readActiveProjectId } from '@/utils/active-project';
import {
  GenerateTestsRequest,
  GenerationConfig,
  SourceData,
  TestPipelineEvent,
} from '@/utils/api-client/interfaces/test-set';
import { Model } from '@/utils/api-client/interfaces/model';
import { Source } from '@/utils/api-client/interfaces/source';
import TestInputScreen from './TestInputScreen';
import TestGenerationInterface from './TestGenerationInterface';
import TestConfigurationConfirmation from './TestConfigurationConfirmation';
import { TEMPLATES } from '@/config/test-templates';
import { getApiErrorMessage } from '@/utils/error-utils';

interface TestGenerationFlowProps {
  sessionToken: string;
}

// Initial empty chip configurations
const createEmptyChips = (): ConfigChips => {
  return {
    behavior: [],
    topics: [],
    category: [],
  };
};

const singularizeCategoryName = (category: keyof ConfigChips): string => {
  switch (category) {
    case 'behavior':
      return 'behavior';
    case 'topics':
      return 'topic';
    case 'category':
      return 'category';
    default:
      return category;
  }
};

// API response types for generated tests
interface GeneratedMultiTurnTest {
  test_configuration: {
    goal: string;
    instructions: string;
    restrictions: string;
    scenario: string;
  };
  behavior: string;
  topic: string;
  category: string;
}

interface GeneratedSingleTurnTest {
  prompt: { content: string; expected_response?: string };
  behavior: string;
  topic: string;
  metadata?: {
    sources?: Array<{
      name?: string;
      source?: string;
      title?: string;
      description?: string;
      content?: string;
    }>;
  };
}

// Helper function to generate samples based on test type
const generateSamplesForTestType = async (
  servicesClient: ServicesClient,
  testType: TestType,
  activeBehaviors: string[],
  activeTopics: string[],
  activeCategories: string[],
  description: string,
  projectName: string,
  sources: SourceData[],
  numTests: number = 5,
  modelId?: string | null
): Promise<AnyTestSample[]> => {
  if (testType === 'multi_turn') {
    // Generate multi-turn tests
    const response = await servicesClient.generateMultiTurnTests({
      generation_prompt: description,
      behavior: activeBehaviors,
      category: activeCategories,
      topic: activeTopics,
      num_tests: numTests,
      ...(modelId ? { model_id: modelId } : {}),
    });

    if (response.tests?.length) {
      return response.tests.map(
        (test: unknown, index: number): MultiTurnTestSample => {
          const t = test as GeneratedMultiTurnTest;
          return {
            id: `sample-${Date.now()}-${index}`,
            testType: 'multi_turn',
            prompt: {
              goal: t.test_configuration.goal,
              instructions: t.test_configuration.instructions,
              restrictions: t.test_configuration.restrictions,
              scenario: t.test_configuration.scenario,
            },
            behavior: t.behavior,
            topic: t.topic,
            category: t.category,
            rating: null,
            feedback: '',
            context: [],
          };
        }
      );
    }
  } else {
    // Generate single-turn tests
    const generationPrompt = `Generate ${numTests} single interaction test cases for: ${description || 'general testing'}`;

    const config = {
      generation_prompt: generationPrompt,
      behaviors: activeBehaviors,
      categories: activeCategories,
      topics: activeTopics,
      additional_context: JSON.stringify({
        project_context: projectName || 'General',
        test_type: 'Single interaction tests',
        output_format: 'Generate only user inputs',
      }),
    };

    const response = await servicesClient.generateTests({
      config,
      num_tests: numTests,
      sources: sources,
      ...(modelId ? { model_id: modelId } : {}),
    });

    if (response.tests?.length) {
      return response.tests.map((test: unknown, index: number): TestSample => {
        const t = test as GeneratedSingleTurnTest;
        return {
          id: `sample-${Date.now()}-${index}`,
          testType: 'single_turn',
          prompt: t.prompt.content,
          behavior: t.behavior,
          topic: t.topic,
          rating: null,
          feedback: '',
          context: t.metadata?.sources
            ?.map(source => ({
              name: source.name || source.source || source.title || '',
              description: source.description || '',
              content: source.content || '',
            }))
            .filter(src => src.name && src.name.trim().length > 0),
        };
      });
    }
  }

  return [];
};

const mapCategoryToChipKey = (category: string): keyof ConfigChips | null => {
  switch (category) {
    case 'behaviors':
      return 'behavior';
    case 'topics':
      return 'topics';
    case 'categories':
      return 'category';
    default:
      return null;
  }
};

const categoryColorVariant: Record<
  string,
  'blue' | 'purple' | 'orange' | 'green'
> = {
  behaviors: 'blue',
  topics: 'green',
  categories: 'purple',
};

const convertTestEventToSample = (
  event: Extract<TestPipelineEvent, { type: 'test' }>
): AnyTestSample => {
  if (event.test_type === 'multi_turn') {
    const t = event.test as unknown as GeneratedMultiTurnTest;
    return {
      id: `sample-${Date.now()}-${event.index}`,
      testType: 'multi_turn',
      prompt: {
        goal: t.test_configuration.goal,
        instructions: t.test_configuration.instructions,
        restrictions: t.test_configuration.restrictions,
        scenario: t.test_configuration.scenario,
      },
      behavior: t.behavior,
      topic: t.topic,
      category: t.category,
      rating: null,
      feedback: '',
      context: [],
    };
  }
  const t = event.test as unknown as GeneratedSingleTurnTest;
  return {
    id: `sample-${Date.now()}-${event.index}`,
    testType: 'single_turn',
    prompt: t.prompt.content,
    behavior: t.behavior,
    topic: t.topic,
    rating: null,
    feedback: '',
    context: t.metadata?.sources
      ?.map(source => ({
        name: source.name || source.source || source.title || '',
        description: source.description || '',
        content: source.content || '',
      }))
      .filter(src => src.name && src.name.trim().length > 0),
  };
};

/**
 * TestGenerationFlow Component
 * Main orchestrator for the test generation flow
 */
export default function TestGenerationFlow({
  sessionToken,
}: TestGenerationFlowProps) {
  const router = useRouter();
  const { show } = useNotifications();

  // Check if template exists before initializing state
  const hasTemplate =
    typeof window !== 'undefined' &&
    sessionStorage.getItem('selectedTemplateId') !== null;

  // Get test type from sessionStorage
  const storedTestType =
    typeof window !== 'undefined'
      ? (sessionStorage.getItem('testType') as TestType | null)
      : null;

  // Navigation State - start with null to prevent premature rendering
  const [currentScreen, setCurrentScreen] = useState<FlowStep | null>(
    hasTemplate ? null : 'input'
  );
  const [mode, setMode] = useState<GenerationMode | null>(
    hasTemplate ? 'template' : 'ai'
  );
  const [testType, setTestType] = useState<TestType>(
    storedTestType || 'single_turn'
  );

  // Data State
  const [description, setDescription] = useState('');
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]); // Keep for display
  const [selectedSources, setSelectedSources] = useState<SourceData[]>([]); // Full source data
  // Project comes from the active-project context; not user-selectable in this flow.
  const selectedProjectId = readActiveProjectId();
  const [selectedEndpointId, setSelectedEndpointId] = useState<string | null>(
    null
  );
  const [configChips, setConfigChips] =
    useState<ConfigChips>(createEmptyChips());
  const [testSamples, setTestSamples] = useState<AnyTestSample[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [testSetName, setTestSetName] = useState('');
  const [numTests, setNumTests] = useState<number>(50);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);

  // UI State
  const [isGenerating, setIsGenerating] = useState(false);
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isFinishing, setIsFinishing] = useState(false);
  const [regeneratingSampleId, setRegeneratingSampleId] = useState<
    string | null
  >(null);

  // Prefetched dropdown data — fetched eagerly on mount so selectors open instantly
  const [prefetchedModels, setPrefetchedModels] = useState<Model[]>([]);
  const [prefetchedSources, setPrefetchedSources] = useState<Source[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [isLoadingSources, setIsLoadingSources] = useState(true);

  useEffect(() => {
    const factory = new ApiClientFactory(sessionToken);

    factory
      .getModelsClient()
      .getModels({ sort_by: 'name', sort_order: 'asc', skip: 0, limit: 100 })
      .then(res => setPrefetchedModels(res.data || []))
      .catch(() => setPrefetchedModels([]))
      .finally(() => setIsLoadingModels(false));

    factory
      .getSourcesClient()
      .getSources({ limit: 100, skip: 0 })
      .then(res =>
        setPrefetchedSources(Array.isArray(res) ? res : res?.data || [])
      )
      .catch(() => setPrefetchedSources([]))
      .finally(() => setIsLoadingSources(false));
  }, [sessionToken]);

  const handleTestTypeChange = useCallback((newType: TestType) => {
    setTestType(newType);
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('testType', newType);
    }
    // Reset flow so the user configures fresh for the new type
    setCurrentScreen('input');
    setConfigChips(createEmptyChips());
    setTestSamples([]);
    setChatMessages([]);
    setDescription('');
  }, []);

  const handlePipelineEvent = useCallback(
    (event: TestPipelineEvent) => {
      switch (event.type) {
        case 'config_item': {
          const chipKey = mapCategoryToChipKey(event.category);
          if (!chipKey) break;
          const chip: ChipConfig = {
            id: event.name.toLowerCase().replace(/\s+/g, '-'),
            label: event.name,
            description: event.description,
            active: event.active,
            colorVariant: categoryColorVariant[event.category] || 'blue',
          };
          setConfigChips(prev => ({
            ...prev,
            [chipKey]: [...prev[chipKey], chip],
          }));
          break;
        }
        case 'config_done':
          setIsLoadingConfig(false);
          break;
        case 'test': {
          const sample = convertTestEventToSample(event);
          setTestSamples(prev => [...prev, sample]);
          break;
        }
        case 'tests_done':
          setIsLoadingSamples(false);
          break;
        case 'error':
          show(`Generation error: ${event.message}`, {
            severity: 'error',
          });
          if (event.phase === 'config') setIsLoadingConfig(false);
          if (event.phase === 'tests') setIsLoadingSamples(false);
          break;
        case 'done':
          setIsLoadingConfig(false);
          setIsLoadingSamples(false);
          break;
      }
    },
    [show]
  );

  // Check for template on mount and stream config + tests via pipeline
  useEffect(() => {
    const initializeFromTemplate = async () => {
      const templateId = sessionStorage.getItem('selectedTemplateId');
      if (!templateId) return;

      try {
        const template = TEMPLATES.find(t => t.id === templateId);
        if (!template) {
          throw new Error(`Template with ID ${templateId} not found`);
        }
        sessionStorage.removeItem('selectedTemplateId');

        setMode('template');
        setDescription(template.description);
        setCurrentScreen('interface');
        setConfigChips(createEmptyChips());
        setTestSamples([]);
        setIsLoadingConfig(true);
        setIsLoadingSamples(true);

        const apiFactory = new ApiClientFactory(sessionToken);
        const servicesClient = apiFactory.getServicesClient();

        await servicesClient.generateTestPipelineStream(
          {
            prompt: template.prompt,
            project_id: selectedProjectId || undefined,
            test_type: testType,
            num_tests: 5,
            sources: selectedSources,
            ...(selectedModelId ? { model_id: selectedModelId } : {}),
          },
          { onEvent: handlePipelineEvent }
        );
      } catch (e) {
        setIsLoadingConfig(false);
        setIsLoadingSamples(false);
        show(getApiErrorMessage(e, 'Failed to load template'), {
          severity: 'error',
        });
      }
    };

    initializeFromTemplate();
    // selectedProjectId, selectedSources, testType, selectedModelId intentionally excluded - template init runs once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionToken, show, handlePipelineEvent]);

  // Input Screen Handler
  const handleContinueFromInput = useCallback(
    async (desc: string, sources: SourceData[]) => {
      setDescription(desc);
      setSelectedSources(sources);
      setSelectedSourceIds(sources.map(s => s.id));
      setCurrentScreen('interface');
      setConfigChips(createEmptyChips());
      setTestSamples([]);
      setIsLoadingConfig(true);
      setIsLoadingSamples(true);

      let apiFactory: ApiClientFactory;
      try {
        apiFactory = new ApiClientFactory(sessionToken);
      } catch (_error) {
        setIsLoadingConfig(false);
        setIsLoadingSamples(false);
        show('Failed to initialize services', { severity: 'error' });
        return;
      }

      // Fetch project for display purposes
      if (selectedProjectId) {
        try {
          const projectsClient = apiFactory.getProjectsClient();
          const fetchedProject =
            await projectsClient.getProject(selectedProjectId);
          setProject(fetchedProject);
        } catch (_error) {
          show('Failed to load project', { severity: 'warning' });
        }
      } else {
        setProject(null);
      }

      try {
        const servicesClient = apiFactory.getServicesClient();
        await servicesClient.generateTestPipelineStream(
          {
            prompt: desc,
            project_id: selectedProjectId || undefined,
            test_type: testType,
            num_tests: 5,
            sources: sources,
            ...(selectedModelId ? { model_id: selectedModelId } : {}),
          },
          { onEvent: handlePipelineEvent }
        );
      } catch (error) {
        show(getApiErrorMessage(error, 'Failed to generate configuration'), {
          severity: 'error',
        });
        setIsLoadingConfig(false);
        setIsLoadingSamples(false);
      }
    },
    [
      sessionToken,
      show,
      testType,
      selectedProjectId,
      selectedModelId,
      handlePipelineEvent,
    ]
  );

  // Generate test samples
  const generateSamples = useCallback(async () => {
    setTestSamples([]);
    setIsLoadingSamples(true);

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();

      const pipelineConfig = {
        behaviors: configChips.behavior.map(c => ({
          name: c.label,
          description: c.description || '',
          active: c.active,
        })),
        topics: configChips.topics.map(c => ({
          name: c.label,
          description: c.description || '',
          active: c.active,
        })),
        categories: configChips.category.map(c => ({
          name: c.label,
          description: c.description || '',
          active: c.active,
        })),
      };

      await servicesClient.generateTestPipelineStream(
        {
          prompt: description,
          project_id: selectedProjectId || undefined,
          test_type: testType,
          num_tests: 5,
          sources: selectedSources.length > 0 ? selectedSources : undefined,
          model_id: selectedModelId || undefined,
          config: pipelineConfig,
        },
        { onEvent: handlePipelineEvent }
      );
    } catch (_error) {
      show('Failed to regenerate samples', { severity: 'error' });
      setIsLoadingSamples(false);
    }
  }, [
    sessionToken,
    description,
    selectedProjectId,
    selectedSources,
    configChips,
    testType,
    selectedModelId,
    handlePipelineEvent,
    show,
  ]);

  // Regenerate sample with feedback
  const handleRegenerateSample = useCallback(
    async (sampleId: string, feedback: string) => {
      // Find the sample
      const sample = testSamples.find(s => s.id === sampleId);
      if (!sample) return;

      setRegeneratingSampleId(sampleId);

      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const servicesClient = apiFactory.getServicesClient();

        // Build config from configuration with feedback
        const activeBehaviors = configChips.behavior
          .filter(c => c.active)
          .map(c => c.label);
        const activeTopics = configChips.topics
          .filter(c => c.active)
          .map(c => c.label);
        const activeCategories = configChips.category
          .filter(c => c.active)
          .map(c => c.label);

        // For single-turn tests, use rated samples
        if (testType === 'single_turn' && sample.testType === 'single_turn') {
          const generationPrompt = `Generate an improved test case based on feedback: ${feedback}`;

          const ratedSample = {
            prompt: sample.prompt,
            response: sample.response || '',
            rating: sample.rating || 1,
            feedback: feedback,
          };

          const config = {
            generation_prompt: generationPrompt,
            behaviors: activeBehaviors,
            categories: activeCategories,
            topics: activeTopics,
            additional_context: JSON.stringify({
              project_context: project?.name || 'General',
              test_type: 'Single interaction tests',
              output_format: 'Generate only user inputs',
              rated_samples: [ratedSample],
            }),
          };

          const response = await servicesClient.generateTests({
            config,
            num_tests: 1,
            sources: selectedSources,
            ...(selectedModelId ? { model_id: selectedModelId } : {}),
          });

          if (response.tests?.length) {
            const t = response.tests[0] as GeneratedSingleTurnTest;
            const newSample: TestSample = {
              id: `sample-${Date.now()}-regenerated`,
              testType: 'single_turn',
              prompt: t?.prompt?.content || '',
              behavior: t?.behavior || '',
              topic: t?.topic || '',
              rating: null,
              feedback: '',
              context: t?.metadata?.sources
                ?.map(source => ({
                  name: source.name || source.source || source.title || '',
                  description: source.description || '',
                  content: source.content || '',
                }))
                .filter(src => src.name && src.name.trim().length > 0),
            };

            setTestSamples(prev =>
              prev.map(s => (s.id === sampleId ? newSample : s))
            );
          }
        } else {
          // For multi-turn, just regenerate a new one
          const newSamples = await generateSamplesForTestType(
            servicesClient,
            testType,
            activeBehaviors,
            activeTopics,
            activeCategories,
            `${description}\n\nFeedback: ${feedback}`,
            project?.name || 'General',
            selectedSources,
            1,
            selectedModelId
          );

          if (newSamples.length > 0) {
            setTestSamples(prev =>
              prev.map(s => (s.id === sampleId ? newSamples[0] : s))
            );
          }
        }

        show('Sample regenerated successfully', { severity: 'success' });
      } catch (_error) {
        show('Failed to regenerate sample', { severity: 'error' });
      } finally {
        setRegeneratingSampleId(null);
      }
    },
    [
      sessionToken,
      description,
      configChips,
      selectedSources,
      selectedModelId,
      project,
      testSamples,
      testType,
      show,
    ]
  );

  // Interface Handlers
  const handleChipToggle = useCallback(
    (category: keyof ConfigChips, chipId: string) => {
      setConfigChips(prev => {
        const categoryChips = prev[category];
        const chipToToggle = categoryChips.find(c => c.id === chipId);

        // Prevent deselecting if this is the last active chip in the category
        if (chipToToggle?.active) {
          const activeCount = categoryChips.filter(c => c.active).length;
          if (activeCount === 1) {
            // Don't allow deselecting the last active chip
            const categoryNameSingular = singularizeCategoryName(category);
            show(`At least one ${categoryNameSingular} must be selected`, {
              severity: 'warning',
            });
            return prev;
          }
        }

        return {
          ...prev,
          [category]: categoryChips.map(chip =>
            chip.id === chipId ? { ...chip, active: !chip.active } : chip
          ),
        };
      });
    },
    [show]
  );

  const handleSendMessage = useCallback(
    async (message: string) => {
      const chipStates: Array<{
        label: string;
        description: string;
        active: boolean;
        category: 'behavior' | 'topic' | 'category' | 'scenario';
      }> = [
        ...configChips.behavior.map(chip => ({
          label: chip.label,
          description: chip.description || '',
          active: chip.active,
          category: 'behavior' as const,
        })),
        ...configChips.topics.map(chip => ({
          label: chip.label,
          description: chip.description || '',
          active: chip.active,
          category: 'topic' as const,
        })),
        ...configChips.category.map(chip => ({
          label: chip.label,
          description: chip.description || '',
          active: chip.active,
          category: 'category' as const,
        })),
      ];

      const newMessage: ChatMessage = {
        id: `msg-${Date.now()}`,
        type: 'user',
        content: message,
        timestamp: new Date(),
        chip_states: chipStates,
      };
      setChatMessages(prev => [...prev, newMessage]);

      setIsGenerating(true);
      setConfigChips(createEmptyChips());
      setTestSamples([]);
      setIsLoadingConfig(true);
      setIsLoadingSamples(true);

      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const servicesClient = apiFactory.getServicesClient();

        const previousMessages = chatMessages
          .filter(msg => msg.type === 'user')
          .map(msg => ({
            content: msg.content,
            timestamp: msg.timestamp.toISOString(),
            chip_states: msg.chip_states,
          }));

        await servicesClient.generateTestPipelineStream(
          {
            prompt: description,
            project_id: selectedProjectId || undefined,
            previous_messages: [
              ...previousMessages,
              {
                content: message,
                timestamp: newMessage.timestamp.toISOString(),
                chip_states: chipStates,
              },
            ],
            test_type: testType,
            num_tests: 5,
            sources: selectedSources.length > 0 ? selectedSources : undefined,
            model_id: selectedModelId || undefined,
          },
          { onEvent: handlePipelineEvent }
        );

        const assistantMessage: ChatMessage = {
          id: `msg-${Date.now()}-assistant`,
          type: 'assistant',
          content:
            'Configuration and samples updated based on your refinement.',
          timestamp: new Date(),
        };
        setChatMessages(prev => [...prev, assistantMessage]);
      } catch (_error) {
        show(getApiErrorMessage(_error, 'Failed to refine test generation'), {
          severity: 'error',
        });
      } finally {
        setIsGenerating(false);
        setIsLoadingConfig(false);
        setIsLoadingSamples(false);
      }
    },
    [
      sessionToken,
      description,
      selectedProjectId,
      selectedSources,
      selectedModelId,
      show,
      configChips,
      chatMessages,
      testType,
      handlePipelineEvent,
    ]
  );

  const handleRateSample = useCallback((sampleId: string, rating: number) => {
    setTestSamples(prev =>
      prev.map(sample =>
        sample.id === sampleId ? { ...sample, rating } : sample
      )
    );
  }, []);

  const handleSampleFeedbackChange = useCallback(
    (sampleId: string, feedback: string) => {
      setTestSamples(prev =>
        prev.map(sample =>
          sample.id === sampleId ? { ...sample, feedback } : sample
        )
      );
    },
    []
  );

  const handleLoadMoreSamples = useCallback(async () => {
    setIsLoadingMore(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();

      const activeBehaviors = configChips.behavior
        .filter(c => c.active)
        .map(c => c.label);
      const activeTopics = configChips.topics
        .filter(c => c.active)
        .map(c => c.label);
      const activeCategories = configChips.category
        .filter(c => c.active)
        .map(c => c.label);

      const newSamples = await generateSamplesForTestType(
        servicesClient,
        testType,
        activeBehaviors,
        activeTopics,
        activeCategories,
        description,
        project?.name || 'General',
        selectedSources,
        5,
        selectedModelId
      );

      setTestSamples(prev => [...prev, ...newSamples]);
    } catch (_error) {
      show('Failed to load more samples', { severity: 'error' });
    } finally {
      setIsLoadingMore(false);
    }
  }, [
    sessionToken,
    description,
    configChips,
    selectedSources,
    selectedModelId,
    project,
    testType,
    show,
  ]);

  // Final generation
  const handleGenerate = useCallback(async () => {
    if (!selectedProjectId) {
      show('A project must be selected before generating a test set.', {
        severity: 'error',
      });
      return;
    }
    setIsFinishing(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = apiFactory.getTestSetsClient();

      const activeBehaviors = configChips.behavior
        .filter(c => c.active)
        .map(c => c.label);
      const activeTopics = configChips.topics
        .filter(c => c.active)
        .map(c => c.label);
      const activeCategories = configChips.category
        .filter(c => c.active)
        .map(c => c.label);

      const clampedNumTests = Math.min(Math.max(numTests, 1), 200);
      const testCoverage =
        clampedNumTests <= 60
          ? 'focused'
          : clampedNumTests >= 150
            ? 'comprehensive'
            : 'standard';

      // Build additional context with samples and metadata
      const additionalContext = {
        project_name: project?.name,
        behaviors: activeBehaviors,
        purposes: activeTopics,
        test_type: testType,
        response_generation: 'prompt_only',
        test_coverage: testCoverage,
        samples: testSamples.map(sample => ({
          text: sample.prompt,
          behavior: sample.behavior,
          topic: sample.topic,
          rating: sample.rating,
          feedback: sample.feedback,
        })),
      };

      // Build new unified GenerationConfig
      const config: GenerationConfig = {
        generation_prompt: description,
        behaviors: activeBehaviors,
        categories: activeCategories,
        topics: activeTopics,
        additional_context: JSON.stringify(additionalContext),
      };

      // Build unified request
      const request: GenerateTestsRequest = {
        config,
        num_tests: clampedNumTests,
        batch_size: 20,
        sources: selectedSources,
        name: testSetName.trim(),
        test_type: testType,
        project_id: selectedProjectId,
        ...(selectedModelId ? { model_id: selectedModelId } : {}),
      };

      const response = await testSetsClient.generateTestSet(request);

      // Clean up sessionStorage
      if (typeof window !== 'undefined') {
        sessionStorage.removeItem('testType');
        sessionStorage.removeItem('selectedTemplateId');
      }

      // Redirect to the newly created test set's detail page
      router.push(`/test-sets/${response.test_set_id}`);
    } catch (_error) {
      show('Failed to start test generation. Please try again.', {
        severity: 'error',
      });
    } finally {
      setIsFinishing(false);
    }
  }, [
    sessionToken,
    configChips.behavior,
    configChips.topics,
    configChips.category,
    description,
    testSamples,
    numTests,
    testSetName,
    selectedSources,
    selectedModelId,
    selectedProjectId,
    project,
    testType,
    router,
    show,
  ]);

  // Navigation handlers
  const handleBackToTests = useCallback(() => {
    // Clean up sessionStorage when navigating away
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('testType');
      sessionStorage.removeItem('selectedTemplateId');
    }
    router.push('/test-sets');
  }, [router]);

  const handleBackToInput = useCallback(() => {
    // If user came from template selection, go back to landing screen
    if (mode === 'template') {
      router.push('/test-sets');
    } else {
      setCurrentScreen('input');
    }
  }, [mode, router]);

  const handleBackToInterface = useCallback(() => {
    setCurrentScreen('interface');
  }, []);

  const handleNextToConfirmation = useCallback(() => {
    setCurrentScreen('confirmation');
  }, []);

  const handleSourceRemove = useCallback((sourceId: string) => {
    setSelectedSources(prev => prev.filter(s => s.id !== sourceId));
    setSelectedSourceIds(prev => prev.filter(id => id !== sourceId));
  }, []);

  // Render current screen
  const renderCurrentScreen = () => {
    // Show loading state while initializing from template
    if (currentScreen === null) {
      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100vh',
            bgcolor: 'background.default',
          }}
        >
          <CircularProgress sx={{ mb: 2 }} />
          <Typography variant="body1">Loading template...</Typography>
        </Box>
      );
    }

    switch (currentScreen) {
      case 'input':
        return (
          <TestInputScreen
            sessionToken={sessionToken}
            testType={testType}
            onTestTypeChange={handleTestTypeChange}
            onContinue={handleContinueFromInput}
            initialDescription={description}
            selectedSourceIds={selectedSourceIds}
            onSourcesChange={(sources: SourceData[]) => {
              setSelectedSources(sources);
              setSelectedSourceIds(sources.map(s => s.id));
            }}
            selectedModelId={selectedModelId}
            onModelChange={setSelectedModelId}
            isLoading={isGenerating}
            onBack={handleBackToTests}
            prefetchedModels={prefetchedModels}
            isLoadingModels={isLoadingModels}
            prefetchedSources={prefetchedSources}
            isLoadingSources={isLoadingSources}
          />
        );

      case 'interface':
        return (
          <TestGenerationInterface
            testType={testType}
            configChips={configChips}
            testSamples={testSamples}
            chatMessages={chatMessages}
            description={description}
            selectedSources={selectedSources}
            selectedEndpointId={selectedEndpointId}
            onChipToggle={handleChipToggle}
            onSendMessage={handleSendMessage}
            onRateSample={handleRateSample}
            onSampleFeedbackChange={handleSampleFeedbackChange}
            onLoadMoreSamples={handleLoadMoreSamples}
            onRegenerateSamples={generateSamples}
            onRegenerate={handleRegenerateSample}
            onBack={handleBackToInput}
            onNext={handleNextToConfirmation}
            onEndpointChange={setSelectedEndpointId}
            onSourceRemove={handleSourceRemove}
            isGenerating={isGenerating}
            isLoadingConfig={isLoadingConfig}
            isLoadingSamples={isLoadingSamples}
            isLoadingMore={isLoadingMore}
            regeneratingSampleId={regeneratingSampleId}
          />
        );

      case 'confirmation':
        return (
          <TestConfigurationConfirmation
            testType={testType}
            configChips={configChips}
            testSetName={testSetName}
            numTests={numTests}
            sources={selectedSources}
            onBack={handleBackToInterface}
            onGenerate={handleGenerate}
            onTestSetNameChange={setTestSetName}
            onNumTestsChange={setNumTests}
            isGenerating={isFinishing}
          />
        );

      default:
        return null;
    }
  };

  return <>{renderCurrentScreen()}</>;
}
