'use client';

import React, { useState, useEffect, useRef } from 'react';
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
  Tooltip,
  IconButton,
  LinearProgress,
  CircularProgress
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

// Common interfaces
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

// Component prop interfaces
interface GenerateTestsStepperProps {
  sessionToken: string;
}

interface ConfigureGenerationProps {
  sessionToken: string;
}

interface ReviewSamplesProps {
  samples: Sample[];
  onRatingChange: (id: number, newValue: number | null) => void;
  onFeedbackChange: (id: number, newValue: string) => void;
}

interface ConfirmGenerateProps {
  samples: Sample[];
  configData: ConfigData;
}

// Constants
const labels: { [index: number]: string } = {
  1: 'Poor',
  2: 'Fair',
  3: 'Good',
  4: 'Very Good',
  5: 'Excellent',
};

function getLabelText(value: number) {
  return `${value} Star${value !== 1 ? 's' : ''}, ${labels[value]}`;
}

const ConfigureGeneration = ({ sessionToken }: ConfigureGenerationProps) => {
  // State declarations
  const [projects, setProjects] = useState<Project[]>([]);
  const [behaviors, setBehaviors] = useState<Behavior[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [selectedBehaviors, setSelectedBehaviors] = useState<string[]>([]);
  const [selectedPurposes, setSelectedPurposes] = useState<string[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [description, setDescription] = useState('');
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [showSuggestButton, setShowSuggestButton] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const { show } = useNotifications();

  // Constants
  const purposes = [
    'Regression Testing',
    'New Feature Testing',
    'Integration Testing',
    'Edge Case Testing',
    'Performance Testing'
  ];

  // Fetch data on component mount
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      
      const apiFactory = new ApiClientFactory(sessionToken);
      const projectsClient = apiFactory.getProjectsClient();
      const behaviorClient = apiFactory.getBehaviorClient();

      try {
        const [projectsData, behaviorsData] = await Promise.all([
          projectsClient.getProjects(),
          behaviorClient.getBehaviors({ sort_by: 'name', sort_order: 'asc' })
        ]);

        if (!Array.isArray(projectsData)) {
          throw new Error('Invalid projects data received');
        }

        setProjects(projectsData);
        
        // Filter out behaviors with empty or invalid names
        const validBehaviors = behaviorsData.filter(behavior => 
          behavior && 
          behavior.id && 
          behavior.name && 
          behavior.name.trim() !== ''
        );
        setBehaviors(validBehaviors);
      } catch (error) {
        console.error('Error fetching data:', error);
        setError('Failed to load projects and behaviors. Please try again.');
        show('Failed to load configuration data', { severity: 'error' });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [sessionToken, show]);

  // Field validation
  const handleFieldTouch = (field: string) => {
    setTouched(prev => ({ ...prev, [field]: true }));
  };

  const getFieldError = (field: string, value: any): string => {
    if (!touched[field]) return '';
    
    switch (field) {
      case 'project':
        return !value ? 'Project is required' : '';
      case 'behaviors':
        return value.length === 0 ? 'At least one behavior must be selected' : '';
      case 'purposes':
        return value.length === 0 ? 'At least one purpose must be selected' : '';
      case 'tags':
        return value.length === 0 ? 'At least one aspect must be added' : '';
      case 'description':
        return !value.trim() ? 'Description is required' : '';
      default:
        return '';
    }
  };

  // Event handlers
  const handleDescriptionFocus = () => {
    if (!description.trim()) {
      setShowSuggestButton(true);
    }
  };

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setDescription(newValue);
    setShowSuggestButton(!newValue.trim());
  };

  const handleSuggestDescription = () => {
    // This will be implemented later with API integration
    console.log('Suggesting description based on current inputs');
  };

  // Form validation
  const errors = {
    project: getFieldError('project', selectedProject),
    behaviors: getFieldError('behaviors', selectedBehaviors),
    purposes: getFieldError('purposes', selectedPurposes),
    tags: getFieldError('tags', tags),
    description: getFieldError('description', description)
  };

  const isFormValid = () => {
    // Mark all fields as touched
    const allFields = ['project', 'behaviors', 'purposes', 'tags', 'description'];
    setTouched(allFields.reduce((acc, field) => ({ ...acc, [field]: true }), {}));

    // Check all validation errors
    const validationErrors = {
      project: !selectedProject,
      behaviors: selectedBehaviors.length === 0,
      purposes: selectedPurposes.length === 0,
      tags: tags.length === 0,
      description: !description.trim()
    };

    const hasErrors = Object.values(validationErrors).some(error => error);
    
    if (hasErrors) {
      show('Please fill in all required fields', { severity: 'error' });
      return false;
    }

    return true;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    return isFormValid();
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button variant="contained" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </Box>
    );
  }

  return (
    <form 
      id="generation-config-form" 
      noValidate 
      onSubmit={handleSubmit}
    >
      <Grid container spacing={3}>
        {/* Left Column */}
        <Grid item xs={12} md={6}>
          <Box sx={{ mb: 3 }}>
            <Autocomplete
              options={projects}
              value={selectedProject}
              onChange={(_, newValue) => setSelectedProject(newValue)}
              onBlur={() => handleFieldTouch('project')}
              getOptionLabel={(option) => option.name}
              isOptionEqualToValue={(option, value) => option.id === value.id}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Select Project"
                  variant="outlined"
                  required
                  error={!!errors.project}
                  helperText={errors.project}
                />
              )}
            />
          </Box>

          <FormControl 
            fullWidth 
            sx={{ mb: 3 }}
            error={!!errors.behaviors}
          >
            <InputLabel required>Behaviors</InputLabel>
            <Select
              multiple
              value={selectedBehaviors}
              onChange={(e) => setSelectedBehaviors(e.target.value as string[])}
              onBlur={() => handleFieldTouch('behaviors')}
              input={<OutlinedInput label="Behaviors" />}
              renderValue={(selected) => (
                <Stack gap={1} direction="row" flexWrap="wrap">
                  {selected.map((value) => {
                    const behavior = behaviors.find(b => b.id === value);
                    return (
                      <Chip 
                        key={value} 
                        label={behavior?.name || value}
                        size="small"
                      />
                    );
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
            {errors.behaviors && (
              <FormHelperText>{errors.behaviors}</FormHelperText>
            )}
          </FormControl>

          <FormControl 
            fullWidth 
            sx={{ mb: 3 }}
            error={!!errors.purposes}
          >
            <InputLabel required>Purpose</InputLabel>
            <Select
              multiple
              value={selectedPurposes}
              onChange={(e) => setSelectedPurposes(e.target.value as string[])}
              onBlur={() => handleFieldTouch('purposes')}
              input={<OutlinedInput label="Purpose" />}
              renderValue={(selected) => (
                <Stack gap={1} direction="row" flexWrap="wrap">
                  {selected.map((value) => (
                    <Chip 
                      key={value} 
                      label={value}
                      size="small"
                    />
                  ))}
                </Stack>
              )}
            >
              {purposes.map((purpose) => (
                <MenuItem key={purpose} value={purpose}>
                  {purpose}
                </MenuItem>
              ))}
            </Select>
            {errors.purposes && (
              <FormHelperText>{errors.purposes}</FormHelperText>
            )}
          </FormControl>
        </Grid>

        {/* Right Column */}
        <Grid item xs={12} md={6}>
          <TextField
            select
            fullWidth
            label="Test Type"
            value="single_turn"
            sx={{ mb: 3 }}
            required
          >
            <MenuItem value="single_turn">Single Turn</MenuItem>
          </TextField>

          <TextField
            select
            fullWidth
            label="Response Generation"
            defaultValue="prompt_only"
            sx={{ mb: 3 }}
            required
          >
            <MenuItem value="prompt_only">
              Generate Prompts Only
            </MenuItem>
            <MenuItem value="prompt_and_response">
              Generate Prompts with Expected Responses
            </MenuItem>
          </TextField>

          <TextField
            select
            fullWidth
            label="Test Coverage"
            defaultValue="standard"
            sx={{ mb: 3 }}
            required
          >
            <MenuItem value="focused">
              Focused Coverage (100+ test cases)
            </MenuItem>
            <MenuItem value="standard">
              Standard Coverage (1,000+ test cases)
            </MenuItem>
            <MenuItem value="comprehensive">
              Comprehensive Coverage (5,000+ test cases)
            </MenuItem>
          </TextField>
        </Grid>

        {/* Full Width Fields */}
        <Grid item xs={12}>
          <Box sx={{ mb: 3 }}>
            <BaseTag
              value={tags}
              onChange={setTags}
              onBlur={() => handleFieldTouch('tags')}
              placeholder="Add aspects..."
              label="Aspects to cover"
              required
              error={!!errors.tags}
              helperText={errors.tags}
            />
          </Box>

          <Box sx={{ mb: 3 }}>
            <TextField
              fullWidth
              multiline
              rows={4}
              label="Describe what you want to test"
              value={description}
              onChange={handleDescriptionChange}
              onFocus={handleDescriptionFocus}
              onBlur={() => handleFieldTouch('description')}
              variant="outlined"
              required
              error={!!errors.description}
              helperText={errors.description}
            />
            {showSuggestButton && (
              <Box sx={{ display: 'flex', justifyContent: 'flex-start', mt: 1 }}>
                <Button
                  variant="contained"
                  size="small"
                  onClick={handleSuggestDescription}
                >
                  Suggest description
                </Button>
              </Box>
            )}
          </Box>
        </Grid>
      </Grid>
    </form>
  );
};

const ReviewSamples = ({ samples: initialSamples, onRatingChange, onFeedbackChange }: ReviewSamplesProps) => {
  const [hover, setHover] = useState<Record<number, number>>({});
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [regenerating, setRegenerating] = useState<Record<number, boolean>>({});
  const [localSamples, setLocalSamples] = useState<Sample[]>(initialSamples);
  
  // Debounce feedback updates
  const feedbackDebounceTimerRef = useRef<Record<number, NodeJS.Timeout>>({});

  // Update local samples when parent samples change (except for feedback values)
  useEffect(() => {
    setLocalSamples(prevLocalSamples => 
      initialSamples.map(sample => ({
        ...sample,
        // Preserve local feedback values to avoid focus issues
        feedback: prevLocalSamples.find(s => s.id === sample.id)?.feedback || sample.feedback
      }))
    );
  }, [initialSamples]);

  const handleLoadMore = () => {
    setIsLoadingMore(true);
    // TODO: Implement actual loading logic
    setTimeout(() => {
      setIsLoadingMore(false);
    }, 2000);
  };

  const handleRegenerate = (sampleId: number) => {
    setRegenerating(prev => ({ ...prev, [sampleId]: true }));
    // TODO: Implement actual regeneration logic
    setTimeout(() => {
      setRegenerating(prev => ({ ...prev, [sampleId]: false }));
    }, 1500);
  };

  const handleLocalFeedbackChange = (id: number, newValue: string) => {
    // Update local state immediately for responsive UI
    setLocalSamples(prevSamples => 
      prevSamples.map(sample => 
        sample.id === id ? { ...sample, feedback: newValue } : sample
      )
    );
    
    // Clear previous debounce timer if exists
    if (feedbackDebounceTimerRef.current[id]) {
      clearTimeout(feedbackDebounceTimerRef.current[id]);
    }
    
    // Debounce the update to parent state to avoid unnecessary re-renders
    feedbackDebounceTimerRef.current[id] = setTimeout(() => {
      onFeedbackChange(id, newValue);
    }, 300);
  };

  const handleLocalRatingChange = (id: number, newValue: number | null) => {
    // If no rating or rating is 4-5 stars, clear feedback
    if (newValue === null || newValue >= 4) {
      setLocalSamples(prevSamples => 
        prevSamples.map(sample => 
          sample.id === id ? { ...sample, rating: newValue, feedback: "" } : sample
        )
      );
    } else {
      // Rating is 1-3 stars
      setLocalSamples(prevSamples => 
        prevSamples.map(sample => 
          sample.id === id ? { ...sample, rating: newValue } : sample
        )
      );
    }
    
    // Update parent state
    onRatingChange(id, newValue);
  };
  
  // Clean up timers on component unmount
  useEffect(() => {
    const timers = feedbackDebounceTimerRef.current;
    return () => {
      Object.values(timers).forEach(timer => {
        clearTimeout(timer);
      });
    };
  }, []);

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="h6" gutterBottom>
        Evaluate Samples
      </Typography>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Please review the generated test samples and provide your feedback. Rate each sample using the stars and optionally add comments for improvement.
      </Typography>

      <Stack spacing={2}>
        {localSamples.map((sample) => (
          <Paper 
            key={sample.id} 
            sx={{ 
              p: 2,
              '& .MuiTextField-root': {
                mt: 0
              },
              // Add subtle highlight for unrated samples
              border: sample.rating === null ? '1px solid' : 'none',
              borderColor: 'warning.light',
              bgcolor: sample.rating === null ? 'warning.lighter' : 'inherit'
            }}
          >
            {/* Chips Row */}
            <Box sx={{ 
              display: 'flex', 
              gap: 1, 
              mb: 1.5,
              borderBottom: '1px solid',
              borderColor: 'divider',
              pb: 1
            }}>
              <Chip
                label={sample.behavior}
                size="small"
                color={sample.behavior === 'Reliability' ? 'success' : 'warning'}
              />
              <Chip
                label={sample.topic}
                size="small"
                variant="outlined"
                color="primary"
              />
            </Box>

            {/* Content Row */}
            <Box sx={{ display: 'flex', gap: 2 }}>
              {/* Left side - Text and Feedback (80%) */}
              <Box sx={{ flex: '0 0 80%' }}>
                <Typography 
                  variant="body1" 
                  sx={{ 
                    fontStyle: 'italic',
                    mb: 1
                  }}
                >
                  {sample.text}
                </Typography>
                <Box sx={{ 
                  display: 'flex', 
                  gap: 1,
                  alignItems: 'flex-start'
                }}>
                  <TextField
                    placeholder="What could be improved?"
                    value={sample.feedback}
                    onChange={(e) => handleLocalFeedbackChange(sample.id, e.target.value)}
                    variant="standard"
                    size="small"
                    disabled={Boolean(sample.rating === null || sample.rating >= 4)}
                    sx={{ 
                      flex: 1,
                      '& .Mui-disabled': {
                        WebkitTextFillColor: 'rgba(0, 0, 0, 0.38)'
                      }
                    }}
                  />
                  <LoadingButton
                    loading={regenerating[sample.id]}
                    onClick={() => handleRegenerate(sample.id)}
                    variant="outlined"
                    size="small"
                    startIcon={<AutorenewIcon />}
                    disabled={Boolean(sample.rating === null || !sample.feedback || sample.rating >= 4)}
                    sx={{ 
                      minWidth: 'auto',
                      opacity: Boolean(sample.feedback && sample.rating !== null && sample.rating < 4) ? 1 : 0.5
                    }}
                  >
                    Regenerate
                  </LoadingButton>
                </Box>
              </Box>

              {/* Right side - Rating (20%) */}
              <Box sx={{ 
                flex: '0 0 20%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative'
              }}>
                {sample.rating === null && (
                  <Box
                    sx={{
                      position: 'absolute',
                      top: -10,
                      left: '50%',
                      transform: 'translateX(-50%)',
                      bgcolor: 'warning.main',
                      color: 'warning.contrastText',
                      px: 1,
                      py: 0.5,
                      borderRadius: 1,
                      fontSize: '0.75rem',
                      whiteSpace: 'nowrap',
                      '&::after': {
                        content: '""',
                        position: 'absolute',
                        top: '100%',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        border: '4px solid transparent',
                        borderTopColor: 'warning.main'
                      }
                    }}
                  >
                    Click to Rate
                  </Box>
                )}
                <Rating
                  value={sample.rating}
                  onChange={(_, newValue) => handleLocalRatingChange(sample.id, newValue)}
                  onChangeActive={(_, newHover) => {
                    setHover(prev => ({ ...prev, [sample.id]: newHover }));
                  }}
                  size="large"
                  getLabelText={getLabelText}
                  emptyIcon={<StarIcon style={{ opacity: 0.55 }} fontSize="inherit" />}
                />
                {sample.rating !== null && (
                  <Typography 
                    variant="caption" 
                    color="text.secondary"
                    sx={{ mt: 0.5 }}
                  >
                    {labels[hover[sample.id] !== undefined ? hover[sample.id] : sample.rating]}
                  </Typography>
                )}
              </Box>
            </Box>
          </Paper>
        ))}

        {/* Load More Button */}
        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'flex-start',
          pt: 1,
          pb: 2 
        }}>
          <LoadingButton
            onClick={handleLoadMore}
            loading={isLoadingMore}
            loadingPosition="start"
            startIcon={<AutoFixHighIcon />}
            variant="outlined"
            sx={{ 
              borderColor: 'divider',
              color: 'text.secondary',
              '&:hover': {
                borderColor: 'primary.main',
                bgcolor: 'action.hover'
              }
            }}
          >
            Load More Samples
          </LoadingButton>
        </Box>
      </Stack>
    </Box>
  );
};

