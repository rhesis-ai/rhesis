'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Grid,
  Typography,
  Paper,
  Chip,
  Button,
  IconButton,
  TextField,
  InputAdornment,
  Rating,
  CircularProgress,
  Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import SendIcon from '@mui/icons-material/Send';
import RefreshIcon from '@mui/icons-material/Refresh';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ProcessedDocument } from '@/utils/api-client/interfaces/documents';

interface TestConfigurationProps {
  sessionToken: string;
}

interface TestSample {
  id: string;
  text: string;
  behavior: string;
  topic: string;
  rating: number | null;
  feedback: string;
}

interface Configuration {
  behaviors: string[];
  topics: string[];
  categories: string[];
  scenarios: string[];
}

const availableBehaviors = [
  'Reliability', 'Compliance', 'Robustness', 'Behavior A', 'Behavior B', 'Behavior C'
];

const availableTopics = [
  'Fraud', 'Claim Processing', 'Topic A', 'Topic B', 'Topic C', 'Topic D'
];

const availableCategories = [
  'Harmful', 'Harmless', 'Prompt Injections', 'Category A', 'Category B', 'Category C'
];

const availableScenarios = [
  'Edge Cases', 'User Journey', 'Error Handling', 'Performance Stress', 'Integration', 'Accessibility'
];

