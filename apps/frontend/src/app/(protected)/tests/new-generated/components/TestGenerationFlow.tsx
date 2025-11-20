'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Box, Typography, CircularProgress } from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import {
  FlowStep,
  GenerationMode,
  ConfigChips,
  TestSample,
  MultiTurnTestSample,
  AnyTestSample,
  ChatMessage,
  TestSetSize,
  TestTemplate,
  ChipConfig,
  TestType,
} from './shared/types';
import { Project } from '@/utils/api-client/interfaces/project';
import {
  TestSetGenerationRequest,
  TestSetGenerationConfig,
  GenerationSample,
  SourceData,
} from '@/utils/api-client/interfaces/test-set';
import TestInputScreen from './TestInputScreen';
import TestGenerationInterface from './TestGenerationInterface';
import TestConfigurationConfirmation from './TestConfigurationConfirmation';
import { TEMPLATES } from '@/config/test-templates';

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

// Helper function to generate samples based on test type
const generateSamplesForTestType = async (
  servicesClient: any,
  testType: TestType,
  activeBehaviors: string[],
  activeTopics: string[],
  activeCategories: string[],
  description: string,
  projectName: string,
  sources: SourceData[],
  numTests: number = 5
): Promise<AnyTestSample[]> => {
  if (testType === 'multi_turn') {
    // Generate multi-turn tests
    const response = await servicesClient.generateMultiTurnTests({
      generation_prompt: description,
      behavior: activeBehaviors,
      category: activeCategories,
      topic: activeTopics,
      num_tests: numTests,
    });

    if (response.tests?.length) {
      return response.tests.map(
        (test: any, index: number): MultiTurnTestSample => ({
          id: `sample-${Date.now()}-${index}`,
          testType: 'multi_turn',
          prompt: test.prompt,
          behavior: test.behavior,
          topic: test.topic,
          category: test.category,
          rating: null,
          feedback: '',
          context: [],
        })
      );
    }
  } else {
    // Generate single-turn tests
    const prompt = {
      project_context: projectName || 'General',
      behaviors: activeBehaviors,
      topics: activeTopics,
      categories: activeCategories,
      specific_requirements: description,
      test_type: 'Single interaction tests',
      output_format: 'Generate only user inputs',
    };

    const response = await servicesClient.generateTests({
      prompt,
      num_tests: numTests,
      sources: sources,
    });

    if (response.tests?.length) {
      return response.tests.map(
        (test: any, index: number): TestSample => ({
          id: `sample-${Date.now()}-${index}`,
          testType: 'single_turn',
          prompt: test.prompt.content,
          response: test.prompt.expected_response,
          behavior: test.behavior,
          topic: test.topic,
          rating: null,
          feedback: '',
          context: test.metadata?.sources
            ?.map((source: any) => ({
              name: source.name || source.source || source.title || '',
              description: source.description || '',
              content: source.content || '',
            }))
            .filter((src: any) => src.name && src.name.trim().length > 0),
        })
      );
    }
  }

  return [];
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
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    null
  );
  const [selectedEndpointId, setSelectedEndpointId] = useState<string | null>(
    null
  );
  const [configChips, setConfigChips] =
    useState<ConfigChips>(createEmptyChips());
  const [testSamples, setTestSamples] = useState<AnyTestSample[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [testSetSize, setTestSetSize] = useState<TestSetSize>('medium');
  const [testSetName, setTestSetName] = useState('');

  // UI State
  const [isGenerating, setIsGenerating] = useState(false);
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isFinishing, setIsFinishing] = useState(false);
  const [regeneratingSampleId, setRegeneratingSampleId] = useState<
    string | null
  >(null);

  // Check for template on mount and directly create config from template values
  useEffect(() => {
    const initializeFromTemplate = async () => {
      try {
        // Check if coming from template selection
        const templateId = sessionStorage.getItem('selectedTemplateId');
        if (templateId) {
          try {
            // Look up template by ID
            const template = TEMPLATES.find(t => t.id === templateId);
            if (!template) {
              throw new Error(`Template with ID ${templateId} not found`);
            }
            sessionStorage.removeItem('selectedTemplateId');

            setMode('template');
            setDescription(template.description);
            setIsGenerating(true);

            // Generate behaviors from template prompt using API
            const apiFactory = new ApiClientFactory(sessionToken);
            const servicesClient = apiFactory.getServicesClient();

            // Call generate/test_config with template prompt to get behaviors
            const configResponse = await servicesClient.generateTestConfig({
              prompt: template.prompt,
              project_id: selectedProjectId || undefined,
            });

            // Create chips from API response and template values
            const createChipsFromArray = (
              items: Array<{ name: string; description: string }> | undefined,
              colorVariant: 'blue' | 'purple' | 'orange' | 'green'
            ): ChipConfig[] => {
              if (!items || !Array.isArray(items)) {
                return [];
              }
              return items.map((item, index) => ({
                id: item.name.toLowerCase().replace(/\s+/g, '-'),
                label: item.name,
                description: item.description,
                active: true, // All template chips are active
                colorVariant,
              }));
            };

            const createChipsFromStringArray = (
              items: string[],
              colorVariant: 'blue' | 'purple' | 'orange' | 'green'
            ): ChipConfig[] => {
              return items.map(item => ({
                id: item.toLowerCase().replace(/\s+/g, '-'),
                label: item,
                description: '',
                active: true, // All template chips are active
                colorVariant,
              }));
            };

            const newConfigChips: ConfigChips = {
              behavior: createChipsFromArray(configResponse.behaviors, 'blue'),
              topics: createChipsFromStringArray(template.topics, 'green'),
              category: createChipsFromStringArray(template.category, 'purple'),
            };

            setConfigChips(newConfigChips);

            // Generate initial test samples directly
            const behaviorLabels = newConfigChips.behavior.map(
              chip => chip.label
            );

            const newSamples = await generateSamplesForTestType(
              servicesClient,
              testType,
              behaviorLabels,
              template.topics,
              template.category,
              template.description,
              project?.name || 'General',
              selectedSources,
              5
            );

            setTestSamples(newSamples);

            // Navigate to interface screen after samples are generated
            setCurrentScreen('interface');
            setIsGenerating(false);
          } catch (e) {
            setIsGenerating(false);
            show('Failed to load template', {
              severity: 'error',
            });
          }
        }
      } catch (error) {
        show('Failed to load template', { severity: 'error' });
      }
    };

    initializeFromTemplate();
  }, [sessionToken, show, project]);

  // Input Screen Handler
  const handleContinueFromInput = useCallback(
    async (desc: string, sources: SourceData[], projectId: string | null) => {
      setDescription(desc);
      setSelectedSources(sources);
      setSelectedSourceIds(sources.map(s => s.id));
      setSelectedProjectId(projectId);
      // Navigate immediately to interface screen
      setCurrentScreen('interface');
      setIsLoadingConfig(true);
      setIsLoadingSamples(true);

      let apiFactory: ApiClientFactory | undefined;
      let servicesClient:
        | ReturnType<ApiClientFactory['getServicesClient']>
        | undefined;

      try {
        apiFactory = new ApiClientFactory(sessionToken);
        servicesClient = apiFactory.getServicesClient();
      } catch (error) {
        setIsLoadingConfig(false);
        setIsLoadingSamples(false);
        show('Failed to initialize services', { severity: 'error' });
        return;
      }

      if (!apiFactory || !servicesClient) {
        setIsLoadingConfig(false);
        setIsLoadingSamples(false);
        show('Failed to initialize services', { severity: 'error' });
        return;
      }

      // Keep track of the freshest project data for prompt context
      let latestProject: Project | null = project;

      // Fetch project if selected
      if (projectId) {
        try {
          const projectsClient = apiFactory.getProjectsClient();
          const fetchedProject = await projectsClient.getProject(projectId);
          setProject(fetchedProject);
          latestProject = fetchedProject;
        } catch (error) {
          show(`Failed to load project`, { severity: 'warning' });
        }
      } else {
        setProject(null);
        latestProject = null;
      }

      // Helper function to create chips from config response
      const createChipsFromArray = (
        items:
          | Array<{ name: string; description: string; active: boolean }>
          | undefined,
        colorVariant: 'blue' | 'purple' | 'orange' | 'green'
      ): ChipConfig[] => {
        if (!items || !Array.isArray(items)) {
          return [];
        }
        return items.map(item => {
          return {
            id: item.name.toLowerCase().replace(/\s+/g, '-'),
            label: item.name,
            description: item.description,
            active: item.active,
            colorVariant,
          };
        });
      };

      // Step 1: Generate test configuration
      try {
        const configResponse = await servicesClient.generateTestConfig({
          prompt: desc,
          project_id: projectId || undefined,
        });

        const newConfigChips: ConfigChips = {
          behavior: createChipsFromArray(
            configResponse.behaviors || [],
            'blue'
          ),
          topics: createChipsFromArray(configResponse.topics || [], 'green'),
          category: createChipsFromArray(
            configResponse.categories || [],
            'purple'
          ),
        };

        setConfigChips(newConfigChips);
        setIsLoadingConfig(false);

        // Step 2: Generate initial test samples (after config is ready)
        try {
          const activeBehaviors = newConfigChips.behavior
            .filter(c => c.active)
            .map(c => c.label);
          const activeTopics = newConfigChips.topics
            .filter(c => c.active)
            .map(c => c.label);
          const activeCategories = newConfigChips.category
            .filter(c => c.active)
            .map(c => c.label);

          const projectContext = latestProject?.name || 'General';

          const newSamples = await generateSamplesForTestType(
            servicesClient,
            testType,
            activeBehaviors,
            activeTopics,
            activeCategories,
            desc,
            projectContext,
            sources,
            5
          );

          setTestSamples(newSamples);
        } catch (error) {
          show('Failed to generate test samples', { severity: 'error' });
        } finally {
          setIsLoadingSamples(false);
        }
      } catch (error) {
        show('Failed to generate configuration', { severity: 'error' });
        setIsLoadingConfig(false);
        setIsLoadingSamples(false);
      }
    },
    [sessionToken, project, show]
  );

  // Generate test samples
  const generateSamples = useCallback(async () => {
    setIsLoadingSamples(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();

      // Build prompt from configuration
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
        5
      );

      setTestSamples(newSamples);
      show('Samples regenerated successfully', { severity: 'success' });
    } catch (error) {
      show('Failed to regenerate samples', { severity: 'error' });
    } finally {
      setIsLoadingSamples(false);
    }
  }, [
    sessionToken,
    description,
    configChips,
    selectedSources,
    project,
    testType,
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

        // Build prompt from configuration with feedback
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
          const prompt = {
            project_context: project?.name || 'General',
            behaviors: activeBehaviors,
            topics: activeTopics,
            categories: activeCategories,
            specific_requirements: description,
            test_type: 'Single interaction tests',
            output_format: 'Generate only user inputs',
          };

          const ratedSample = {
            prompt: sample.prompt,
            response: sample.response || '',
            rating: sample.rating || 1,
            feedback: feedback,
          };

          const response = await servicesClient.generateTests({
            prompt,
            num_tests: 1,
            sources: selectedSources,
            rated_samples: [ratedSample],
          });

          if (response.tests?.length) {
            const newSample: TestSample = {
              id: `sample-${Date.now()}-regenerated`,
              testType: 'single_turn',
              prompt: response.tests[0].prompt.content,
              response: response.tests[0].prompt.expected_response,
              behavior: response.tests[0].behavior,
              topic: response.tests[0].topic,
              rating: null,
              feedback: '',
              context: response.tests[0].metadata?.sources
                ?.map((source: any) => ({
                  name: source.name || source.source || source.title || '',
                  description: source.description || '',
                  content: source.content || '',
                }))
                .filter((src: any) => src.name && src.name.trim().length > 0),
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
            1
          );

          if (newSamples.length > 0) {
            setTestSamples(prev =>
              prev.map(s => (s.id === sampleId ? newSamples[0] : s))
            );
          }
        }

        show('Sample regenerated successfully', { severity: 'success' });
      } catch (error) {
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
      // 1. Collect all chip states (both selected and deselected) for this message
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
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const servicesClient = apiFactory.getServicesClient();

        // Build complete iteration context

        // 1. Collect all rated samples with feedback
        const ratedSamples = testSamples
          .filter(sample => sample.rating !== null)
          .map(sample => ({
            prompt: sample.prompt,
            response: sample.response || '',
            rating: sample.rating as number,
            feedback:
              sample.feedback && sample.feedback.trim()
                ? sample.feedback
                : undefined,
          }));

        // 2. Collect all previous user messages (not assistant responses) with their chip_states
        const previousMessages = chatMessages
          .filter(msg => msg.type === 'user')
          .map(msg => ({
            content: msg.content,
            timestamp: msg.timestamp.toISOString(),
            chip_states: msg.chip_states,
          }));

        // Step 1: Regenerate test configuration with full iteration context
        const configResponse = await servicesClient.generateTestConfig({
          prompt: description, // Keep original prompt separate
          project_id: selectedProjectId || undefined,
          previous_messages: [
            ...previousMessages,
            {
              content: message,
              timestamp: newMessage.timestamp.toISOString(),
              chip_states: chipStates,
            },
          ],
        });

        // Step 2: Create chips from config response
        const createChipsFromArray = (
          items:
            | Array<{ name: string; description: string; active: boolean }>
            | undefined,
          colorVariant: 'blue' | 'purple' | 'orange' | 'green'
        ): ChipConfig[] => {
          if (!items || !Array.isArray(items)) {
            return [];
          }
          return items.map(item => {
            return {
              id: item.name.toLowerCase().replace(/\s+/g, '-'),
              label: item.name,
              description: item.description,
              active: item.active,
              colorVariant,
            };
          });
        };

        const newConfigChips: ConfigChips = {
          behavior: createChipsFromArray(
            configResponse.behaviors || [],
            'blue'
          ),
          topics: createChipsFromArray(configResponse.topics || [], 'green'),
          category: createChipsFromArray(
            configResponse.categories || [],
            'purple'
          ),
        };

        setConfigChips(newConfigChips);

        // Step 3: Generate new test samples with updated configuration
        const activeBehaviors = newConfigChips.behavior
          .filter(c => c.active)
          .map(c => c.label);
        const activeTopics = newConfigChips.topics
          .filter(c => c.active)
          .map(c => c.label);
        const activeCategories = newConfigChips.category
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
          5
        );

        setTestSamples(newSamples);

        if (newSamples.length > 0) {
          // Add assistant response to chat
          const assistantMessage: ChatMessage = {
            id: `msg-${Date.now()}-assistant`,
            type: 'assistant',
            content:
              'Configuration and samples updated based on your refinement.',
            timestamp: new Date(),
          };
          setChatMessages(prev => [...prev, assistantMessage]);

          show('Test generation refined successfully', { severity: 'success' });
        }
      } catch (error) {
        show('Failed to refine test generation', { severity: 'error' });
      } finally {
        setIsGenerating(false);
      }
    },
    [
      sessionToken,
      description,
      selectedSourceIds,
      project,
      show,
      configChips,
      testSamples,
      chatMessages,
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
        5
      );

      setTestSamples(prev => [...prev, ...newSamples]);
    } catch (error) {
      show('Failed to load more samples', { severity: 'error' });
    } finally {
      setIsLoadingMore(false);
    }
  }, [
    sessionToken,
    description,
    configChips,
    selectedSources,
    project,
    testType,
    show,
  ]);

  // Final generation
  const handleGenerate = useCallback(async () => {
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

      // Map test set size to actual number of tests
      // Small: 25-50 tests, Medium: 75-150 tests, Large: 200+ tests
      const numTests =
        testSetSize === 'small' ? 50 : testSetSize === 'large' ? 200 : 100;

      const generationConfig: TestSetGenerationConfig = {
        project_name: project?.name,
        behaviors: activeBehaviors,
        purposes: activeTopics,
        test_type: testType,
        response_generation: 'prompt_only',
        test_coverage:
          testSetSize === 'small'
            ? 'focused'
            : testSetSize === 'large'
              ? 'comprehensive'
              : 'standard',
        tags: activeTopics,
        description,
      };

      const generationSamples: GenerationSample[] = testSamples.map(sample => ({
        text:
          sample.testType === 'single_turn'
            ? sample.prompt
            : sample.prompt.goal,
        behavior: sample.behavior,
        topic: sample.topic,
        rating: sample.rating,
        feedback: sample.feedback,
      }));

      const request: TestSetGenerationRequest = {
        config: generationConfig,
        samples: generationSamples,
        synthesizer_type: 'prompt',
        batch_size: 20,
        num_tests: numTests,
        sources: selectedSources,
        name: testSetName.trim() || undefined,
      };

      const response = await testSetsClient.generateTestSet(request);

      show(response.message, { severity: 'success' });

      // Clean up sessionStorage
      if (typeof window !== 'undefined') {
        sessionStorage.removeItem('testType');
        sessionStorage.removeItem('selectedTemplateId');
      }

      setTimeout(() => router.push('/tests'), 2000);
    } catch (error) {
      show('Failed to start test generation. Please try again.', {
        severity: 'error',
      });
    } finally {
      setIsFinishing(false);
    }
  }, [
    sessionToken,
    configChips,
    description,
    testSamples,
    testSetSize,
    testSetName,
    selectedSourceIds,
    project,
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
    router.push('/tests');
  }, [router]);

  const handleBackToInput = useCallback(() => {
    // If user came from template selection, go back to landing screen
    if (mode === 'template') {
      router.push('/tests');
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
            onContinue={handleContinueFromInput}
            initialDescription={description}
            selectedSourceIds={selectedSourceIds}
            onSourcesChange={(sources: SourceData[]) => {
              setSelectedSources(sources);
              setSelectedSourceIds(sources.map(s => s.id));
            }}
            selectedProjectId={selectedProjectId}
            onProjectChange={setSelectedProjectId}
            isLoading={isGenerating}
            onBack={handleBackToTests}
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
            testSetSize={testSetSize}
            testSetName={testSetName}
            sources={selectedSources}
            onBack={handleBackToInterface}
            onGenerate={handleGenerate}
            onTestSetSizeChange={setTestSetSize}
            onTestSetNameChange={setTestSetName}
            isGenerating={isFinishing}
          />
        );

      default:
        return null;
    }
  };

  return <>{renderCurrentScreen()}</>;
}
