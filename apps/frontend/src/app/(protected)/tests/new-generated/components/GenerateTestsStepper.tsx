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
import { 
  TestSetGenerationRequest, 
  TestSetGenerationConfig, 
  GenerationSample 
} from '@/utils/api-client/interfaces/test-set';
import { ProcessedDocument } from '@/utils/api-client/interfaces/documents';
import StarIcon from '@mui/icons-material/Star';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DeleteIcon from '@mui/icons-material/Delete';
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
  testCoverage: "focused",
  tags: [],
  description: ""
};

// Add a constant for supported file types
const SUPPORTED_FILE_EXTENSIONS = [
  // Office formats
  '.docx', '.pptx', '.xlsx',
  
  // Documents
  '.pdf', '.txt', '.csv', '.json', '.xml', '.html', '.htm',
  
  // Archives (iterate over contents)
  '.zip',
  
  // E-books
  '.epub'
];

// Create a helper function to check file type
const isFileTypeSupported = (filename: string): boolean => {
  const extension = filename.toLowerCase().slice(filename.lastIndexOf('.'));
  return SUPPORTED_FILE_EXTENSIONS.includes(extension);
};

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB in bytes

// Helper functions
const getLabelText = (value: number) => {
  return `${value} Star${value !== 1 ? 's' : ''}, ${RATING_LABELS[value]}`;
};

const generatePromptFromConfig = (config: ConfigData): string => {
  const parts = [
    `Project Context: ${config.project?.name || 'General'}`,
    `Test Behaviors: ${config.behaviors.join(', ')}`,
    `Test Purposes: ${config.purposes.join(', ')}`,
    `Key Topics: ${config.tags.join(', ')}`,
    `Specific Requirements: ${config.description}`,
    `Test Type: ${config.testType === 'single_turn' ? 'Single interaction tests' : 'Multi-turn conversation tests'}`,
    `Output Format: ${config.responseGeneration === 'prompt_only' ? 'Generate only user inputs' : 'Generate both user inputs and expected responses'}`
  ];
  return parts.join('\n');
};

// Step 1: Configuration Component
const ConfigureGeneration = ({ sessionToken, onSubmit, configData, onConfigChange }: { 
  sessionToken: string; 
  onSubmit: (config: ConfigData) => void;
  configData: ConfigData;
  onConfigChange: (config: ConfigData) => void;
}) => {
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
          console.error('Failed to load configuration data:', error);
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
    
    if (!configData.project) newErrors.project = 'Project is required';
    if (configData.behaviors.length === 0) newErrors.behaviors = 'At least one behavior must be selected';
    if (configData.purposes.length === 0) newErrors.purposes = 'At least one purpose must be selected';
    // Tags are optional
    if (!configData.description.trim()) newErrors.description = 'Description is required';
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [configData]);

  // Form handlers
  const updateField = useCallback((field: keyof ConfigData, value: any) => {
    onConfigChange({ ...configData, [field]: value });
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  }, [configData, onConfigChange, errors]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      onSubmit(configData);
    }
  }, [configData, validateForm, onSubmit]);

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
            value={configData.project}
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
              value={configData.behaviors}
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
              value={configData.purposes}
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
            value={configData.testType}
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
            value={configData.responseGeneration}
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
            value={configData.testCoverage}
            onChange={(e) => updateField('testCoverage', e.target.value)}
            sx={{ mb: 3 }}
          >
            <MenuItem value="focused">Focused Coverage (100 test cases)</MenuItem>
            <MenuItem value="standard">Standard Coverage (1,000 test cases)</MenuItem>
            <MenuItem value="comprehensive">Comprehensive Coverage (5,000 test cases)</MenuItem>
          </TextField>
        </Grid>

        <Grid item xs={12}>
          <BaseTag
            id="topics-tags"
            name="topics"
            value={configData.tags}
            onChange={(value) => updateField('tags', value)}
            placeholder="Add topics..."
            label="Topics to cover"
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
            value={configData.description}
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