export default function TestConfiguration({
  sessionToken,
}: TestConfigurationProps) {
  const router = useRouter();
  const { show } = useNotifications();

  const [description, setDescription] = useState('');
  const [documents, setDocuments] = useState<ProcessedDocument[]>([]);
  const [configuration, setConfiguration] = useState<Configuration>({
    behaviors: ['Reliability', 'Compliance', 'Robustness'],
    topics: ['Fraud', 'Claim Processing'],
    categories: ['Harmful', 'Harmless', 'Prompt Injections'],
    scenarios: ['Edge Cases', 'User Journey', 'Error Handling'],
  });
  const [samples, setSamples] = useState<TestSample[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [refinementText, setRefinementText] = useState('');

  useEffect(() => {
    // Load data from session storage
    const savedDescription = sessionStorage.getItem('testGenerationDescription');
    const savedDocuments = sessionStorage.getItem('testGenerationDocuments');
    const savedConfig = sessionStorage.getItem('testGenerationConfig');

    if (savedDescription) {
      setDescription(savedDescription);
    }

    if (savedConfig) {
      try {
        const config = JSON.parse(savedConfig);
        setConfiguration({
          behaviors: config.behaviors,
          topics: config.topics,
          categories: config.categories,
          scenarios: config.scenarios,
        });
        // Generate initial samples with the loaded configuration
        generateInitialSamples(savedDescription, config);
      } catch (error) {
        console.error('Failed to parse saved configuration:', error);
      }
    }

    if (savedDocuments) {
      try {
        setDocuments(JSON.parse(savedDocuments));
      } catch (error) {
        console.error('Failed to parse saved documents:', error);
      }
    }
  }, []);

  const generateInitialSamples = async (desc: string, config: any) => {
    if (!desc.trim()) return;

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();

      const request = {
        prompt: {
          project_context: desc,
          test_behaviors: config.behaviors,
          test_purposes: config.topics,
          key_topics: config.categories,
          specific_requirements: config.scenarios.join(', '),
          test_type: 'config',
          output_format: 'json',
        },
        num_tests: 5,
        documents: documents.map(doc => ({
          name: doc.name,
          description: doc.description || '',
          path: doc.path,
          content: doc.content || '',
        })),
      };

      const response = await servicesClient.generateTests(request);

      // Convert response to samples format
      const newSamples: TestSample[] = response.tests.map((test: any, index: number) => ({
        id: `initial-${index}`,
        text: test.prompt?.content || test.text || '',
        behavior: test.behavior || 'Reliability',
        topic: test.topic || 'General',
        rating: null,
        feedback: '',
      }));

      setSamples(newSamples);
    } catch (error) {
      console.error('Failed to generate initial samples:', error);
    }
  };

  const handleBack = () => {
    router.push('/tests/generate/describe');
  };

  const handleToggleSelection = (category: keyof Configuration, item: string) => {
    setConfiguration(prev => {
      const newConfig = {
        ...prev,
        [category]: prev[category].includes(item)
          ? prev[category].filter(i => i !== item)
          : [...prev[category], item]
      };

      // Regenerate samples when configuration changes
      regenerateSamples(newConfig);

      return newConfig;
    });
  };

  const regenerateSamples = async (config: Configuration) => {
    if (!description.trim()) return;

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();

      const request = {
        prompt: {
          project_context: description,
          test_behaviors: config.behaviors,
          test_purposes: config.topics,
          key_topics: config.categories,
          specific_requirements: config.scenarios.join(', '),
          test_type: 'config',
          output_format: 'json',
        },
        num_tests: 5,
        documents: documents.map(doc => ({
          name: doc.name,
          description: doc.description || '',
          path: doc.path,
          content: doc.content || '',
        })),
      };

      const response = await servicesClient.generateTests(request);

      // Convert response to samples format
      const newSamples: TestSample[] = response.tests.map((test: any, index: number) => ({
        id: `reactive-${Date.now()}-${index}`,
        text: test.prompt?.content || test.text || '',
        behavior: test.behavior || 'Reliability',
        topic: test.topic || 'General',
        rating: null,
        feedback: '',
      }));

      setSamples(newSamples);
    } catch (error) {
      console.error('Failed to regenerate samples:', error);
    }
  };

  const handleGenerateSamples = async () => {
    if (!description.trim()) {
      show('Please provide a description first', { severity: 'error' });
      return;
    }

    setIsGenerating(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();

      const request = {
        prompt: {
          project_context: description,
          test_behaviors: configuration.behaviors,
          test_purposes: configuration.topics,
          key_topics: configuration.categories,
          specific_requirements: configuration.scenarios.join(', '),
          test_type: 'config',
          output_format: 'json',
        },
        num_tests: 3,
        documents: documents.map(doc => ({
          name: doc.name,
          description: doc.description || '',
          path: doc.path,
          content: doc.content || '',
        })),
      };

      const response = await servicesClient.generateTests(request);

      // Convert response to samples format
      const newSamples: TestSample[] = response.tests.map((test: any, index: number) => ({
        id: `sample-${index}`,
        text: test.prompt?.content || test.text || '',
        behavior: test.behavior || 'Reliability',
        topic: test.topic || 'General',
        rating: null,
        feedback: '',
      }));

      setSamples(newSamples);
      show('Test samples generated successfully', { severity: 'success' });
    } catch (error) {
      console.error('Failed to generate samples:', error);
      show('Failed to generate test samples', { severity: 'error' });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSampleRating = (sampleId: string, rating: number) => {
    if (rating === 0) {
      // Remove disliked samples
      setSamples(prev => prev.filter(sample => sample.id !== sampleId));
    } else {
      // Update liked samples
      setSamples(prev => prev.map(sample =>
        sample.id === sampleId ? { ...sample, rating } : sample
      ));
    }
  };

  const handleSampleFeedback = (sampleId: string, feedback: string) => {
    setSamples(prev => prev.map(sample =>
      sample.id === sampleId ? { ...sample, feedback } : sample
    ));
  };

  const handleRefinementSubmit = async () => {
    if (!refinementText.trim()) return;

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();

      const request = {
        prompt: {
          project_context: `${description}\n\nAdditional refinement: ${refinementText}`,
          test_behaviors: configuration.behaviors,
          test_purposes: configuration.topics,
          key_topics: configuration.categories,
          specific_requirements: configuration.scenarios.join(', '),
          test_type: 'config',
          output_format: 'json',
        },
        num_tests: 2,
        documents: documents.map(doc => ({
          name: doc.name,
          description: doc.description || '',
          path: doc.path,
          content: doc.content || '',
        })),
      };

      const response = await servicesClient.generateTests(request);

      const newSamples: TestSample[] = response.tests.map((test: any, index: number) => ({
        id: `refined-${Date.now()}-${index}`,
        text: test.prompt?.content || test.text || '',
        behavior: test.behavior || 'Reliability',
        topic: test.topic || 'General',
        rating: null,
        feedback: '',
      }));

      setSamples(prev => [...prev, ...newSamples]);
      setRefinementText('');
      show('Refined test samples generated', { severity: 'success' });
    } catch (error) {
      console.error('Failed to refine samples:', error);
      show('Failed to refine test samples', { severity: 'error' });
    }
  };

  const handleContinue = () => {
    // Store configuration and samples for final step
    sessionStorage.setItem('testGenerationConfiguration', JSON.stringify(configuration));
    sessionStorage.setItem('testGenerationSamples', JSON.stringify(samples));
    router.push('/tests/generate/confirm');
  };

  const renderConfigurationSection = (
    title: string,
    items: string[],
    selectedItems: string[],
    color: string,
    onToggle: (item: string) => void
  ) => (
    <Box sx={{ mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        {title}
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {items.map((item) => (
          <Chip
            key={item}
            label={item}
            onClick={() => onToggle(item)}
            variant={selectedItems.includes(item) ? 'filled' : 'outlined'}
            sx={(theme) => ({
              backgroundColor: selectedItems.includes(item) ? `${theme.palette[color].main}20` : 'transparent',
              borderColor: theme.palette[color].main,
              color: selectedItems.includes(item) ? theme.palette[color].main : 'text.primary',
              '&:hover': {
                backgroundColor: `${theme.palette[color].main}10`,
              },
            })}
          />
        ))}
      </Box>
    </Box>
  );

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <IconButton onClick={handleBack} sx={{ mr: 1 }}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6">Configure Test Generation</Typography>
        </Box>
      </Box>

      <Grid container sx={{ flex: 1, overflow: 'hidden' }}>
        {/* Left Sidebar - Configuration */}
        <Grid item xs={12} md={4} sx={{ borderRight: 1, borderColor: 'divider' }}>
          <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
            <Typography variant="h5" gutterBottom>
              Tests Configuration
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Configure test parameters and upload documents to guide AI generation.
            </Typography>

            {renderConfigurationSection(
              'Behavior Testing',
              configuration.behaviors.length > 0 ? [...new Set([...configuration.behaviors, ...availableBehaviors])] : availableBehaviors,
              configuration.behaviors,
              'primary.main',
              (item) => handleToggleSelection('behaviors', item)
            )}

            {renderConfigurationSection(
              'Topics',
              configuration.topics.length > 0 ? [...new Set([...configuration.topics, ...availableTopics])] : availableTopics,
              configuration.topics,
              'secondary.main',
              (item) => handleToggleSelection('topics', item)
            )}

            {renderConfigurationSection(
              'Test Categories',
              configuration.categories.length > 0 ? [...new Set([...configuration.categories, ...availableCategories])] : availableCategories,
              configuration.categories,
              'warning.main',
              (item) => handleToggleSelection('categories', item)
            )}

            {renderConfigurationSection(
              'Test Scenarios',
              configuration.scenarios.length > 0 ? [...new Set([...configuration.scenarios, ...availableScenarios])] : availableScenarios,
              configuration.scenarios,
              'success.main',
              (item) => handleToggleSelection('scenarios', item)
            )}

            {/* Uploaded Files */}
            {documents.length > 0 && (
              <Box sx={{ mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Uploaded Files
                </Typography>
                {documents.map((doc) => (
                  <Box
                    key={doc.id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      p: 1,
                      border: 1,
                      borderColor: 'grey.200',
                      sx: (theme) => ({ borderRadius: theme.shape.borderRadius }),
                      mb: 1,
                    }}
                  >
                    <Typography variant="body2">{doc.name}</Typography>
                    <IconButton size="small">×</IconButton>
                  </Box>
                ))}
              </Box>
            )}

            {/* Refinement Input */}
            <Box sx={{ mb: 3 }}>
              <TextField
                fullWidth
                multiline
                rows={3}
                value={refinementText}
                onChange={(e) => setRefinementText(e.target.value)}
                placeholder="Further refine your test generation instructions..."
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={handleRefinementSubmit}
                        disabled={!refinementText.trim()}
                      >
                        <SendIcon />
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
            </Box>

            <Button
              variant="outlined"
              onClick={handleBack}
              sx={{ width: '100%' }}
            >
              ← Back
            </Button>
          </Box>
        </Grid>

        {/* Right Content - Test Samples */}
        <Grid item xs={12} md={8}>
          <Box sx={{ p: 3, height: 'calc(100vh - 120px)', overflow: 'auto' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Box>
                <Typography variant="h5" gutterBottom>
                  Review Test Cases
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Preview of generated test samples. Rate them to improve future generations.
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  • {samples.length} samples
                </Typography>
                <Button
                  variant="contained"
                  startIcon={<RefreshIcon />}
                  onClick={handleGenerateSamples}
                  disabled={isGenerating || !description.trim()}
                >
                  {isGenerating ? 'Generating...' : 'Generate Samples'}
                </Button>
              </Box>
            </Box>

            {isGenerating && (
              <Box sx={{ mb: 3 }}>
                <CircularProgress size={24} sx={{ mr: 2 }} />
                <Typography variant="body2" color="text.secondary">
                  Generating test samples...
                </Typography>
              </Box>
            )}

            {samples.length === 0 && !isGenerating && (
              <Alert severity="info" sx={{ mb: 3 }}>
                Click "Generate Samples" to create test cases based on your configuration.
              </Alert>
            )}

            {/* Test Samples */}
            {samples.map((sample) => (
              <Paper key={sample.id} sx={{ p: 3, mb: 3 }}>
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body1" sx={{ mb: 1 }}>
                    <strong>Test Prompt:</strong>
                  </Typography>
                  <Box
                    sx={{
                      p: 2,
                      bgcolor: 'primary.50',
                      sx: (theme) => ({ borderRadius: theme.shape.borderRadius }),
                      border: '1px solid',
                      borderColor: 'primary.200',
                    }}
                  >
                    <Typography variant="body1">{sample.text}</Typography>
                  </Box>
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="body1" sx={{ mb: 1 }}>
                    <strong>Expected Response:</strong>
                  </Typography>
                  <Box
                    sx={{
                      p: 2,
                      bgcolor: 'grey.50',
                      sx: (theme) => ({ borderRadius: theme.shape.borderRadius }),
                      border: '1px solid',
                      borderColor: 'grey.200',
                    }}
                  >
                    <Typography variant="body2" color="text.secondary">
                      This is a sample expected response that would be generated based on the test prompt.
                    </Typography>
                  </Box>
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                  <Typography variant="body2">Rate this test:</Typography>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <IconButton
                      size="small"
                      onClick={() => handleSampleRating(sample.id, 1)}
                      color={sample.rating === 1 ? 'primary' : 'default'}
                    >
                      <ThumbUpIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleSampleRating(sample.id, 0)}
                      color={sample.rating === 0 ? 'error' : 'default'}
                    >
                      <ThumbDownIcon />
                    </IconButton>
                  </Box>
                </Box>

                <TextField
                  fullWidth
                  multiline
                  rows={2}
                  value={sample.feedback}
                  onChange={(e) => handleSampleFeedback(sample.id, e.target.value)}
                  placeholder="Provide feedback to improve this test..."
                  size="small"
                />
              </Paper>
            ))}

            {samples.length > 0 && (
              <Box sx={{ textAlign: 'center', mt: 4 }}>
                <Button
                  variant="contained"
                  size="large"
                  onClick={handleContinue}
                  sx={{ px: 4, py: 1.5 }}
                >
                  Continue to Confirmation
                </Button>
              </Box>
            )}
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
