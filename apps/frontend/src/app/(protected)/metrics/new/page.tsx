'use client';

import * as React from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { PageContainer } from '@toolpad/core/PageContainer';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import IconButton from '@mui/material/IconButton';
import { useTheme } from '@mui/material/styles';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNotifications } from '@/components/common/NotificationContext';
import Stepper from '@mui/material/Stepper';
import Step from '@mui/material/Step';
import StepLabel from '@mui/material/StepLabel';
import BaseTag from '@/components/common/BaseTag';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { MetricCreate } from '@/utils/api-client/interfaces/metric';
import { TypeLookupClient } from '@/utils/api-client/type-lookup-client';
import { TypeLookupsQueryParams } from '@/utils/api-client/interfaces/type-lookup';
import { User } from '@/utils/api-client/interfaces/user';
import { UUID } from 'crypto';
import { Model } from '@/utils/api-client/interfaces/model';
import CircularProgress from '@mui/material/CircularProgress';

// Add session type augmentation
declare module 'next-auth' {
  interface Session {
    session_token?: string;
    user?: User;
  }
}

interface MetricFormData {
  name: string;
  description: string;
  tags: string[];
  evaluation_prompt: string;
  evaluation_steps: string[];
  reasoning: string;
  score_type: 'binary' | 'numeric';
  min_score?: number;
  max_score?: number;
  threshold?: number;
  explanation: string;
  model_id: string;
}

const initialFormData: MetricFormData = {
  name: '',
  description: '',
  tags: [],
  evaluation_prompt: '',
  evaluation_steps: [''],
  reasoning: '',
  score_type: 'binary',
  explanation: '',
  model_id: '',
};

const steps = ['Metric Information and Criteria', 'Confirmation'];

const STEP_SEPARATOR = '\n---\n';