// Step 2: Upload Documents Component
const UploadDocuments = ({ 
  sessionToken, 
  documents, 
  onDocumentsChange
}: {
  sessionToken: string;
  documents: ProcessedDocument[];
  onDocumentsChange: (documents: ProcessedDocument[] | ((prev: ProcessedDocument[]) => ProcessedDocument[])) => void;
}) => {
  const { show } = useNotifications();

  const processDocument = useCallback(async (file: File) => {
    const documentId = Math.random().toString(36).substr(2, 9);
    
    // Create initial document entry
    const initialDoc: ProcessedDocument = {
      id: documentId,
      name: '',
      description: '',
      path: '',
      content: '',
      originalName: file.name,
      status: 'uploading'
    };
  
    onDocumentsChange((prevDocs: ProcessedDocument[]) => [...prevDocs, initialDoc]);
  
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();
  
      // Step 1: Upload document
      const uploadResponse = await servicesClient.uploadDocument(file);
      
      // Update status to extracting
      onDocumentsChange((prevDocs: ProcessedDocument[]) => prevDocs.map((doc: ProcessedDocument) => 
        doc.id === documentId ? { ...doc, path: uploadResponse.path, status: 'extracting' as const } : doc
      ));
  
      // Step 2: Extract content using the document extractor
      const extractResponse = await servicesClient.extractDocument(uploadResponse.path);
  
      // Update status to generating metadata
      onDocumentsChange((prevDocs: ProcessedDocument[]) => prevDocs.map((doc: ProcessedDocument) => 
        doc.id === documentId ? { 
          ...doc, 
          content: extractResponse.content,  // Store the extracted content
          status: 'generating' as const 
        } : doc
      ));
  
      // Step 3: Generate metadata using the extracted content
      const metadata = await servicesClient.generateDocumentMetadata(extractResponse.content);
  
      // Update with final data
      onDocumentsChange((prevDocs: ProcessedDocument[]) => prevDocs.map((doc: ProcessedDocument) => 
        doc.id === documentId ? {
          ...doc,
          name: metadata.name,
          description: metadata.description,
          status: 'completed' as const
        } : doc
      ));
  
      show(`Document "${file.name}" processed successfully`, { severity: 'success' });
    } catch (error) {
      console.error('Error processing document:', error);
      
      onDocumentsChange((prevDocs: ProcessedDocument[]) => {
        const docExists = prevDocs.some((d: ProcessedDocument) => d.id === documentId);
        
        if (!docExists) {
          const errorDoc: ProcessedDocument = {
            id: documentId,
            name: '',
            description: '',
            path: '',
            content: '',
            originalName: file.name,
            status: 'error' as const
          };
          return [...prevDocs, errorDoc];
        }
        
        return prevDocs.map((doc: ProcessedDocument) => 
          doc.id === documentId ? { ...doc, status: 'error' as const } : doc
        );
      });
      
      show(`Failed to process document "${file.name}"`, { severity: 'error' });
    }
  }, [sessionToken, onDocumentsChange, show]);
  
  const handleFileUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files?.length) return;
  
    // Process each file
    for (const file of Array.from(files)) {
      // Check file size
      if (file.size > MAX_FILE_SIZE) {
        show(`File "${file.name}" is too large. Maximum size is 5 MB.`, { severity: 'error' });
        continue; // Skip this file and process the next one
      }
      
      await processDocument(file);
    }

    // Reset input
    event.target.value = '';
  }, [processDocument, show]);

  const handleDocumentUpdate = useCallback((id: string, field: 'name' | 'description', value: string) => {
    onDocumentsChange(documents.map(doc => 
      doc.id === id ? { ...doc, [field]: value } : doc
    ));
  }, [documents, onDocumentsChange]);

  const handleRemoveDocument = useCallback((id: string) => {
    onDocumentsChange(documents.filter(doc => doc.id !== id));
  }, [documents, onDocumentsChange]);

  const canProceed = documents.length === 0 || documents.every(doc => doc.status === 'completed');

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Upload Documents</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
      Select documents to add context to test generation (optional).
      </Typography>

      <Box sx={{ mb: 3 }}>
        <input
          type="file"
          multiple
          onChange={handleFileUpload}
          style={{ display: 'none' }}
          id="document-upload"
          accept={SUPPORTED_FILE_EXTENSIONS.join(',')}
        />
        
        <label htmlFor="document-upload">
          <LoadingButton
            component="span"
            variant="contained"
            startIcon={<UploadFileIcon />}
            disabled={documents.some(doc => doc.status !== 'completed' && doc.status !== 'error')}
          >
            Select Documents
          </LoadingButton>
        </label>
        <FormHelperText>
          Supported formats: {SUPPORTED_FILE_EXTENSIONS.join(', ')} • Maximum file size: 5 MB
        </FormHelperText>
      </Box>

      {documents.length > 0 && (
        <Stack spacing={2} sx={{ mb: 3 }}>
          {documents.map((doc) => (
            <Paper key={doc.id} sx={{ p: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
                <Box sx={{ flex: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Typography variant="subtitle1">{doc.originalName}</Typography>
                    <Chip
                      label={doc.status}
                      color={
                        doc.status === 'completed' ? 'success' :
                        doc.status === 'error' ? 'error' :
                        'info'
                      }
                      size="small"
                    />
                    {doc.status !== 'uploading' && (
                      <Button
                        size="small"
                        color="error"
                        startIcon={<DeleteIcon />}
                        onClick={() => handleRemoveDocument(doc.id)}
                      >
                        Remove
                      </Button>
                    )}
                  </Box>

                  {doc.status === 'completed' && (
                    <>
                      <TextField
                        fullWidth
                        label="Name"
                        value={doc.name}
                        onChange={(e) => handleDocumentUpdate(doc.id, 'name', e.target.value)}
                        sx={{ mb: 2 }}
                        size="small"
                      />
                      <TextField
                        fullWidth
                        multiline
                        rows={2}
                        label="Description"
                        value={doc.description}
                        onChange={(e) => handleDocumentUpdate(doc.id, 'description', e.target.value)}
                        size="small"
                      />
                    </>
                  )}

                  {doc.status !== 'completed' && doc.status !== 'error' && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CircularProgress size={16} />
                      <Typography variant="body2" color="text.secondary">
                        {doc.status === 'uploading' && 'Uploading...'}
                        {doc.status === 'extracting' && 'Extracting content...'}
                        {doc.status === 'generating' && 'Generating metadata...'}
                      </Typography>
                    </Box>
                  )}

                  {doc.status === 'error' && (
                    <Alert severity="error" sx={{ mt: 1 }}>
                      Failed to process this document. Please try uploading again.
                    </Alert>
                  )}
                </Box>
              </Box>
            </Paper>
          ))}
        </Stack>
      )}

    </Box>
  );
};

// Step 3: Review Samples Component  
const ReviewSamples = ({ 
  samples, 
  onSamplesChange,
  sessionToken, 
  configData,
  documents,
  isLoading = false
}: {
  samples: Sample[];
  onSamplesChange: (samples: Sample[]) => void;
  sessionToken: string;
  configData: ConfigData;
  documents: ProcessedDocument[];
  isLoading?: boolean;
}) => {  const [isLoadingMore, setIsLoadingMore] = useState(false);
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
      const servicesClient = apiFactory.getServicesClient();
      
      // Create documents payload with content instead of paths
      const documentPayload = documents
        .filter(doc => doc.status === 'completed')
        .map(doc => ({
          name: doc.name,
          description: doc.description,
          content: doc.content
        }));
      
      const response = await servicesClient.generateTests({
        prompt: generatePromptFromConfig(configData),
        num_tests: 5,
        documents: documentPayload
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
  }, [sessionToken, configData, documents, samples, onSamplesChange, show]); 


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

// Step 4: Confirm Generation Component
const ConfirmGenerate = ({ 
  samples, 
  configData, 
  documents,
  behaviors
}: { 
  samples: Sample[]; 
  configData: ConfigData; 
  documents: ProcessedDocument[];
  behaviors: Behavior[];
}) => {
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
            {configData.behaviors.map(behaviorId => {
              const behavior = behaviors.find(b => b.id === behaviorId);
              return (
                <Chip key={behaviorId} label={behavior?.name || behaviorId} size="small" />
              );
            })}
          </Stack>

          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Topics</Typography>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            {configData.tags.map(tag => (
              <Chip key={tag} label={tag} size="small" variant="outlined" />
            ))}
          </Stack>

          {documents.length > 0 && (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Documents</Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {documents.map(doc => (
                  <Chip key={doc.id} label={doc.name} size="small" variant="outlined" />
                ))}
              </Stack>
            </>
          )}          
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
  const [documents, setDocuments] = useState<ProcessedDocument[]>([]);
  const [behaviors, setBehaviors] = useState<Behavior[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isFinishing, setIsFinishing] = useState(false);
  const router = useRouter();
  const { show } = useNotifications();

  const steps = ['Configure Generation', 'Upload Documents', 'Review Samples', 'Confirm & Generate'];

  useEffect(() => {
    const fetchBehaviors = async () => {
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const behaviorsData = await apiFactory.getBehaviorClient().getBehaviors({ 
          sort_by: 'name', 
          sort_order: 'asc' 
        });
        setBehaviors(behaviorsData.filter(b => b?.id && b?.name?.trim()) || []);
      } catch (error) {
        console.error('Failed to load behaviors:', error);
      }
    };

    fetchBehaviors();
  }, [sessionToken]);

  const handleConfigSubmit = useCallback(async (config: ConfigData) => {
    setConfigData(config);
    setActiveStep(1); // Move to document upload step
  }, []);

  const handleConfigChange = useCallback((config: ConfigData) => {
    setConfigData(config);
  }, []);

  const handleDocumentsSubmit = useCallback(async () => {
    setActiveStep(2); // Move to review samples step
    setIsGenerating(true);
    
    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const servicesClient = apiFactory.getServicesClient();
      
      const generatedPrompt = generatePromptFromConfig(configData);
      
      // Create documents payload with content instead of paths
      const documentPayload = documents
        .filter(doc => doc.status === 'completed')
        .map(doc => ({
          name: doc.name,
          description: doc.description,
          content: doc.content
        }));
      
      const requestPayload = {
        prompt: generatedPrompt,
        num_tests: 5,
        documents: documentPayload
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
      console.error('Error generating samples:', error);
      show('Failed to generate samples', { severity: 'error' });
      setActiveStep(1);
    } finally {
      setIsGenerating(false);
    }
  }, [sessionToken, configData, documents, show]);
  
  
  const handleNext = useCallback(() => {
    if (activeStep === 1) { // Document upload step
      // Check if there are any documents still processing
      const hasProcessingDocuments = documents.some(doc => 
        doc.status !== 'completed' && doc.status !== 'error'
      );
      if (hasProcessingDocuments) {
        show('Please wait for all documents to finish processing', { severity: 'warning' });
        return; // ← Add this return
      }
      // Move to next step and generate samples
      handleDocumentsSubmit();
      return; // ← Add this return to prevent further execution
    } else if (activeStep === 2) { // Review samples step
      const hasUnratedSamples = samples.some(s => s.rating === null);
      if (hasUnratedSamples) {
        show('Please rate all samples before proceeding', { severity: 'error' });
        return;
      }
      setActiveStep(prev => prev + 1);
    } else {
      setActiveStep(prev => prev + 1);
    }
  }, [activeStep, documents, samples, show, handleDocumentsSubmit]);

    const handleBack = useCallback(() => {
      setActiveStep(prev => prev - 1);
    }, []);
  
    const handleFinish = useCallback(async () => {
      setIsFinishing(true);
      try {
        const apiFactory = new ApiClientFactory(sessionToken);
        const testSetsClient = apiFactory.getTestSetsClient();
        
        // Convert UI data to API format
        const generationConfig: TestSetGenerationConfig = {
          project_name: configData.project?.name,
          behaviors: configData.behaviors,
          purposes: configData.purposes,
          test_type: configData.testType,
          response_generation: configData.responseGeneration,
          test_coverage: configData.testCoverage,
          tags: configData.tags,
          description: configData.description,
        };
        
        const generationSamples: GenerationSample[] = samples.map(sample => ({
          text: sample.text,
          behavior: sample.behavior,
          topic: sample.topic,
          rating: sample.rating,
          feedback: sample.feedback,
        }));
        
        const request: TestSetGenerationRequest = {
          config: generationConfig,
          samples: generationSamples,
          synthesizer_type: "prompt",
          batch_size: 20,
        };
        
        const response = await testSetsClient.generateTestSet(request);
        
        show(response.message, { severity: 'success' });
        console.log('Test generation task started:', { 
          taskId: response.task_id, 
          estimatedTests: response.estimated_tests 
        });
        
        setTimeout(() => router.push('/tests'), 2000);
        
      } catch (error) {
        console.error('Failed to start test generation:', error);
        show('Failed to start test generation. Please try again.', { severity: 'error' });
      } finally {
        setIsFinishing(false);
      }
    }, [sessionToken, configData, samples, router, show]);
  
  const renderStepContent = useMemo(() => {
    switch (activeStep) {
      case 0:
        return <ConfigureGeneration 
          sessionToken={sessionToken} 
          onSubmit={handleConfigSubmit} 
          configData={configData}
          onConfigChange={handleConfigChange}
        />;
      case 1:
        return (
          <UploadDocuments 
            sessionToken={sessionToken}
            documents={documents}
            onDocumentsChange={setDocuments}
          />
        );
      case 2:
        return (
          <ReviewSamples 
            samples={samples}
            onSamplesChange={setSamples}
            sessionToken={sessionToken}
            configData={configData}
            documents={documents} 
            isLoading={isGenerating}
          />
        );
      case 3:
        return <ConfirmGenerate samples={samples} configData={configData} documents={documents} behaviors={behaviors} />;
      default:
        return null;
    }
  }, [activeStep, sessionToken, handleConfigSubmit, handleConfigChange, documents, samples, configData, isGenerating]);

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
            <LoadingButton 
              variant="contained" 
              onClick={handleFinish}
              loading={isFinishing}
              disabled={isFinishing}
            >
              Generate Tests
            </LoadingButton>
          ) : (
            <Button 
              variant="contained" 
              type={activeStep === 0 ? "submit" : "button"}
              form={activeStep === 0 ? "generation-config-form" : undefined}
              onClick={activeStep === 0 ? undefined : handleNext}
              disabled={isGenerating || (activeStep === 1 && documents.some(doc => 
                doc.status !== 'completed' && doc.status !== 'error'
              ))}
            >
              Next
            </Button>
          )}
        </Box>
      </Box>
    </Container>
  );
}