const ConfirmGenerate = ({ samples, configData }: ConfirmGenerateProps) => {
  // Calculate feedback statistics
  const totalSamples = samples.length;
  const samplesWithFeedback = samples.filter(sample => sample.feedback && sample.feedback.trim() !== "").length;
  const feedbackPercentage = totalSamples > 0 ? Math.round((samplesWithFeedback / totalSamples) * 100) : 0;
  
  // Calculate average rating - only include samples with ratings
  const ratedSamples = samples.filter(s => s.rating !== null);
  const totalRating = ratedSamples.reduce((acc, sample) => acc + (sample.rating || 0), 0);
  const averageRating = ratedSamples.length > 0 
    ? (totalRating / ratedSamples.length).toFixed(1) 
    : "N/A";
    
  // Convert raw values to human-readable labels
  const testTypeLabels: Record<string, string> = {
    'single_turn': 'Single Turn'
  };
  
  const responseGenerationLabels: Record<string, string> = {
    'prompt_only': 'Generate Prompts Only',
    'prompt_and_response': 'Generate Prompts with Expected Responses'
  };
  
  const testCoverageLabels: Record<string, string> = {
    'focused': 'Focused Coverage (100+ test cases)',
    'standard': 'Standard Coverage (1,000+ test cases)',
    'comprehensive': 'Comprehensive Coverage (5,000+ test cases)'
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Confirm Test Generation
      </Typography>
      
      {/* Configuration Summary */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          Test Configuration
        </Typography>
        
        <Grid container spacing={2}>
          <Grid item xs={6} md={4}>
            <Typography variant="body2" color="text.secondary">Project</Typography>
            <Typography variant="body1" gutterBottom>{configData.project?.name || "Not set"}</Typography>
            
            <Typography variant="body2" color="text.secondary">Test Type</Typography>
            <Typography variant="body1" gutterBottom>
              {testTypeLabels[configData.testType] || configData.testType}
            </Typography>
            
            <Typography variant="body2" color="text.secondary">Response Generation</Typography>
            <Typography variant="body1" gutterBottom>
              {responseGenerationLabels[configData.responseGeneration] || configData.responseGeneration}
            </Typography>
          </Grid>
          
          <Grid item xs={6} md={4}>
            <Typography variant="body2" color="text.secondary">Test Coverage</Typography>
            <Typography variant="body1" gutterBottom>
              {testCoverageLabels[configData.testCoverage] || configData.testCoverage}
            </Typography>
            
            <Typography variant="body2" color="text.secondary">Behaviors</Typography>
            <Box sx={{ mb: 1 }}>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {configData.behaviors.length > 0 ? (
                  configData.behaviors.map((behavior, index) => (
                    <Chip key={index} label={behavior} size="small" sx={{ mt: 0.5 }} />
                  ))
                ) : (
                  <Typography variant="body1">None selected</Typography>
                )}
              </Stack>
            </Box>
            
            <Typography variant="body2" color="text.secondary">Purposes</Typography>
            <Box>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {configData.purposes.length > 0 ? (
                  configData.purposes.map((purpose, index) => (
                    <Chip key={index} label={purpose} size="small" sx={{ mt: 0.5 }} />
                  ))
                ) : (
                  <Typography variant="body1">None selected</Typography>
                )}
              </Stack>
            </Box>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Typography variant="body2" color="text.secondary">Aspects to cover</Typography>
            <Box sx={{ mb: 1 }}>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {configData.tags.length > 0 ? (
                  configData.tags.map((tag, index) => (
                    <Chip key={index} label={tag} size="small" sx={{ mt: 0.5 }} />
                  ))
                ) : (
                  <Typography variant="body1">None added</Typography>
                )}
              </Stack>
            </Box>
            
            <Typography variant="body2" color="text.secondary">Description</Typography>
            <Typography variant="body1" sx={{ 
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
            }}>
              {configData.description || "No description provided"}
            </Typography>
          </Grid>
        </Grid>
      </Paper>
      
      {/* Samples Summary */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          Sample Evaluation Summary
        </Typography>
        
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Typography variant="body2" color="text.secondary">Total Samples</Typography>
            <Typography variant="body1" gutterBottom>{totalSamples}</Typography>
            
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">Average Rating</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Rating 
                  value={parseFloat(averageRating) || 0} 
                  precision={0.1} 
                  readOnly 
                  size="medium"
                />
                <Typography variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                  ({averageRating})
                </Typography>
              </Box>
            </Box>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <Typography variant="body2" color="text.secondary">Feedback Provided</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.5, mb: 2 }}>
              <Box sx={{ flex: 1, mr: 2 }}>
                <Typography variant="body1">{feedbackPercentage}% ({samplesWithFeedback}/{totalSamples})</Typography>
              </Box>
              <LinearProgress 
                variant="determinate" 
                value={feedbackPercentage}
                sx={{ 
                  width: '100px', 
                  height: 8,
                  borderRadius: 1,
                  backgroundColor: 'action.hover',
                  '& .MuiLinearProgress-bar': {
                    backgroundColor: feedbackPercentage > 50 ? 'success.main' : 'primary.main'
                  }
                }}
              />
            </Box>
            
            <Typography variant="body2" color="text.secondary">Sample Breakdown</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 0.5 }}>
              {['Reliability', 'Compliance'].map(behavior => {
                const count = samples.filter(s => s.behavior === behavior).length;
                return (
                  <Chip
                    key={behavior}
                    label={`${behavior}: ${count}`}
                    size="small"
                    color={behavior === 'Reliability' ? 'success' : 'warning'}
                    variant="outlined"
                  />
                );
              })}
            </Box>
          </Grid>
        </Grid>
      </Paper>
      
      {/* Information Box */}
      <Box sx={{ mb: 2 }}>
        <Alert severity="info">
          <AlertTitle>What happens next?</AlertTitle>
          <Typography variant="body2">
            When you click &quot;Generate Tests&quot;, our system will:
          </Typography>
          <Box component="ul" sx={{ pl: 2, mt: 1, mb: 0 }}>
            <li>Begin the test generation process using your configuration and feedback</li>
            <li>Notify you via email when your tests are ready</li>
            <li>Make the generated tests available in your test library</li>
          </Box>
        </Alert>
      </Box>
    </Box>
  );
};