export default function NewMetricPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const notifications = useNotifications();
  const { data: session } = useSession();
  const theme = useTheme();
  const type = searchParams.get('type');
  const [activeStep, setActiveStep] = React.useState(0);
  const [formData, setFormData] =
    React.useState<MetricFormData>(initialFormData);
  const [models, setModels] = React.useState<Model[]>([]);
  const [isLoadingModels, setIsLoadingModels] = React.useState(true);
  const [isCreating, setIsCreating] = React.useState(false);

  // Redirect if no type is selected
  React.useEffect(() => {
    if (!type) {
      router.push('/metrics');
    }
  }, [type, router]);

  // Fetch models on component mount
  React.useEffect(() => {
    const fetchModels = async () => {
      if (!session?.session_token) return;

      try {
        setIsLoadingModels(true);
        const apiClient = new ApiClientFactory(session.session_token);
        const modelsClient = apiClient.getModelsClient();
        const response = await modelsClient.getModels({
          sort_by: 'name',
          sort_order: 'asc',
          skip: 0,
          limit: 100,
        });
        setModels(response.data || []); // Use .data instead of .items
      } catch (error) {
        notifications.show('Failed to load evaluation models', {
          severity: 'error',
        });
      } finally {
        setIsLoadingModels(false);
      }
    };

    fetchModels();
  }, [session?.session_token, notifications]);

  const handleChange =
    (field: keyof MetricFormData) =>
    (
      event:
        | React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
        | SelectChangeEvent<string | 'binary' | 'numeric'>
    ) => {
      const value = event.target.value;
      setFormData(prev => ({
        ...prev,
        [field]: value,
      }));
    };

  const handleStepChange =
    (index: number) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const newSteps = [...formData.evaluation_steps];
      newSteps[index] = event.target.value;
      setFormData(prev => ({
        ...prev,
        evaluation_steps: newSteps,
      }));
    };

  const addStep = () => {
    setFormData(prev => ({
      ...prev,
      evaluation_steps: [...prev.evaluation_steps, ''],
    }));
  };

  const removeStep = (index: number) => {
    setFormData(prev => ({
      ...prev,
      evaluation_steps: prev.evaluation_steps.filter((_, i) => i !== index),
    }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (activeStep !== steps.length - 1) {
      // If not on the final step, don't submit
      return;
    }

    setIsCreating(true);

    try {
      if (!session?.session_token) {
        throw new Error(
          'No session token available. Please try logging in again.'
        );
      }

      const apiClient = new ApiClientFactory(session.session_token);
      const metricsClient = apiClient.getMetricsClient();
      const typeLookupClient = apiClient.getTypeLookupClient();

      // Get both metric type and backend type in a single API call
      const allTypeLookups = await typeLookupClient.getTypeLookups({
        $filter: `(type_name eq 'MetricType' and type_value eq '${type}') or (type_name eq 'BackendType' and type_value eq 'custom')`,
      });

      const typeLookups = allTypeLookups.filter(
        lookup =>
          lookup.type_name === 'MetricType' && lookup.type_value === type
      );
      const backendTypes = allTypeLookups.filter(
        lookup =>
          lookup.type_name === 'BackendType' && lookup.type_value === 'custom'
      );

      if (!typeLookups.length) {
        throw new Error('Invalid metric type');
      }

      if (!backendTypes.length) {
        throw new Error('Custom backend type not found');
      }

      // Filter out empty steps and join with separator
      const nonEmptySteps = formData.evaluation_steps.filter(step =>
        step.trim()
      );
      const formattedSteps = nonEmptySteps.map(
        (step, index) => `Step ${index + 1}:\n${step.trim()}`
      );

      // Create the metric request object
      const metricRequest: MetricCreate = {
        name: formData.name,
        description: formData.description || '',
        tags: formData.tags,
        evaluation_prompt: formData.evaluation_prompt,
        evaluation_steps: formattedSteps.join(STEP_SEPARATOR),
        reasoning: formData.reasoning || '',
        score_type: formData.score_type,
        min_score:
          formData.score_type === 'numeric'
            ? parseFloat(String(formData.min_score))
            : undefined,
        max_score:
          formData.score_type === 'numeric'
            ? parseFloat(String(formData.max_score))
            : undefined,
        threshold:
          formData.score_type === 'numeric'
            ? parseFloat(String(formData.threshold))
            : undefined,
        explanation: formData.explanation || '',
        metric_type_id: typeLookups[0].id as UUID,
        backend_type_id: backendTypes[0].id as UUID,
        model_id: formData.model_id ? (formData.model_id as UUID) : undefined,
        owner_id: session.user?.id as UUID,
      };

      await metricsClient.createMetric(metricRequest);
      notifications.show('Metric created successfully', {
        severity: 'success',
      });
      router.push('/metrics?tab=directory');
    } catch (error) {
      notifications.show(
        error instanceof Error ? error.message : 'Failed to create metric',
        { severity: 'error' }
      );
    } finally {
      setIsCreating(false);
    }
  };

  const handleNext = (event: React.MouseEvent) => {
    event.preventDefault(); // Prevent any form submission
    setActiveStep(prevStep => prevStep + 1);
  };

  const handleBack = (event: React.MouseEvent) => {
    event.preventDefault(); // Prevent any form submission
    setActiveStep(prevStep => prevStep - 1);
  };

  const renderMetricInformation = () => (
    <>
      {/* General Section */}
      <Box sx={{ mb: 5 }}>
        <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
          General Information
        </Typography>
        <TextField
          fullWidth
          required
          label="Name"
          placeholder="e.g. Helpfulness"
          value={formData.name}
          onChange={handleChange('name')}
          helperText="Your custom metric name is simply for identification purposes only. It must not be one of Rhesis AI's default metric name, and cannot already be taken by another custom metric."
          sx={{ mb: 3 }}
        />

        <TextField
          fullWidth
          multiline
          rows={3}
          label="Description"
          value={formData.description}
          onChange={handleChange('description')}
          helperText="Provide a clear description of what this metric evaluates and its purpose."
          sx={{ mb: 3 }}
        />

        <BaseTag
          value={formData.tags}
          onChange={newTags =>
            setFormData(prev => ({ ...prev, tags: newTags }))
          }
          label="Tags"
          placeholder="Add tags (press Enter or comma to add)"
          helperText="Add relevant tags to help organize and find this metric later"
          chipColor="primary"
          addOnBlur
          delimiters={[',', 'Enter']}
          size="small"
        />
      </Box>

      {/* Evaluation Section */}
      <Box sx={{ mb: 5 }}>
        <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
          Evaluation Process
        </Typography>

        <FormControl fullWidth sx={{ mb: 3 }}>
          <InputLabel required>Evaluation Model</InputLabel>
          <Select
            value={formData.model_id}
            label="Evaluation Model"
            onChange={handleChange('model_id')}
          >
            {isLoadingModels ? (
              <MenuItem disabled>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CircularProgress size={20} />
                  <Typography>Loading models...</Typography>
                </Box>
              </MenuItem>
            ) : models.length === 0 ? (
              <MenuItem disabled>
                <Typography>No models available</Typography>
              </MenuItem>
            ) : (
              models.map(model => (
                <MenuItem key={model.id} value={model.id}>
                  <Box>
                    <Typography variant="subtitle2">{model.name}</Typography>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      display="block"
                    >
                      {model.description}
                    </Typography>
                  </Box>
                </MenuItem>
              ))
            )}
          </Select>
        </FormControl>

        <TextField
          fullWidth
          required
          multiline
          rows={3}
          label="Evaluation Prompt"
          value={formData.evaluation_prompt}
          onChange={handleChange('evaluation_prompt')}
          helperText="The main prompt that will guide the evaluation process. This should clearly state what needs to be evaluated."
          sx={{ mb: 3 }}
        />

        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Evaluation Steps
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Break down the evaluation process into clear, sequential steps. Each
          step should be specific and actionable.
        </Typography>
        {formData.evaluation_steps?.map((step, index) => (
          <Box key={index} sx={{ display: 'flex', gap: 1, mb: 2 }}>
            <TextField
              fullWidth
              required
              multiline
              rows={2}
              label={`Step ${index + 1}`}
              placeholder="Describe this evaluation step..."
              value={step}
              onChange={handleStepChange(index)}
            />
            <IconButton
              onClick={() => removeStep(index)}
              disabled={formData.evaluation_steps.length === 1}
              sx={{ mt: 1 }}
              color="error"
            >
              <DeleteIcon />
            </IconButton>
          </Box>
        ))}
        <Button startIcon={<AddIcon />} onClick={addStep} sx={{ mb: 3 }}>
          Add Step
        </Button>

        <TextField
          fullWidth
          required
          multiline
          rows={3}
          label="Reasoning Instructions"
          value={formData.reasoning}
          onChange={handleChange('reasoning')}
          helperText="Provide detailed instructions on how the evaluation should be reasoned about. Include key aspects that should be considered during the evaluation process."
          sx={{ mb: 3 }}
        />
      </Box>

      {/* Result Section */}
      <Box>
        <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
          Result Configuration
        </Typography>
        <FormControl fullWidth sx={{ mb: 3 }}>
          <InputLabel required>Score Type</InputLabel>
          <Select<'binary' | 'numeric'>
            value={formData.score_type}
            label="Score Type"
            onChange={handleChange('score_type')}
          >
            <MenuItem value="binary">Binary (Pass/Fail)</MenuItem>
            <MenuItem value="numeric">Numeric</MenuItem>
          </Select>
        </FormControl>

        {formData.score_type === 'numeric' && (
          <>
            <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
              <TextField
                required
                type="number"
                label="Minimum Score"
                value={formData.min_score || ''}
                onChange={handleChange('min_score')}
                fullWidth
              />
              <TextField
                required
                type="number"
                label="Maximum Score"
                value={formData.max_score || ''}
                onChange={handleChange('max_score')}
                fullWidth
              />
            </Box>

            <TextField
              required
              type="number"
              label="Threshold"
              value={formData.threshold || ''}
              onChange={handleChange('threshold')}
              helperText="The minimum score required for this metric to pass"
              fullWidth
              sx={{ mb: 3 }}
            />
          </>
        )}

        <TextField
          fullWidth
          required
          multiline
          rows={3}
          label="Result Explanation"
          value={formData.explanation}
          onChange={handleChange('explanation')}
          helperText="Provide instructions on how to explain the reasoning behind the score. This helps users understand why a particular score was given."
        />
      </Box>
    </>
  );

  const renderConfirmation = () => (
    <Box>
      <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
        Review Your Metric
      </Typography>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
          gap: 3,
          maxWidth: '1000px',
          mx: 'auto',
        }}
      >
        {/* Left Column */}
        <Box>
          {/* General Section Review */}
          <Paper sx={{ p: 3, mb: 3, bgcolor: 'background.default' }}>
            <Typography variant="h6" color="primary" sx={{ mb: 2 }}>
              General Information
            </Typography>

            <Box sx={{ mb: 2 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ fontWeight: 'medium' }}
              >
                Name
              </Typography>
              <Typography sx={{ color: 'text.primary' }}>
                {formData.name}
              </Typography>
            </Box>

            <Box sx={{ mb: 2 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ fontWeight: 'medium' }}
              >
                Description
              </Typography>
              <Typography sx={{ color: 'text.primary' }}>
                {formData.description || 'No description provided'}
              </Typography>
            </Box>

            <Box>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ fontWeight: 'medium', mb: 1 }}
              >
                Tags
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {formData.tags.length > 0 ? (
                  formData.tags.map(tag => (
                    <Box
                      key={tag}
                      sx={{
                        bgcolor: 'primary.main',
                        color: 'primary.contrastText',
                        px: 1.5,
                        py: 0.5,
                        borderRadius: theme => theme.shape.borderRadius * 0.25,
                        fontSize: theme.typography.helperText.fontSize,
                      }}
                    >
                      {tag}
                    </Box>
                  ))
                ) : (
                  <Typography
                    variant="body2"
                    sx={{ color: 'text.secondary', fontStyle: 'italic' }}
                  >
                    No tags added
                  </Typography>
                )}
              </Box>
            </Box>
          </Paper>

          {/* Evaluation Section Review */}
          <Paper sx={{ p: 3, bgcolor: 'background.default' }}>
            <Typography variant="h6" color="primary" sx={{ mb: 2 }}>
              Evaluation Process
            </Typography>

            <Box sx={{ mb: 2 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ fontWeight: 'medium' }}
              >
                Evaluation Model
              </Typography>
              <Typography sx={{ color: 'text.primary' }}>
                {models.find(model => model.id === formData.model_id)?.name ||
                  'No model selected'}
              </Typography>
            </Box>

            <Box sx={{ mb: 2 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ fontWeight: 'medium' }}
              >
                Evaluation Prompt
              </Typography>
              <Paper
                variant="outlined"
                sx={{ p: 2, bgcolor: 'action.hover', mt: 1 }}
              >
                <Typography
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: theme.typography.helperText.fontSize,
                    whiteSpace: 'pre-wrap',
                    color: 'text.primary',
                  }}
                >
                  {formData.evaluation_prompt}
                </Typography>
              </Paper>
            </Box>

            <Box>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ fontWeight: 'medium', mb: 1 }}
              >
                Reasoning Instructions
              </Typography>
              <Paper variant="outlined" sx={{ p: 2, bgcolor: 'action.hover' }}>
                <Typography
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: theme.typography.helperText.fontSize,
                    whiteSpace: 'pre-wrap',
                    color: 'text.primary',
                  }}
                >
                  {formData.reasoning}
                </Typography>
              </Paper>
            </Box>
          </Paper>
        </Box>

        {/* Right Column */}
        <Box>
          {/* Evaluation Steps */}
          <Paper sx={{ p: 3, mb: 3, bgcolor: 'background.default' }}>
            <Typography variant="h6" color="primary" sx={{ mb: 2 }}>
              Evaluation Steps
            </Typography>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {formData.evaluation_steps
                ?.filter(step => step.trim())
                .map((step, index) => (
                  <Paper
                    key={index}
                    variant="outlined"
                    sx={{
                      p: 2,
                      bgcolor: 'background.paper',
                      position: 'relative',
                      pl: 4,
                    }}
                  >
                    <Typography
                      sx={{
                        position: 'absolute',
                        left: 12,
                        top: 12,
                        color: 'primary.main',
                        fontWeight: 'bold',
                        fontSize: theme.typography.helperText.fontSize,
                      }}
                    >
                      {index + 1}
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        color: 'text.primary',
                      }}
                    >
                      {step}
                    </Typography>
                  </Paper>
                ))}
            </Box>
          </Paper>

          {/* Result Configuration */}
          <Paper sx={{ p: 3, bgcolor: 'background.default' }}>
            <Typography variant="h6" color="primary" sx={{ mb: 2 }}>
              Result Configuration
            </Typography>

            <Box sx={{ mb: 2 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ fontWeight: 'medium' }}
              >
                Score Type
              </Typography>
              <Box
                sx={{
                  bgcolor:
                    formData.score_type === 'binary'
                      ? 'primary.main'
                      : 'primary.main',
                  color: 'primary.contrastText',
                  px: 1.5,
                  py: 0.5,
                  borderRadius: theme => theme.shape.borderRadius * 0.25,
                  fontSize: theme.typography.helperText.fontSize,
                  display: 'inline-block',
                  mt: 0.5,
                }}
              >
                {formData.score_type === 'binary'
                  ? 'Binary (Pass/Fail)'
                  : 'Numeric'}
              </Box>
            </Box>

            {formData.score_type === 'numeric' && (
              <>
                <Box sx={{ display: 'flex', gap: 3, mb: 2 }}>
                  <Box>
                    <Typography
                      variant="subtitle2"
                      color="text.secondary"
                      sx={{ fontWeight: 'medium' }}
                    >
                      Min Score
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: theme.typography.subtitle1.fontSize,
                        fontWeight: 500,
                        color: 'text.primary',
                      }}
                    >
                      {formData.min_score}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography
                      variant="subtitle2"
                      color="text.secondary"
                      sx={{ fontWeight: 'medium' }}
                    >
                      Max Score
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: theme.typography.subtitle1.fontSize,
                        fontWeight: 500,
                        color: 'text.primary',
                      }}
                    >
                      {formData.max_score}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography
                      variant="subtitle2"
                      color="text.secondary"
                      sx={{ fontWeight: 'medium' }}
                    >
                      Threshold
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: theme.typography.subtitle1.fontSize,
                        fontWeight: 500,
                        color: 'success.main',
                      }}
                    >
                      ≥ {formData.threshold}
                    </Typography>
                  </Box>
                </Box>
              </>
            )}

            <Box>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ fontWeight: 'medium', mb: 1 }}
              >
                Result Explanation
              </Typography>
              <Paper variant="outlined" sx={{ p: 2, bgcolor: 'action.hover' }}>
                <Typography
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: theme.typography.helperText.fontSize,
                    whiteSpace: 'pre-wrap',
                    color: 'text.primary',
                  }}
                >
                  {formData.explanation}
                </Typography>
              </Paper>
            </Box>
          </Paper>
        </Box>
      </Box>
    </Box>
  );

  const getStepContent = (step: number) => {
    switch (step) {
      case 0:
        return renderMetricInformation();
      case 1:
        return renderConfirmation();
      default:
        return null;
    }
  };

  const getTitle = () => {
    switch (type) {
      case 'grading':
        return 'Create Grading Criteria Metric';
      case 'api-call':
        return 'Create API Call Metric';
      case 'custom-code':
        return 'Create Custom Code Metric';
      case 'custom-prompt':
        return 'Create Custom Prompt Metric';
      case 'framework':
        return 'Create Framework Metric';
      default:
        return 'Create New Metric';
    }
  };

  return (
    <PageContainer
      title={getTitle()}
      breadcrumbs={[
        { title: 'Metrics', path: '/metrics' },
        { title: 'New Metric' },
      ]}
      sx={{ mb: 4 }}
    >
      <Box sx={{ width: '100%' }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            mb: 4,
            mt: 4,
          }}
        >
          <Box sx={{ maxWidth: '600px', width: '100%' }}>
            <Stepper activeStep={activeStep}>
              {steps.map(label => (
                <Step key={label}>
                  <StepLabel>{label}</StepLabel>
                </Step>
              ))}
            </Stepper>
          </Box>
        </Box>

        <Paper sx={{ p: 4 }}>
          <form onSubmit={handleSubmit}>
            {getStepContent(activeStep)}

            <Box sx={{ display: 'flex', gap: 2, mt: 4 }}>
              <Button
                startIcon={<ArrowBackIcon />}
                onClick={
                  activeStep === 0 ? () => router.push('/metrics') : handleBack
                }
                type="button"
                disabled={isCreating}
              >
                {activeStep === 0 ? 'Cancel' : 'Back'}
              </Button>

              {activeStep === steps.length - 1 ? (
                <Button
                  type="submit"
                  variant="contained"
                  color="primary"
                  disabled={isCreating}
                  startIcon={
                    isCreating ? <CircularProgress size={20} /> : undefined
                  }
                >
                  {isCreating ? 'Creating...' : 'Create Metric'}
                </Button>
              ) : (
                <Button variant="contained" onClick={handleNext} type="button">
                  Next
                </Button>
              )}
            </Box>
          </form>
        </Paper>
      </Box>
    </PageContainer>
  );
}
