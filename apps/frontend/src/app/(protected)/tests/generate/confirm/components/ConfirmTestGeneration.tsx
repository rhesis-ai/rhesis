'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  TextField,
  Button,
  Chip,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormLabel,
  Paper,
  Divider,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DescriptionIcon from '@mui/icons-material/Description';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TestSetGenerationRequest,
  TestSetGenerationConfig,
  GenerationSample,
} from '@/utils/api-client/interfaces/test-set';
import { Document as DocumentInterface } from '@/utils/api-client/interfaces/documents';

interface ConfirmTestGenerationProps {
  sessionToken: string;
  onGenerateComplete?: () => void;
  onBack?: () => void;
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

export default function ConfirmTestGeneration({
  sessionToken,
  onGenerateComplete,
  onBack,
}: ConfirmTestGenerationProps) {
  const router = useRouter();
  const { show } = useNotifications();

  const [description, setDescription] = useState('');
  const [configuration, setConfiguration] = useState<Configuration>({
    behaviors: [],
    topics: [],
    categories: [],
    scenarios: [],
  });
  const [samples, setSamples] = useState<TestSample[]>([]);
  const [testSetName, setTestSetName] = useState('');
  const [testSetSize, setTestSetSize] = useState('medium');
  const [isGenerating, setIsGenerating] = useState(false);
  const [documents, setDocuments] = useState<DocumentInterface[]>([]);

  useEffect(() => {
    // Load data from session storage
    const savedDescription = sessionStorage.getItem(
      'testGenerationDescription'
    );
    const savedConfiguration = sessionStorage.getItem('testGenerationConfig');
    const savedSamples = sessionStorage.getItem('testGenerationSamples');
    const savedDocuments = sessionStorage.getItem('testGenerationDocuments');

    if (savedDescription) {
      setDescription(savedDescription);
    }

    if (savedConfiguration) {
      try {
        const config = JSON.parse(savedConfiguration);
        setConfiguration(config);
      } catch (error) {
        console.error('Failed to parse saved configuration:', error);
      }
    }

    if (savedSamples) {
      try {
        setSamples(JSON.parse(savedSamples));
      } catch (error) {
        console.error('Failed to parse saved samples:', error);
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

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      router.push('/tests/generate/configure');
    }
  };

  const handleGenerate = async () => {
    if (!testSetName.trim()) {
      show('Please enter a test set name', { severity: 'error' });
      return;
    }

    if (samples.length === 0) {
      show(
        'No test samples available. Please go back and generate some samples.',
        { severity: 'error' }
      );
      return;
    }

    // Debug logging for troubleshooting
    console.log('Starting test generation with:', {
      testSetName,
      samplesCount: samples.length,
      configuration,
      description,
      documents: documents.length,
    });

    setIsGenerating(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = apiFactory.getTestSetsClient();

      // Convert UI data to API format
      const generationConfig: TestSetGenerationConfig = {
        project_name: testSetName,
        behaviors: configuration.behaviors,
        purposes: configuration.topics, // Map topics to purposes
        test_type: 'single_turn',
        response_generation: 'prompt_only',
        test_coverage: testSetSize || 'standard',
        description: description,
      };

      const generationSamples: GenerationSample[] = samples.map(sample => ({
        text: sample.text,
        behavior: sample.behavior,
        topic: sample.topic,
        rating: sample.rating || 1, // Default to liked (1) for remaining samples
        feedback: sample.feedback || '',
      }));

      const request: TestSetGenerationRequest = {
        config: generationConfig,
        samples: generationSamples,
        synthesizer_type: 'prompt',
        batch_size: 20,
        ...(documents.length > 0 && {
          documents: documents.map(doc => ({
            name: doc.name,
            description: doc.description || '',
            path: doc.path,
            content: doc.content || '',
          })),
        }),
      };

      console.log('Test generation request:', {
        config: generationConfig,
        samplesCount: generationSamples.length,
        documentsCount: documents.length,
      });
      const response = await testSetsClient.generateTestSet(request);
      console.log('Backend response:', response);

      show(response.message, { severity: 'success' });

      // Clear session storage
      sessionStorage.removeItem('testGenerationDescription');
      sessionStorage.removeItem('testGenerationConfig');
      sessionStorage.removeItem('testGenerationSamples');
      sessionStorage.removeItem('testGenerationDocuments');

      // Call completion callback or redirect
      if (onGenerateComplete) {
        setTimeout(onGenerateComplete, 2000);
      } else {
        setTimeout(() => router.push('/tests'), 2000);
      }
    } catch (error) {
      console.error('Failed to start test generation:', error);
      show('Failed to start test generation. Please try again.', {
        severity: 'error',
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const getTestCountEstimate = (size: string) => {
    switch (size) {
      case 'small':
        return '25-50 tests';
      case 'medium':
        return '75-150 tests';
      case 'large':
        return '200+ tests';
      default:
        return '75-150 tests';
    }
  };

  const totalConfigurations =
    configuration.behaviors.length +
    configuration.topics.length +
    configuration.categories.length +
    configuration.scenarios.length;

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <IconButton onClick={handleBack} sx={{ mb: 2 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h4" component="h1" gutterBottom fontWeight="bold">
          Confirm Test Generation
        </Typography>
        <Typography variant="h6" color="text.secondary">
          Review your configuration and select the test set size to proceed with
          generation.
        </Typography>
      </Box>

      <Grid container spacing={4}>
        {/* Save as Test Set */}
        <Grid item xs={12}>
          <Card sx={{ mb: 4 }}>
            <CardContent sx={{ p: 4 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <Box
                  sx={{
                    width: 48,
                    height: 48,
                    sx: theme => ({ borderRadius: theme.shape.borderRadius }),
                    bgcolor: 'primary.main',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mr: 2,
                  }}
                >
                  <DescriptionIcon
                    sx={{ fontSize: 24, color: 'primary.contrastText' }}
                  />
                </Box>
                <Box>
                  <Typography variant="h5" component="h2" fontWeight="bold">
                    Save as Test Set
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Create a reusable test set from your configuration.
                  </Typography>
                </Box>
              </Box>

              <TextField
                fullWidth
                label="Test Set Name"
                value={testSetName}
                onChange={e => setTestSetName(e.target.value)}
                placeholder="e.g., Insurance AI Compliance Suite"
                sx={{ maxWidth: 400 }}
                InputProps={{
                  sx: {
                    '&::placeholder': {
                      color: 'text.secondary',
                      opacity: 1,
                    },
                  },
                }}
                helperText="Enter a name for your test set to enable generation"
                required
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Configuration Summary */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 4 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <Box
                  sx={{
                    width: 48,
                    height: 48,
                    sx: theme => ({ borderRadius: theme.shape.borderRadius }),
                    bgcolor: 'success.main',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mr: 2,
                  }}
                >
                  <CheckCircleIcon
                    sx={{ fontSize: 24, color: 'success.contrastText' }}
                  />
                </Box>
                <Box>
                  <Typography variant="h5" component="h2" fontWeight="bold">
                    Configuration Summary
                  </Typography>
                </Box>
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="subtitle1"
                  fontWeight="medium"
                  gutterBottom
                >
                  Behavior:
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                  {configuration.behaviors.map(behavior => (
                    <Chip
                      key={behavior}
                      label={behavior}
                      size="small"
                      color="primary"
                    />
                  ))}
                </Box>
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="subtitle1"
                  fontWeight="medium"
                  gutterBottom
                >
                  Topics:
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                  {configuration.topics.map(topic => (
                    <Chip
                      key={topic}
                      label={topic}
                      size="small"
                      color="secondary"
                    />
                  ))}
                </Box>
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="subtitle1"
                  fontWeight="medium"
                  gutterBottom
                >
                  Category:
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                  {configuration.categories.map(category => (
                    <Chip
                      key={category}
                      label={category}
                      size="small"
                      color="warning"
                    />
                  ))}
                </Box>
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="subtitle1"
                  fontWeight="medium"
                  gutterBottom
                >
                  Scenarios:
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                  {configuration.scenarios.map(scenario => (
                    <Chip
                      key={scenario}
                      label={scenario}
                      size="small"
                      color="success"
                    />
                  ))}
                </Box>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Typography variant="body2" color="text.secondary">
                Total active configurations: {totalConfigurations}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Test Set Size */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 4 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <Box
                  sx={{
                    width: 48,
                    height: 48,
                    sx: theme => ({ borderRadius: theme.shape.borderRadius }),
                    bgcolor: 'info.main',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mr: 2,
                  }}
                >
                  <RefreshIcon
                    sx={{ fontSize: 24, color: 'info.contrastText' }}
                  />
                </Box>
                <Box>
                  <Typography variant="h5" component="h2" fontWeight="bold">
                    Test Set Size
                  </Typography>
                </Box>
              </Box>

              <FormControl component="fieldset">
                <FormLabel component="legend">Test Set Size</FormLabel>
                <RadioGroup
                  value={testSetSize}
                  onChange={e => setTestSetSize(e.target.value)}
                >
                  <FormControlLabel
                    value="small"
                    control={<Radio />}
                    label={
                      <Box>
                        <Typography variant="body1" fontWeight="medium">
                          Small Fast
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {getTestCountEstimate('small')}
                        </Typography>
                      </Box>
                    }
                  />
                  <FormControlLabel
                    value="medium"
                    control={<Radio />}
                    label={
                      <Box>
                        <Typography variant="body1" fontWeight="medium">
                          Medium Balanced
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {getTestCountEstimate('medium')}
                        </Typography>
                      </Box>
                    }
                  />
                  <FormControlLabel
                    value="large"
                    control={<Radio />}
                    label={
                      <Box>
                        <Typography variant="body1" fontWeight="medium">
                          Large Comprehensive
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {getTestCountEstimate('large')}
                        </Typography>
                      </Box>
                    }
                  />
                </RadioGroup>
              </FormControl>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Action Buttons */}
      <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2, mt: 4 }}>
        <Button variant="outlined" onClick={handleBack} disabled={isGenerating}>
          Back
        </Button>
        <Button
          variant="contained"
          size="large"
          startIcon={<RefreshIcon />}
          onClick={handleGenerate}
          disabled={isGenerating || !testSetName.trim()}
          sx={{ px: 4, py: 1.5 }}
          title={
            !testSetName.trim() ? 'Please enter a test set name' : undefined
          }
        >
          {isGenerating ? 'Generating...' : 'Generate Tests'}
        </Button>
      </Box>
    </Container>
  );
}
