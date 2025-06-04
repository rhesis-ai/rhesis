'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Button,
  Step,
  StepLabel,
  Stepper,
  Typography,
  Container,
  Grid,
  Autocomplete,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  Chip,
  OutlinedInput,
  FormHelperText,
  Paper,
  Rating,
  Alert,
  AlertTitle,
  LinearProgress,
  CircularProgress,
  Skeleton
} from '@mui/material';
import { LoadingButton } from '@mui/lab';
import BaseTag from '@/components/common/BaseTag';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Project } from '@/utils/api-client/interfaces/project';
import { Behavior } from '@/utils/api-client/interfaces/behavior';
import { useNotifications } from '@/components/common/NotificationContext';
import StarIcon from '@mui/icons-material/Star';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import styles from '@/styles/ReviewSamples.module.css';

// Types
interface Sample {
  id: number;
  text: string;
  behavior: 'Reliability' | 'Compliance';
  topic: string;
  rating: number | null;
  feedback: string;
}

interface ConfigData {
  project: Project | null;
  behaviors: string[];
  purposes: string[];
  testType: string;
  responseGeneration: string;
  testCoverage: string;
  tags: string[];
  description: string;
}

interface GenerateTestsStepperProps {
  sessionToken: string;
}

// Constants
const RATING_LABELS: Record<number, string> = {
  1: 'Poor',
  2: 'Fair', 
  3: 'Good',
  4: 'Very Good',
  5: 'Excellent',
};

const PURPOSES = [
  'Regression Testing',
  'New Feature Testing', 
  'Integration Testing',
  'Edge Case Testing',
  'Performance Testing'
];

const INITIAL_CONFIG: ConfigData = {
  project: null,
  behaviors: [],
  purposes: [],
  testType: "single_turn",
  responseGeneration: "prompt_only", 
  testCoverage: "standard",
  tags: [],
  description: ""
};

// Helper functions
const getLabelText = (value: number) => {
  return `${value} Star${value !== 1 ? 's' : ''}, ${RATING_LABELS[value]}`;
};

const generatePromptFromConfig = (config: ConfigData): string => {
  const parts = [
    `Project Context: ${config.project?.name || 'General'}`,
    `Test Behaviors: ${config.behaviors.join(', ')}`,
    `Test Purposes: ${config.purposes.join(', ')}`,
    `Key Aspects: ${config.tags.join(', ')}`,
    `Specific Requirements: ${config.description}`,
    `Test Type: ${config.testType === 'single_turn' ? 'Single interaction tests' : 'Multi-turn conversation tests'}`,
    `Output Format: ${config.responseGeneration === 'prompt_only' ? 'Generate only user inputs' : 'Generate both user inputs and expected responses'}`
  ];
  return parts.join('\n');
};

