'use client';

import { useState, useEffect } from 'react';
import { Box, Stack, Paper, Typography, Button, TextField, FormControl, InputLabel, Select, MenuItem, IconButton } from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import AssessmentIcon from '@mui/icons-material/Assessment';
import SettingsIcon from '@mui/icons-material/Settings';
import EditIcon from '@mui/icons-material/Edit';
import CancelIcon from '@mui/icons-material/Cancel';
import CheckIcon from '@mui/icons-material/Check';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import BaseWorkflowSection from '@/components/common/BaseWorkflowSection';
import BaseTag from '@/components/common/BaseTag';
import { PageContainer } from '@toolpad/core/PageContainer';
import { useParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { MetricDetail, ScoreType } from '@/utils/api-client/interfaces/metric';
import { Model } from '@/utils/api-client/interfaces/model';
import { useNotifications } from '@/components/common/NotificationContext';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { UUID } from 'crypto';
import React from 'react';

type EditableSectionType = 'general' | 'evaluation' | 'configuration';

interface EditData {
  name?: string;
  description?: string;
  model_id?: UUID;
  evaluation_prompt?: string;
  evaluation_steps?: string[];
  reasoning?: string;
  score_type?: ScoreType;
  min_score?: number;
  max_score?: number;
  threshold?: number;
  explanation?: string;
}

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default function MetricDetailPage() {
  const params = useParams();
  const identifier = params.identifier as string;
  const { data: session } = useSession();
  const [metric, setMetric] = useState<MetricDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const notifications = useNotifications();
  const [isEditing, setIsEditing] = useState<EditableSectionType | null>(null);
  const [editData, setEditData] = useState<Partial<EditData>>({});
  const [models, setModels] = useState<Model[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      if (!session?.session_token) return;
      
      try {
        const clientFactory = new ApiClientFactory(session.session_token);
        const metricsClient = clientFactory.getMetricsClient();
        
        // Only fetch metric data - model data is included in the response
        const metricData = await metricsClient.getMetric(identifier as UUID);
        
        setMetric(metricData);
        
        // If we need models for editing, fetch them only when entering edit mode
        // For display, we use the model data included in the metric response
      } catch (error) {
        console.error('Error fetching data:', error);
        notifications.show('Failed to load metric details', { severity: 'error' });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [identifier, session?.session_token, notifications]);

  const handleTagsChange = async (newTags: string[]) => {
    if (!session?.session_token || !metric) return;

    try {
      const clientFactory = new ApiClientFactory(session.session_token);
      const metricsClient = clientFactory.getMetricsClient();
      const updatedMetric = await metricsClient.getMetric(metric.id);
      setMetric(updatedMetric);
    } catch (error) {
      console.error('Error refreshing metric:', error);
      notifications.show('Failed to refresh metric data', { severity: 'error' });
    }
  };

  const handleEdit = async (section: EditableSectionType) => {
    setIsEditing(section);
    let sectionData: Partial<EditData> = {};

    if (section === 'general') {
      sectionData = {
        name: metric?.name || '',
        description: metric?.description || ''
      };
    } else if (section === 'evaluation') {
      sectionData = {
        model_id: metric?.model_id,
        evaluation_prompt: metric?.evaluation_prompt || '',
        evaluation_steps: metric?.evaluation_steps?.split('\n---\n') || [''],
        reasoning: metric?.reasoning || ''
      };
      
      // Fetch models only when entering evaluation edit mode (if not already loaded)
      if (models.length === 0 && session?.session_token) {
        try {
          const clientFactory = new ApiClientFactory(session.session_token);
          const modelsClient = clientFactory.getModelsClient();
          const modelsData = await modelsClient.getModels({ limit: 100, skip: 0 });
          setModels(modelsData.data || []);
        } catch (error) {
          console.error('Error fetching models:', error);
          notifications.show('Failed to load models for editing', { severity: 'error' });
        }
      }
    } else if (section === 'configuration') {
      sectionData = {
        score_type: metric?.score_type || 'binary',
        min_score: metric?.min_score,
        max_score: metric?.max_score,
        threshold: metric?.threshold,
        explanation: metric?.explanation || ''
      };
    }

    setEditData(sectionData);
  };

  const handleCancelEdit = () => {
    setIsEditing(null);
    setEditData({});
  };

  const handleConfirmEdit = async () => {
    if (!session?.session_token || !metric) return;

    try {
      const clientFactory = new ApiClientFactory(session.session_token);
      const metricsClient = clientFactory.getMetricsClient();
      
      // Create a copy of editData and prepare it for the API
      const dataToSend: any = { ...editData };
      
      // Handle evaluation steps
      if (Array.isArray(dataToSend.evaluation_steps)) {
        dataToSend.evaluation_steps = dataToSend.evaluation_steps.join('\n---\n');
      }

      // Remove tags from the update data as they're handled separately
      delete dataToSend.tags;
      
      // Remove any undefined or null values
      Object.keys(dataToSend).forEach(key => {
        if (dataToSend[key] === undefined || dataToSend[key] === null) {
          delete dataToSend[key];
        }
      });

      console.log('Sending update data:', dataToSend);
      
      await metricsClient.updateMetric(metric.id, dataToSend);
      const updatedMetric = await metricsClient.getMetric(metric.id);
      setMetric(updatedMetric as MetricDetail);
      setIsEditing(null);
      setEditData({});
      notifications.show('Metric updated successfully', { severity: 'success' });
    } catch (error) {
      console.error('Error updating metric:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to update metric';
      notifications.show(errorMessage, { severity: 'error' });
    }
  };

  // Memoize individual field handlers to prevent recreating them on each render
  const handleNameChange = React.useCallback((event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setEditData(prev => ({ ...prev, name: event.target.value }));
  }, []);

  const handleDescriptionChange = React.useCallback((event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setEditData(prev => ({ ...prev, description: event.target.value }));
  }, []);

  const handleEvaluationPromptChange = React.useCallback((event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setEditData(prev => ({ ...prev, evaluation_prompt: event.target.value }));
  }, []);

  const handleReasoningChange = React.useCallback((event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setEditData(prev => ({ ...prev, reasoning: event.target.value }));
  }, []);

  const handleExplanationChange = React.useCallback((event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setEditData(prev => ({ ...prev, explanation: event.target.value }));
  }, []);

  const handleStepChange = React.useCallback((index: number) => (
    event: React.ChangeEvent<HTMLTextAreaElement>
  ) => {
    setEditData(prev => {
      const newSteps = [...(prev.evaluation_steps || [])];
      newSteps[index] = event.target.value;
      return {
        ...prev,
        evaluation_steps: newSteps
      };
    });
  }, []);

  const addStep = React.useCallback(() => {
    setEditData(prev => ({
      ...prev,
      evaluation_steps: [...(prev.evaluation_steps || []), '']
    }));
  }, []);

  const removeStep = React.useCallback((index: number) => {
    setEditData(prev => {
      const newSteps = [...(prev.evaluation_steps || [])];
      newSteps.splice(index, 1);
      return {
        ...prev,
        evaluation_steps: newSteps
      };
    });
  }, []);

  const EditableSection = ({ 
    title,
    icon,
    section,
    children 
  }: { 
    title: string;
    icon: React.ReactNode;
    section: EditableSectionType;
    children: React.ReactNode;
  }) => (
    <Paper sx={{ p: 3, position: 'relative' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <SectionHeader icon={icon} title={title} />
        {!isEditing && (
          <Button
            startIcon={<EditIcon />}
            onClick={() => handleEdit(section)}
            variant="outlined"
            size="small"
          >
            Edit Section
          </Button>
        )}
      </Box>
      
      {isEditing === section ? (
        <Box>
          <Box sx={{ 
            display: 'flex', 
            flexDirection: 'column', 
            gap: 3,
            p: 2,
            bgcolor: 'action.hover',
            borderRadius: 1,
            mb: 3
          }}>
            {children}
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
            <Button
              variant="outlined"
              color="error"
              startIcon={<CancelIcon />}
              onClick={handleCancelEdit}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={<CheckIcon />}
              onClick={handleConfirmEdit}
            >
              Save Section
            </Button>
          </Box>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {children}
        </Box>
      )}
    </Paper>
  );

  const SectionHeader = ({ icon, title }: { icon: React.ReactNode; title: string }) => (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Box sx={{ color: 'primary.main' }}>{icon}</Box>
      <Typography variant="h6">{title}</Typography>
    </Box>
  );

  const InfoRow = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 'medium' }}>
        {label}
      </Typography>
      {children}
    </Box>
  );

  if (loading) {
    return (
      <PageContainer title="Loading...">
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Typography>Loading metric details...</Typography>
        </Box>
      </PageContainer>
    );
  }

  if (!metric) {
    return (
      <PageContainer title="Error">
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Typography color="error">Failed to load metric details</Typography>
        </Box>
      </PageContainer>
    );
  }

  return (
    <PageContainer title={metric.name} breadcrumbs={[
      { title: 'Metrics', path: '/metrics' },
      { title: metric.name, path: `/metrics/${identifier}` }
    ]}>
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={3}>
        {/* Left side - Main content */}
        <Box sx={{ flex: 1 }}>
          <Stack spacing={3}>
            {/* General Information Section */}
            <EditableSection 
              title="General Information" 
              icon={<InfoIcon />}
              section="general"
            >
              <InfoRow label="Name">
                {isEditing === 'general' ? (
                  <TextField
                    fullWidth
                    required
                    value={editData.name || ''}
                    onChange={handleNameChange}
                    placeholder="Enter metric name"
                  />
                ) : (
                  <Typography>{metric.name}</Typography>
                )}
              </InfoRow>

              <InfoRow label="Description">
                {isEditing === 'general' ? (
                  <TextField
                    fullWidth
                    multiline
                    rows={4}
                    value={editData.description || ''}
                    onChange={handleDescriptionChange}
                    placeholder="Enter metric description"
                  />
                ) : (
                  <Typography>{metric.description || '-'}</Typography>
                )}
              </InfoRow>

              <InfoRow label="Tags">
                <BaseTag
                  value={metric.tags?.map(tag => tag.name) || []}
                  onChange={handleTagsChange}
                  placeholder="Add tags..."
                  chipColor="primary"
                  disableEdition={isEditing !== 'general'}
                  entityType={EntityType.METRIC}
                  entity={metric}
                  sessionToken={session?.session_token}
                />
              </InfoRow>
            </EditableSection>

            {/* Evaluation Process Section */}
            <EditableSection 
              title="Evaluation Process" 
              icon={<AssessmentIcon />}
              section="evaluation"
            >
              <InfoRow label="LLM Judge Model">
                {isEditing === 'evaluation' ? (
                  <FormControl fullWidth>
                    <InputLabel>Model</InputLabel>
                    <Select
                      value={editData.model_id || ''}
                      onChange={(e) => setEditData({ ...editData, model_id: e.target.value as UUID })}
                      label="Model"
                    >
                      {models.map((model) => (
                        <MenuItem key={model.id} value={model.id}>
                          <Box>
                            <Typography variant="subtitle2">
                              {model.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" display="block">
                              {model.description}
                            </Typography>
                          </Box>
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                ) : (
                  <>
                    <Typography>{metric.model?.name || '-'}</Typography>
                    {metric.model?.description && (
                      <Typography variant="body2" color="text.secondary">
                        {metric.model.description}
                      </Typography>
                    )}
                  </>
                )}
              </InfoRow>

              <InfoRow label="Evaluation Prompt">
                {isEditing === 'evaluation' ? (
                  <TextField
                    fullWidth
                    multiline
                    rows={4}
                    value={editData.evaluation_prompt || ''}
                    onChange={handleEvaluationPromptChange}
                    placeholder="Enter evaluation prompt"
                  />
                ) : (
                  <Typography
                    component="pre"
                    variant="body2"
                    sx={{
                      whiteSpace: 'pre-wrap',
                      fontFamily: 'monospace',
                      bgcolor: 'action.hover',
                      borderRadius: 1,
                      padding: 1,
                      minHeight: 'calc(4 * 1.4375em + 2 * 8px)',
                      wordBreak: 'break-word',
                    }}
                  >
                    {metric.evaluation_prompt || '-'}
                  </Typography>
                )}
              </InfoRow>

              <InfoRow label="Evaluation Steps">
                {isEditing === 'evaluation' ? (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {(editData.evaluation_steps || ['']).map((step, index) => (
                      <Box key={index} sx={{ display: 'flex', gap: 1 }}>
                        <TextField
                          fullWidth
                          multiline
                          rows={2}
                          value={step}
                          onChange={handleStepChange(index)}
                          placeholder={`Step ${index + 1}: Describe this evaluation step...`}
                        />
                        <IconButton 
                          onClick={() => removeStep(index)}
                          disabled={(editData.evaluation_steps || []).length === 1}
                          sx={{ mt: 1 }}
                          color="error"
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Box>
                    ))}
                    <Button
                      startIcon={<AddIcon />}
                      onClick={addStep}
                      sx={{ alignSelf: 'flex-start' }}
                    >
                      Add Step
                    </Button>
                  </Box>
                ) : (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {metric.evaluation_steps ? (
                      metric.evaluation_steps.split('\n---\n').map((step, index) => (
                        <Paper 
                          key={index} 
                          variant="outlined" 
                          sx={{ 
                            p: 2,
                            bgcolor: 'background.paper',
                            position: 'relative',
                            pl: 6
                          }}
                        >
                          <Typography
                            sx={{
                              position: 'absolute',
                              left: 16,
                              color: 'primary.main',
                              fontWeight: 'bold'
                            }}
                          >
                            {index + 1}
                          </Typography>
                          <Typography sx={{ whiteSpace: 'pre-wrap' }}>
                            {step.replace(/^Step \d+:\n/, '')}
                          </Typography>
                        </Paper>
                      ))
                    ) : (
                      <Typography>-</Typography>
                    )}
                  </Box>
                )}
              </InfoRow>

              <InfoRow label="Reasoning Instructions">
                {isEditing === 'evaluation' ? (
                  <TextField
                    fullWidth
                    multiline
                    rows={4}
                    value={editData.reasoning || ''}
                    onChange={handleReasoningChange}
                    placeholder="Enter reasoning instructions"
                  />
                ) : (
                  <Typography
                    component="pre"
                    variant="body2"
                    sx={{
                      whiteSpace: 'pre-wrap',
                      fontFamily: 'monospace',
                      bgcolor: 'action.hover',
                      borderRadius: 1,
                      padding: 1,
                      minHeight: 'calc(4 * 1.4375em + 2 * 8px)',
                      wordBreak: 'break-word',
                    }}
                  >
                    {metric.reasoning || '-'}
                  </Typography>
                )}
              </InfoRow>
            </EditableSection>

            {/* Result Configuration Section */}
            <EditableSection 
              title="Result Configuration" 
              icon={<SettingsIcon />}
              section="configuration"
            >
              <InfoRow label="Score Type">
                {isEditing === 'configuration' ? (
                  <FormControl fullWidth>
                    <InputLabel>Score Type</InputLabel>
                    <Select
                      value={editData.score_type || 'binary'}
                      onChange={(e) => setEditData({ ...editData, score_type: e.target.value as ScoreType })}
                      label="Score Type"
                    >
                      <MenuItem value="binary">Binary (Pass/Fail)</MenuItem>
                      <MenuItem value="numeric">Numeric</MenuItem>
                    </Select>
                  </FormControl>
                ) : (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography
                      sx={{
                        bgcolor: 'primary.main',
                        color: 'primary.contrastText',
                        px: 1.5,
                        py: 0.5,
                        borderRadius: 1,
                        fontSize: '0.875rem',
                        fontWeight: 'medium'
                      }}
                    >
                      {metric.score_type === 'binary' ? 'Binary (Pass/Fail)' : 'Numeric'}
                    </Typography>
                  </Box>
                )}
              </InfoRow>

              {(metric.score_type === 'numeric' || editData.score_type === 'numeric') && (
                <>
                  <Box sx={{ display: 'flex', gap: 4 }}>
                    <InfoRow label="Minimum Score">
                      {isEditing === 'configuration' ? (
                        <TextField
                          type="number"
                          value={editData.min_score || ''}
                          onChange={(e) => setEditData({ ...editData, min_score: Number(e.target.value) })}
                          fullWidth
                          placeholder="Enter minimum score"
                        />
                      ) : (
                        <Typography variant="h6" color="text.secondary">
                          {metric.min_score}
                        </Typography>
                      )}
                    </InfoRow>

                    <InfoRow label="Maximum Score">
                      {isEditing === 'configuration' ? (
                        <TextField
                          type="number"
                          value={editData.max_score || ''}
                          onChange={(e) => setEditData({ ...editData, max_score: Number(e.target.value) })}
                          fullWidth
                          placeholder="Enter maximum score"
                        />
                      ) : (
                        <Typography variant="h6" color="text.secondary">
                          {metric.max_score}
                        </Typography>
                      )}
                    </InfoRow>
                  </Box>

                  <InfoRow label="Threshold">
                    {isEditing === 'configuration' ? (
                      <TextField
                        type="number"
                        value={editData.threshold || ''}
                        onChange={(e) => setEditData({ ...editData, threshold: Number(e.target.value) })}
                        fullWidth
                        placeholder="Enter threshold score"
                        helperText="Minimum score required to pass"
                      />
                    ) : (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Typography
                          sx={{
                            bgcolor: 'success.main',
                            color: 'success.contrastText',
                            px: 2,
                            py: 0.5,
                            borderRadius: 1,
                            fontSize: '0.875rem',
                            fontWeight: 'medium'
                          }}
                        >
                          ≥ {metric.threshold}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Minimum score required to pass
                        </Typography>
                      </Box>
                    )}
                  </InfoRow>
                </>
              )}

              <InfoRow label="Result Explanation">
                {isEditing === 'configuration' ? (
                  <TextField
                    fullWidth
                    multiline
                    rows={4}
                    value={editData.explanation || ''}
                    onChange={handleExplanationChange}
                    placeholder="Enter result explanation"
                  />
                ) : (
                  <Typography
                    component="pre"
                    variant="body2"
                    sx={{
                      whiteSpace: 'pre-wrap',
                      fontFamily: 'monospace',
                      bgcolor: 'action.hover',
                      borderRadius: 1,
                      padding: 1,
                      minHeight: 'calc(4 * 1.4375em + 2 * 8px)',
                      wordBreak: 'break-word',
                    }}
                  >
                    {metric.explanation || '-'}
                  </Typography>
                )}
              </InfoRow>
            </EditableSection>
          </Stack>
        </Box>

        {/* Right side - Workflow */}
        <Box sx={{ width: { xs: '100%', md: '400px' }, flexShrink: 0 }}>
          <Paper sx={{ p: 3 }}>
            <BaseWorkflowSection
              title="Workflow"
              entityId={identifier}
              entityType="Metric"
              status={metric.status?.name}
              assignee={metric.assignee}
              owner={metric.owner}
              clientFactory={session?.session_token ? new ApiClientFactory(session.session_token) : undefined}
              showPriority={false}

              onUpdateEntity={async (updateData, fieldName) => {
                if (!session?.session_token) return;
                
                try {
                  const clientFactory = new ApiClientFactory(session.session_token);
                  const metricsClient = clientFactory.getMetricsClient();
                  await metricsClient.updateMetric(identifier as UUID, updateData);
                  
                  // Refresh metric data after successful update
                  const updatedMetric = await metricsClient.getMetric(identifier as UUID);
                  setMetric(updatedMetric);
                  
                  notifications.show(`${fieldName} updated successfully`, { severity: 'success' });
                } catch (error) {
                  console.error('Error updating metric:', error);
                  notifications.show(`Failed to update ${fieldName}`, { severity: 'error' });
                  throw error; // Re-throw to let BaseWorkflowSection handle the error
                }
              }}
            />
          </Paper>
        </Box>
      </Stack>
    </PageContainer>
  );
} 