export default function GenerateTestsStepper({ sessionToken }: GenerateTestsStepperProps) {
  const [activeStep, setActiveStep] = useState(0);
  const router = useRouter();
  const { show } = useNotifications();
  const feedbackDebounceTimerRef = useRef<Record<number, NodeJS.Timeout>>({});

  // Initial sample data
  const [samples, setSamples] = useState<Sample[]>([
    {
      id: 1,
      text: "How can I understand the overall cost and its impact on the return of the investment for insurance-based investment products?",
      behavior: "Reliability",
      topic: "Cost Analysis",
      rating: null,
      feedback: ""
    },
    {
      id: 2,
      text: "How often should information about costs and charges be provided to customers during the life cycle of the investment?",
      behavior: "Compliance",
      topic: "Disclosure",
      rating: null,
      feedback: ""
    },
    {
      id: 3,
      text: "What information should be included in the disclosure of costs and charges?",
      behavior: "Compliance",
      topic: "Documentation",
      rating: null,
      feedback: ""
    }
  ]);
  
  // Configuration data state
  const [configData, setConfigData] = useState<ConfigData>({
    project: null,
    behaviors: [],
    purposes: [],
    testType: "single_turn",
    responseGeneration: "prompt_only",
    testCoverage: "standard",
    tags: [],
    description: ""
  });
  
  // Use a ref to track feedback changes without causing re-renders
  const feedbackUpdates = useRef<Record<number, string>>({});

  // Step handlers
  const handleNext = () => {
    // Validate first step
    if (activeStep === 0) {
      const configForm = document.getElementById('generation-config-form') as HTMLFormElement;
      if (configForm) {
        const event = new Event('submit', { cancelable: true });
        configForm.dispatchEvent(event);
        
        // Get the form validation result directly from the form's onSubmit handler
        const formValid = configForm.onsubmit ? (configForm.onsubmit as any)(event) : true;
        
        if (!formValid) {
          return;
        }
        
        // Get configuration data from form fields
        // In a real implementation, this would be replaced with proper form data retrieval
        // Here we're just simulating it for demonstration purposes
        const projectSelect = document.querySelector('[name="project"]') as HTMLInputElement;
        const projectName = projectSelect?.value || "Sample Project";
        
        // Update config data in state
        setConfigData(prev => ({
          ...prev,
          project: { id: '123', name: projectName } as Project,
          behaviors: ['Compliance', 'Reliability'],
          purposes: ['Regression Testing', 'Edge Case Testing'],
          testType: 'single_turn',
          responseGeneration: 'prompt_only',
          testCoverage: 'standard',
          tags: ['Cost Analysis', 'Risk Assessment', 'Regulatory Compliance'],
          description: "Testing the system's ability to provide accurate information about investment costs and fees."
        }));
      }
    }
    
    // Validate samples step
    if (activeStep === 1) {
      // Apply any pending feedback updates to the samples
      if (Object.keys(feedbackUpdates.current).length > 0) {
        setSamples(prevSamples => 
          prevSamples.map(sample => ({
            ...sample,
            feedback: feedbackUpdates.current[sample.id] !== undefined 
              ? feedbackUpdates.current[sample.id] 
              : sample.feedback
          }))
        );
        feedbackUpdates.current = {};
      }
      
      const hasUnratedSamples = samples.some(sample => sample.rating === null);
      if (hasUnratedSamples) {
        show('Please rate all samples before proceeding', { severity: 'error' });
        return;
      }
    }
    
    setActiveStep(prevStep => prevStep + 1);
  };

  const handleBack = () => {
    setActiveStep(prevStep => prevStep - 1);
  };

  const handleFinish = () => {
    // Apply any pending feedback updates to the samples
    if (Object.keys(feedbackUpdates.current).length > 0) {
      setSamples(prevSamples => 
        prevSamples.map(sample => ({
          ...sample,
          feedback: feedbackUpdates.current[sample.id] !== undefined 
            ? feedbackUpdates.current[sample.id] 
            : sample.feedback
        }))
      );
      feedbackUpdates.current = {};
    }
    
    // Show a success notification
    show('Test generation started. You will be notified by email when complete.', { 
      severity: 'success',
      autoHideDuration: 5000
    });
    
    // Simulate an API call for test generation
    console.log('Generating tests...', { config: configData, samples });
    
    // Redirect back to tests page
    setTimeout(() => {
      router.push('/tests');
    }, 1000);
  };

  // Sample handling
  const handleRatingChange = (id: number, newValue: number | null) => {
    setSamples(prevSamples => 
      prevSamples.map(sample => 
        sample.id === id ? { ...sample, rating: newValue } : sample
      )
    );
  };

  const handleFeedbackChange = (id: number, newValue: string) => {
    // Store feedback updates in ref without triggering re-renders
    feedbackUpdates.current[id] = newValue;
  };

  // Step definitions
  const steps = [
    {
      label: 'Configure Generation',
      component: () => <ConfigureGeneration sessionToken={sessionToken} />
    },
    {
      label: 'Review Samples',
      component: () => (
        <ReviewSamples 
          samples={samples}
          onRatingChange={handleRatingChange}
          onFeedbackChange={handleFeedbackChange}
        />
      )
    },
    {
      label: 'Confirm & Generate',
      component: () => (
        <ConfirmGenerate 
          samples={samples}
          configData={configData}
        />
      )
    }
  ];

  const CurrentStepComponent = steps[activeStep].component;

  // Clean up timers on component unmount
  useEffect(() => {
    const timers = feedbackDebounceTimerRef.current;
    return () => {
      Object.values(timers).forEach(timer => {
        clearTimeout(timer);
      });
    };
  }, []);

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Box sx={{ 
        minHeight: '80vh',
        display: 'flex',
        flexDirection: 'column'
      }}>
        <Stepper 
          activeStep={activeStep} 
          sx={{ 
            py: 4,
            px: { xs: 2, sm: 4, md: 6 }
          }}
        >
          {steps.map((step) => (
            <Step key={step.label}>
              <StepLabel>{step.label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        <Box 
          sx={{ flex: 1, mt: 4, px: { xs: 2, sm: 4, md: 6 } }}
        >
          <CurrentStepComponent />
        </Box>

        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'flex-end',
          gap: 2,
          mt: 4,
          px: { xs: 2, sm: 4, md: 6 }
        }}>
          {activeStep > 0 && (
            <Button
              variant="outlined"
              onClick={handleBack}
            >
              Back
            </Button>
          )}
          
          {activeStep === steps.length - 1 ? (
            <Button
              variant="contained"
              onClick={handleFinish}
            >
              Generate Tests
            </Button>
          ) : (
            <Button
              variant="contained"
              onClick={handleNext}
              disabled={activeStep === 1 && samples.some(sample => sample.rating === null)}
            >
              {activeStep === 0 ? "Generate Samples" : "Next"}
            </Button>
          )}
        </Box>
      </Box>
    </Container>
  );
} 