// Step 1: Configuration Component
const ConfigureGeneration = ({ sessionToken, onSubmit }: { 
  sessionToken: string; 
  onSubmit: (config: ConfigData) => void;
}) => {
  const [formData, setFormData] = useState(INITIAL_CONFIG);
  const [projects, setProjects] = useState<Project[]>([]);
  const [behaviors, setBehaviors] = useState<Behavior[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const { show } = useNotifications();

  // Load initial data
  useEffect(() => {
    let mounted = true;
    
    const fetchData = async () => {
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const [projectsData, behaviorsData] = await Promise.all([
          apiFactory.getProjectsClient().getProjects(),
          apiFactory.getBehaviorClient().getBehaviors({ sort_by: 'name', sort_order: 'asc' })
        ]);

        if (!mounted) return;

        setProjects(Array.isArray(projectsData) ? projectsData : []);
        setBehaviors(behaviorsData.filter(b => b?.id && b?.name?.trim()) || []);
      } catch (error) {
        if (mounted) {
          console.error('Failed to load data:', error);
          show('Failed to load configuration data', { severity: 'error' });
        }
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    };

    fetchData();
    return () => { mounted = false; };
  }, [sessionToken, show]);

  // Form validation
  const validateForm = useCallback(() => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.project) newErrors.project = 'Project is required';
    if (formData.behaviors.length === 0) newErrors.behaviors = 'At least one behavior must be selected';
    if (formData.purposes.length === 0) newErrors.purposes = 'At least one purpose must be selected';
    // Tags are optional
    if (!formData.description.trim()) newErrors.description = 'Description is required';
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);

  // Form handlers
  const updateField = useCallback((field: keyof ConfigData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  }, [errors]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      onSubmit(formData);
    }
  }, [formData, validateForm, onSubmit]);

  if (isLoading) {
    return (
      <Grid container spacing={3}>
        {[...Array(6)].map((_, i) => (
          <Grid item xs={12} md={6} key={i}>
            <Skeleton variant="rectangular" height={56} sx={{ mb: 3 }} />
          </Grid>
        ))}
      </Grid>
    );
  }

  return (
    <form id="generation-config-form" onSubmit={handleSubmit}>
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Autocomplete
            id="project-select"
            options={projects}
            value={formData.project}
            onChange={(_, value) => updateField('project', value)}
            getOptionLabel={(option) => option.name}
            isOptionEqualToValue={(option, value) => option.id === value.id}
            renderInput={(params) => (
              <TextField
                {...params}
                id="project-input"
                name="project"
                label="Select Project"
                required
                error={!!errors.project}
                helperText={errors.project}
                sx={{ mb: 3 }}
              />
            )}
          />

          <FormControl fullWidth error={!!errors.behaviors} sx={{ mb: 3 }}>
            <InputLabel id="behaviors-label" required>Behaviors</InputLabel>
            <Select
              labelId="behaviors-label"
              id="behaviors-select"
              name="behaviors"
              multiple
              value={formData.behaviors}
              onChange={(e) => updateField('behaviors', e.target.value)}
              input={<OutlinedInput label="Behaviors" />}
              renderValue={(selected) => (
                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                  {selected.map((value) => {
                    const behavior = behaviors.find(b => b.id === value);
                    return <Chip key={value} label={behavior?.name || value} size="small" />;
                  })}
                </Stack>
              )}
            >
              {behaviors.map((behavior) => (
                <MenuItem key={behavior.id} value={behavior.id}>
                  {behavior.name}
                </MenuItem>
              ))}
            </Select>
            <FormHelperText>{errors.behaviors}</FormHelperText>
          </FormControl>

          <FormControl fullWidth error={!!errors.purposes} sx={{ mb: 3 }}>
            <InputLabel id="purposes-label" required>Purpose</InputLabel>
            <Select
              labelId="purposes-label"
              id="purposes-select"
              name="purposes"
              multiple
              value={formData.purposes}
              onChange={(e) => updateField('purposes', e.target.value)}
              input={<OutlinedInput label="Purpose" />}
              renderValue={(selected) => (
                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                  {selected.map((value) => (
                    <Chip key={value} label={value} size="small" />
                  ))}
                </Stack>
              )}
            >
              {PURPOSES.map((purpose) => (
                <MenuItem key={purpose} value={purpose}>
                  {purpose}
                </MenuItem>
              ))}
            </Select>
            <FormHelperText>{errors.purposes}</FormHelperText>
          </FormControl>
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            id="test-type-select"
            name="testType"
            select
            fullWidth
            label="Test Type"
            value={formData.testType}
            onChange={(e) => updateField('testType', e.target.value)}
            sx={{ mb: 3 }}
          >
            <MenuItem value="single_turn">Single Turn</MenuItem>
          </TextField>

          <TextField
            id="response-generation-select"
            name="responseGeneration"
            select
            fullWidth
            label="Response Generation"
            value={formData.responseGeneration}
            onChange={(e) => updateField('responseGeneration', e.target.value)}
            sx={{ mb: 3 }}
          >
            <MenuItem value="prompt_only">Generate Prompts Only</MenuItem>
            <MenuItem value="prompt_and_response">Generate Prompts with Expected Responses</MenuItem>
          </TextField>

          <TextField
            id="test-coverage-select"
            name="testCoverage"
            select
            fullWidth
            label="Test Coverage"
            value={formData.testCoverage}
            onChange={(e) => updateField('testCoverage', e.target.value)}
            sx={{ mb: 3 }}
          >
            <MenuItem value="focused">Focused Coverage (100+ test cases)</MenuItem>
            <MenuItem value="standard">Standard Coverage (1,000+ test cases)</MenuItem>
            <MenuItem value="comprehensive">Comprehensive Coverage (5,000+ test cases)</MenuItem>
          </TextField>
        </Grid>

        <Grid item xs={12}>
          <BaseTag
            id="aspects-tags"
            name="aspects"
            value={formData.tags}
            onChange={(value) => updateField('tags', value)}
            placeholder="Add aspects..."
            label="Aspects to cover"
            error={!!errors.tags}
            helperText={errors.tags}
            sx={{ mb: 3 }}
          />

          <TextField
            id="description-input"
            name="description"
            fullWidth
            multiline
            rows={4}
            label="Describe what you want to test"
            value={formData.description}
            onChange={(e) => updateField('description', e.target.value)}
            required
            error={!!errors.description}
            helperText={errors.description}
          />
        </Grid>
      </Grid>
    </form>
  );
};

// Step 2: Review Samples Component  
const ReviewSamples = ({ 
  samples, 
  onSamplesChange,
  sessionToken, 
  configData,
  isLoading = false
}: {
  samples: Sample[];
  onSamplesChange: (samples: Sample[]) => void;
  sessionToken: string;
  configData: ConfigData;
  isLoading?: boolean;
}) => {
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [regenerating, setRegenerating] = useState<Set<number>>(new Set());
  const { show } = useNotifications();

  const updateSample = useCallback((id: number, updates: Partial<Sample>) => {
    onSamplesChange(samples.map(sample => 
      sample.id === id ? { ...sample, ...updates } : sample
    ));
  }, [samples, onSamplesChange]);

  const handleRatingChange = useCallback((id: number, rating: number | null) => {
    updateSample(id, { rating, feedback: rating && rating >= 4 ? '' : samples.find(s => s.id === id)?.feedback || '' });
  }, [updateSample, samples]);

  const handleFeedbackChange = useCallback((id: number, feedback: string) => {
    updateSample(id, { feedback });
  }, [updateSample]);

  const loadMoreSamples = useCallback(async () => {
    setIsLoadingMore(true);
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      
      // Debug: Check the services client here too
      const servicesClient = apiFactory.getServicesClient();
      console.log('ServicesClient (loadMoreSamples):', servicesClient);
      console.log('generateTests method exists:', typeof servicesClient.generateTests === 'function');
      
      const response = await servicesClient.generateTests({
        prompt: generatePromptFromConfig(configData),
        num_tests: 5
      });

      if (response.tests?.length) {
        const newSamples: Sample[] = response.tests.map((test, index) => ({
          id: Math.max(...samples.map(s => s.id), 0) + index + 1,
          text: test.prompt.content,
          behavior: test.behavior as 'Reliability' | 'Compliance',
          topic: test.topic,
          rating: null,
          feedback: ''
        }));
        
        onSamplesChange([...samples, ...newSamples]);
        show('Additional samples loaded', { severity: 'success' });
      }
    } catch (error) {
      console.error('Error in loadMoreSamples:', error);
      show('Failed to load more samples', { severity: 'error' });
    } finally {
      setIsLoadingMore(false);
    }
  }, [sessionToken, configData, samples, onSamplesChange, show]);

  const regenerateSample = useCallback(async (sampleId: number) => {
    const sample = samples.find(s => s.id === sampleId);
    if (!sample?.feedback || sample.rating === null || sample.rating >= 4) return;

    setRegenerating(prev => new Set(prev).add(sampleId));
    
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      
      // Debug: Check the services client here too
      const servicesClient = apiFactory.getServicesClient();
      console.log('ServicesClient (regenerateSample):', servicesClient);
      console.log('generateTests method exists:', typeof servicesClient.generateTests === 'function');
      
      const prompt = `
        Original Test: "${sample.text}"
        Test Type: ${sample.behavior}
        Topic: ${sample.topic}
        User Rating: ${sample.rating}/5 stars
        Improvement Feedback: "${sample.feedback}"
        
        Please generate a new version of this test that addresses the feedback.`;

      const response = await servicesClient.generateTests({
        prompt,
        num_tests: 1
      });

      if (response.tests?.[0]) {
        const newTest = response.tests[0];
        updateSample(sampleId, {
          text: newTest.prompt.content,
          behavior: newTest.behavior as 'Reliability' | 'Compliance',
          topic: newTest.topic,
          rating: null,
          feedback: ''
        });
        show('Test regenerated successfully', { severity: 'success' });
      }
    } catch (error) {
      console.error('Error in regenerateSample:', error);
      show('Failed to regenerate test', { severity: 'error' });
    } finally {
      setRegenerating(prev => {
        const next = new Set(prev);
        next.delete(sampleId);
        return next;
      });
    }
  }, [samples, sessionToken, updateSample, show]);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 4 }}>
        <CircularProgress sx={{ mb: 2 }} />
        <Typography>Generating test samples...</Typography>
      </Box>
    );
  }

  if (samples.length === 0) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 4 }}>
        <Typography variant="h6" color="text.secondary">No samples generated yet</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Evaluate Samples</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Rate each sample and provide feedback for improvements.
      </Typography>

      <Stack spacing={2}>
        {samples.map((sample) => (
          <Paper 
            key={sample.id} 
            sx={{ 
              p: 2,
              border: sample.rating === null ? '1px solid' : 'none',
              borderColor: 'warning.light',
              bgcolor: sample.rating === null ? 'warning.lighter' : 'inherit'
            }}
          >
            <Box sx={{ display: 'flex', gap: 1, mb: 1.5, pb: 1, borderBottom: 1, borderColor: 'divider' }}>
              <Chip label={sample.behavior} size="small" color={sample.behavior === 'Reliability' ? 'success' : 'warning'} />
              <Chip label={sample.topic} size="small" variant="outlined" />
            </Box>

            <Box sx={{ display: 'flex', gap: 2 }}>
              <Box sx={{ flex: 1 }}>
                <Typography variant="body1" sx={{ fontStyle: 'italic', mb: 1 }}>
                  {sample.text}
                </Typography>
                
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                  <TextField
                    placeholder="What could be improved?"
                    value={sample.feedback}
                    onChange={(e) => handleFeedbackChange(sample.id, e.target.value)}
                    variant="standard"
                    size="small"
                    disabled={sample.rating === null || sample.rating >= 4}
                    sx={{ flex: 1 }}
                  />
                  
                  <LoadingButton
                    loading={regenerating.has(sample.id)}
                    onClick={() => regenerateSample(sample.id)}
                    variant="outlined"
                    size="small"
                    startIcon={<AutorenewIcon />}
                    disabled={!sample.feedback || sample.rating === null || sample.rating >= 4}
                  >
                    Regenerate
                  </LoadingButton>
                </Box>
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative' }}>
                {sample.rating === null && (
                  <Box sx={{
                    position: 'absolute',
                    top: -30,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    bgcolor: 'background.paper',
                    color: 'text.primary',
                    border: 1,
                    borderColor: 'divider',
                    px: 1,
                    py: 0.5,
                    borderRadius: 1,
                    fontSize: '0.75rem',
                    whiteSpace: 'nowrap',
                    zIndex: 1,
                    boxShadow: 1,
                    '&::after': {
                      content: '""',
                      position: 'absolute',
                      top: '100%',
                      left: '50%',
                      transform: 'translateX(-50%)',
                      width: 0,
                      height: 0,
                      borderLeft: '4px solid transparent',
                      borderRight: '4px solid transparent',
                      borderTop: '4px solid',
                      borderTopColor: 'background.paper'
                    }
                  }}>
                    Click to Rate
                  </Box>
                )}
                <Rating
                  value={sample.rating}
                  onChange={(_, value) => handleRatingChange(sample.id, value)}
                  size="large"
                  getLabelText={getLabelText}
                  emptyIcon={<StarIcon style={{ opacity: 0.55 }} fontSize="inherit" />}
                />
                {sample.rating && (
                  <Typography variant="caption" color="text.secondary">
                    {RATING_LABELS[sample.rating]}
                  </Typography>
                )}
              </Box>
            </Box>
          </Paper>
        ))}

        <LoadingButton
          onClick={loadMoreSamples}
          loading={isLoadingMore}
          startIcon={<AutoFixHighIcon />}
          variant="outlined"
          sx={{ alignSelf: 'flex-start' }}
        >
          Load More Samples
        </LoadingButton>
      </Stack>
    </Box>
  );
};

// Step 3: Confirm Generation Component
const ConfirmGenerate = ({ samples, configData }: { samples: Sample[]; configData: ConfigData }) => {
  const ratedSamples = samples.filter(s => s.rating !== null);
  const averageRating = ratedSamples.length > 0 
    ? (ratedSamples.reduce((acc, s) => acc + (s.rating || 0), 0) / ratedSamples.length).toFixed(1)
    : 'N/A';

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Confirm Test Generation</Typography>
      
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>Configuration Summary</Typography>
        <Grid container spacing={2}>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">Project</Typography>
            <Typography variant="body1" gutterBottom>{configData.project?.name || 'Not set'}</Typography>
            <Typography variant="body2" color="text.secondary">Behaviors</Typography>
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              {configData.behaviors.map(behavior => (
                <Chip key={behavior} label={behavior} size="small" />
              ))}
            </Stack>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="body2" color="text.secondary">Average Rating</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Rating value={parseFloat(averageRating) || 0} precision={0.1} readOnly size="small" />
              <Typography variant="body2">({averageRating})</Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      <Alert severity="info">
        <AlertTitle>What happens next?</AlertTitle>
        When you click &quot;Generate Tests&quot;, we&apos;ll create your test suite and notify you when ready.
      </Alert>
    </Box>
  );
};

// Main Stepper Component
export default function GenerateTestsStepper({ sessionToken }: GenerateTestsStepperProps) {
  const [activeStep, setActiveStep] = useState(0);
  const [configData, setConfigData] = useState(INITIAL_CONFIG);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const router = useRouter();
  const { show } = useNotifications();

  const steps = ['Configure Generation', 'Review Samples', 'Confirm & Generate'];

  const handleConfigSubmit = useCallback(async (config: ConfigData) => {
    setConfigData(config);
    setActiveStep(1);
    setIsGenerating(true);
    
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      
      // Debug: Check what the apiFactory looks like
      console.log('ApiClientFactory instance:', apiFactory);
      
      const servicesClient = apiFactory.getServicesClient();
      
      // Debug: Check what the services client looks like
      console.log('ServicesClient instance:', servicesClient);
      console.log('ServicesClient methods:', Object.getOwnPropertyNames(Object.getPrototypeOf(servicesClient)));
      console.log('generateTests method:', servicesClient.generateTests);
      
      const generatedPrompt = generatePromptFromConfig(config);
      
      const requestPayload = {
        prompt: generatedPrompt,
        num_tests: 5
      };
      
      const response = await servicesClient.generateTests(requestPayload);

      if (response.tests?.length) {
        const newSamples: Sample[] = response.tests.map((test, index) => ({
          id: index + 1,
          text: test.prompt.content,
          behavior: test.behavior as 'Reliability' | 'Compliance',
          topic: test.topic,
          rating: null,
          feedback: ''
        }));
        
        setSamples(newSamples);
        show('Samples generated successfully', { severity: 'success' });
      } else {
        throw new Error('No tests generated in response');
      }
    } catch (error) {
      console.error('Error in handleConfigSubmit:', error);
      show('Failed to generate samples', { severity: 'error' });
      setActiveStep(0);
    } finally {
      setIsGenerating(false);
    }
  }, [sessionToken, show]);

  const handleNext = useCallback(() => {
    if (activeStep === 1) {
      const hasUnratedSamples = samples.some(s => s.rating === null);
      if (hasUnratedSamples) {
        show('Please rate all samples before proceeding', { severity: 'error' });
        return;
      }
    }
    setActiveStep(prev => prev + 1);
  }, [activeStep, samples, show]);

  const handleBack = useCallback(() => {
    setActiveStep(prev => prev - 1);
  }, []);

  const handleFinish = useCallback(() => {
    show('Test generation started. You will be notified when complete.', { severity: 'success' });
    setTimeout(() => router.push('/tests'), 1000);
  }, [router, show]);

  const renderStepContent = useMemo(() => {
    switch (activeStep) {
      case 0:
        return <ConfigureGeneration sessionToken={sessionToken} onSubmit={handleConfigSubmit} />;
      case 1:
        return (
          <ReviewSamples 
            samples={samples}
            onSamplesChange={setSamples}
            sessionToken={sessionToken}
            configData={configData}
            isLoading={isGenerating}
          />
        );
      case 2:
        return <ConfirmGenerate samples={samples} configData={configData} />;
      default:
        return null;
    }
  }, [activeStep, sessionToken, handleConfigSubmit, samples, configData, isGenerating]);

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Box sx={{ minHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <Stepper activeStep={activeStep} sx={{ py: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        <Box sx={{ flex: 1, mt: 4 }}>
          {renderStepContent}
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, mt: 4 }}>
          {activeStep > 0 && (
            <Button 
              variant="outlined" 
              onClick={handleBack}
              disabled={isGenerating}
            >
              Back
            </Button>
          )}
          
          {activeStep === steps.length - 1 ? (
            <Button variant="contained" onClick={handleFinish}>
              Generate Tests
            </Button>
          ) : activeStep === 0 ? (
            <LoadingButton
              variant="contained"
              loading={isGenerating}
              disabled={isGenerating}
              form="generation-config-form"
              type="submit"
            >
              Generate Samples
            </LoadingButton>
          ) : (
            <Button 
              variant="contained" 
              onClick={handleNext}
              disabled={isGenerating}
            >
              Next
            </Button>
          )}
        </Box>
      </Box>
    </Container>
  );
} 