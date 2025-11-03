'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useTheme } from '@mui/material/styles';
import {
  Box,
  Stack,
  Paper,
  Typography,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import AssessmentIcon from '@mui/icons-material/Assessment';
import SettingsIcon from '@mui/icons-material/Settings';
import EditIcon from '@mui/icons-material/Edit';
import CancelIcon from '@mui/icons-material/Cancel';
import CheckIcon from '@mui/icons-material/Check';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
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
import { Status } from '@/utils/api-client/interfaces/status';
import { User } from '@/utils/api-client/interfaces/user';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

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

interface StepWithId {
  id: string;
  content: string;
}

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default function MetricDetailPage() {
  const params = useParams();
  const identifier = params.identifier as string;
  const { data: session } = useSession();
  const theme = useTheme();
  const [metric, setMetric] = useState<MetricDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const notifications = useNotifications();
  const [isEditing, setIsEditing] = useState<EditableSectionType | null>(null);
  const [editData, setEditData] = useState<Partial<EditData>>({});
  const [models, setModels] = useState<Model[]>([]);
  const [stepsWithIds, setStepsWithIds] = useState<StepWithId[]>([]);
  const [statuses, setStatuses] = useState<Status[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const dataFetchedRef = useRef(false);

  // Set document title dynamically
  useDocumentTitle(metric?.name || null);

  // Refs for uncontrolled text fields
  const nameRef = useRef<HTMLInputElement>(null);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);
  const evaluationPromptRef = useRef<HTMLTextAreaElement>(null);
  const reasoningRef = useRef<HTMLTextAreaElement>(null);
  const explanationRef = useRef<HTMLTextAreaElement>(null);
  const stepRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map());

  useEffect(() => {
    const fetchData = async () => {
      if (!session?.session_token || dataFetchedRef.current) return;

      dataFetchedRef.current = true;

      try {
        const clientFactory = new ApiClientFactory(session.session_token);
        const metricsClient = clientFactory.getMetricsClient();
        const statusClient = clientFactory.getStatusClient();
        const usersClient = clientFactory.getUsersClient();

        // Fetch all data in parallel
        const [metricData, statusesData, usersData] = await Promise.all([
          metricsClient.getMetric(identifier as UUID),
          statusClient.getStatuses({
            entity_type: 'Metric',
            sort_by: 'name',
            sort_order: 'asc',
          }),
          usersClient.getUsers({ limit: 100 }),
        ]);

        setMetric(metricData);
        setStatuses(statusesData || []);
        setUsers(usersData.data || []);

        // Model data is already included in the metric response
        if (metricData.model) {
          setModels([metricData.model]);
        }
      } catch (error) {
        // Use notifications without depending on it
        const notificationsContext = notifications;
        notificationsContext.show('Failed to load metric details', {
          severity: 'error',
        });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [identifier, session?.session_token, notifications]);

  // Helper function to collect current field values without triggering re-renders
  const collectFieldValues = React.useCallback((): Partial<EditData> => {
    const values: Partial<EditData> = {};

    if (nameRef.current) values.name = nameRef.current.value;
    if (descriptionRef.current)
      values.description = descriptionRef.current.value;
    if (evaluationPromptRef.current)
      values.evaluation_prompt = evaluationPromptRef.current.value;
    if (reasoningRef.current) values.reasoning = reasoningRef.current.value;
    if (explanationRef.current)
      values.explanation = explanationRef.current.value;

    // Collect step values
    const stepValues: string[] = [];
    stepsWithIds.forEach(step => {
      const stepElement = stepRefs.current.get(step.id);
      if (stepElement) {
        stepValues.push(stepElement.value);
      }
    });
    if (stepValues.length > 0) {
      values.evaluation_steps = stepValues;
    }

    return values;
  }, [stepsWithIds]);

  // Helper function to populate refs with initial values when entering edit mode
  const populateFieldRefs = React.useCallback(
    (section: EditableSectionType, currentMetric: MetricDetail) => {
      if (section === 'general') {
        if (nameRef.current) nameRef.current.value = currentMetric.name || '';
        if (descriptionRef.current)
          descriptionRef.current.value = currentMetric.description || '';
      } else if (section === 'evaluation') {
        if (evaluationPromptRef.current)
          evaluationPromptRef.current.value =
            currentMetric.evaluation_prompt || '';
        if (reasoningRef.current)
          reasoningRef.current.value = currentMetric.reasoning || '';

        // Populate step refs
        const steps = currentMetric.evaluation_steps?.split('\n---\n') || [''];
        const stepsWithIds = steps.map((step, index) => {
          // Remove the "Step X:" prefix if it exists
          const cleanedStep = step.replace(/^Step \d+:\n?/, '').trim();
          return {
            id: `step-${Date.now()}-${index}`,
            content: cleanedStep,
          };
        });
        setStepsWithIds(stepsWithIds);

        // Populate step refs after a brief delay to ensure DOM elements exist
        setTimeout(() => {
          stepsWithIds.forEach(step => {
            const stepElement = stepRefs.current.get(step.id);
            if (stepElement) {
              stepElement.value = step.content;
            }
          });
        }, 0);
      } else if (section === 'configuration') {
        if (explanationRef.current)
          explanationRef.current.value = currentMetric.explanation || '';
      }
    },
    []
  );

  const handleTagsChange = React.useCallback(
    async (newTags: string[]) => {
      if (!session?.session_token) return;

      // Use functional state update to avoid depending on metric
      setMetric(currentMetric => {
        if (!currentMetric) return currentMetric;

        (async () => {
          try {
            const clientFactory = new ApiClientFactory(session.session_token!);
            const metricsClient = clientFactory.getMetricsClient();
            const updatedMetric = await metricsClient.getMetric(
              currentMetric.id
            );
            setMetric(updatedMetric);
          } catch (error) {
            notifications.show('Failed to refresh metric data', {
              severity: 'error',
            });
          }
        })();

        return currentMetric;
      });
    },
    [session?.session_token, notifications]
  );

  const handleEdit = React.useCallback(
    async (section: EditableSectionType) => {
      if (!metric) return;

      setIsEditing(section);

      // Populate refs with initial values (no re-renders)
      populateFieldRefs(section, metric);

      // Only set editData for select fields (model, score_type, etc.)
      let sectionData: Partial<EditData> = {};

      if (section === 'evaluation') {
        sectionData = {
          model_id: metric.model_id,
        };

        // For editing, we need all available models, not just the current one
        setModels(currentModels => {
          if (currentModels.length <= 1 && session?.session_token) {
            // Fetch models asynchronously without blocking
            (async () => {
              try {
                const clientFactory = new ApiClientFactory(
                  session.session_token!
                );
                const modelsClient = clientFactory.getModelsClient();
                const modelsData = await modelsClient.getModels({
                  limit: 100,
                  skip: 0,
                });
                setModels(modelsData.data || []);
              } catch (error) {
                notifications.show('Failed to load models for editing', {
                  severity: 'error',
                });
              }
            })();
          }
          return currentModels;
        });
      } else if (section === 'configuration') {
        sectionData = {
          score_type: metric.score_type || 'numeric',
          min_score: metric.min_score,
          max_score: metric.max_score,
          threshold: metric.threshold,
        };
      }

      setEditData(sectionData);
    },
    [metric, session?.session_token, populateFieldRefs, notifications]
  );

  const handleCancelEdit = React.useCallback(() => {
    setIsEditing(null);
    setEditData({});
    setStepsWithIds([]);
    // Clear step refs
    stepRefs.current.clear();
  }, []);

  const handleConfirmEdit = React.useCallback(async () => {
    if (!session?.session_token || !metric) return;

    setIsSaving(true);
    try {
      // Collect current field values without triggering re-renders
      const fieldValues = collectFieldValues();

      // Also collect select field values from editData
      const dataToSend: any = {
        ...fieldValues,
        ...(editData.model_id && { model_id: editData.model_id }),
        ...(editData.score_type && { score_type: editData.score_type }),
        ...(editData.min_score !== undefined && {
          min_score: editData.min_score,
        }),
        ...(editData.max_score !== undefined && {
          max_score: editData.max_score,
        }),
        ...(editData.threshold !== undefined && {
          threshold: editData.threshold,
        }),
      };

      // Handle evaluation steps
      if (Array.isArray(dataToSend.evaluation_steps)) {
        dataToSend.evaluation_steps = dataToSend.evaluation_steps
          .map((step: string, index: number) => `Step ${index + 1}:\n${step}`)
          .join('\n---\n');
      }

      // Remove tags from the update data as they're handled separately
      delete dataToSend.tags;

      // Remove any undefined or null values
      Object.keys(dataToSend).forEach(key => {
        if (dataToSend[key] === undefined || dataToSend[key] === null) {
          delete dataToSend[key];
        }
      });

      const clientFactory = new ApiClientFactory(session.session_token);
      const metricsClient = clientFactory.getMetricsClient();
      await metricsClient.updateMetric(metric.id, dataToSend);
      const updatedMetric = await metricsClient.getMetric(metric.id);
      setMetric(updatedMetric as MetricDetail);
      setIsEditing(null);
      setEditData({});
      setStepsWithIds([]);

      notifications.show('Metric updated successfully', {
        severity: 'success',
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to update metric';
      notifications.show(errorMessage, { severity: 'error' });
    } finally {
      setIsSaving(false);
    }
  }, [
    session?.session_token,
    metric,
    collectFieldValues,
    editData,
    notifications,
  ]);

  const addStep = React.useCallback(() => {
    setStepsWithIds(prev => {
      const newStep = { id: `step-${Date.now()}-${prev.length}`, content: '' };
      return [...prev, newStep];
    });
  }, []);

  const removeStep = React.useCallback((stepId: string) => {
    setStepsWithIds(prev => prev.filter(step => step.id !== stepId));
    // Clean up the ref for the removed step
    stepRefs.current.delete(stepId);
  }, []);

  // Move EditableSection completely outside the main component
  const EditableSection = React.memo(
    ({
      title,
      icon,
      section,
      children,
      isEditing,
      onEdit,
      onCancel,
      onConfirm,
      isSaving,
    }: {
      title: string;
      icon: React.ReactNode;
      section: EditableSectionType;
      children: React.ReactNode;
      isEditing: EditableSectionType | null;
      onEdit: (section: EditableSectionType) => void;
      onCancel: () => void;
      onConfirm: () => void;
      isSaving?: boolean;
    }) => {
      return (
        <Paper
          sx={{
            p: theme.spacing(3),
            position: 'relative',
            borderRadius: theme.shape.borderRadius,
            bgcolor: theme.palette.background.paper,
            boxShadow: theme.shadows[1],
          }}
        >
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: theme.spacing(3),
              pb: theme.spacing(2),
              borderBottom: `1px solid ${theme.palette.divider}`,
            }}
          >
            <SectionHeader icon={icon} title={title} />
            {!isEditing && (
              <Button
                startIcon={<EditIcon />}
                onClick={() => onEdit(section)}
                variant="outlined"
                size="small"
                sx={{
                  color: theme.palette.primary.main,
                  borderColor: theme.palette.primary.main,
                  '&:hover': {
                    backgroundColor: theme.palette.primary.light,
                    borderColor: theme.palette.primary.main,
                  },
                }}
              >
                Edit Section
              </Button>
            )}
          </Box>

          {isEditing === section ? (
            <Box>
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: theme.spacing(3),
                  p: theme.spacing(2),
                  bgcolor: theme.palette.action.hover,
                  borderRadius: theme.shape.borderRadius,
                  mb: theme.spacing(3),
                  border: `1px solid ${theme.palette.divider}`,
                }}
              >
                {children}
              </Box>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: theme.spacing(1),
                  mt: theme.spacing(2),
                }}
              >
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<CancelIcon />}
                  onClick={onCancel}
                  disabled={isSaving}
                  sx={{
                    borderColor: theme.palette.error.main,
                    '&:hover': {
                      backgroundColor: theme.palette.error.light,
                      borderColor: theme.palette.error.main,
                    },
                  }}
                >
                  Cancel
                </Button>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<CheckIcon />}
                  onClick={onConfirm}
                  disabled={isSaving}
                  sx={{
                    bgcolor: theme.palette.primary.main,
                    '&:hover': {
                      bgcolor: theme.palette.primary.dark,
                    },
                  }}
                >
                  {isSaving ? 'Saving...' : 'Save Section'}
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
    }
  );

  EditableSection.displayName = 'EditableSection';

  const SectionHeader = React.memo(
    ({ icon, title }: { icon: React.ReactNode; title: string }) => {
      const theme = useTheme();
      return (
        <Box
          sx={{ display: 'flex', alignItems: 'center', gap: theme.spacing(1) }}
        >
          <Box
            sx={{
              color: theme.palette.primary.main,
              display: 'flex',
              alignItems: 'center',
              '& > svg': {
                fontSize: theme.typography.h6.fontSize,
              },
            }}
          >
            {icon}
          </Box>
          <Typography
            variant="h6"
            sx={{
              fontWeight: theme.typography.fontWeightMedium,
              color: theme.palette.text.primary,
            }}
          >
            {title}
          </Typography>
        </Box>
      );
    }
  );

  SectionHeader.displayName = 'SectionHeader';

  const InfoRow = React.memo(
    ({ label, children }: { label: string; children: React.ReactNode }) => {
      const theme = useTheme();
      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: theme.spacing(1),
            py: theme.spacing(1),
          }}
        >
          <Typography
            variant="subtitle2"
            sx={{
              color: theme.palette.text.secondary,
              fontWeight: theme.typography.fontWeightMedium,
              letterSpacing: '0.02em',
            }}
          >
            {label}
          </Typography>
          <Box
            sx={{
              '& .MuiTypography-root': {
                color: theme.palette.text.primary,
              },
            }}
          >
            {children}
          </Box>
        </Box>
      );
    }
  );

  InfoRow.displayName = 'InfoRow';

  // Memoize icons to prevent recreation
  const infoIcon = <InfoIcon />;
  const assessmentIcon = <AssessmentIcon />;
  const settingsIcon = <SettingsIcon />;

  if (loading) {
    return (
      <PageContainer title="Loading...">
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%',
          }}
        >
          <Typography>Loading metric details...</Typography>
        </Box>
      </PageContainer>
    );
  }

  if (!metric) {
    return (
      <PageContainer title="Error">
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%',
          }}
        >
          <Typography color="error">Failed to load metric details</Typography>
        </Box>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={metric.name}
      breadcrumbs={[
        { title: 'Metrics', path: '/metrics' },
        { title: metric.name, path: `/metrics/${identifier}` },
      ]}
    >
      {/* Memoize the entire content to prevent unnecessary re-renders */}
      <Stack direction="column" spacing={3}>
        {/* Main content */}
        <Box sx={{ flex: 1 }}>
          <Stack spacing={3}>
            {/* General Information Section */}
            <EditableSection
              title="General Information"
              icon={infoIcon}
              section="general"
              isEditing={isEditing}
              onEdit={handleEdit}
              onCancel={handleCancelEdit}
              onConfirm={handleConfirmEdit}
              isSaving={isSaving}
            >
              <InfoRow label="Name">
                {isEditing === 'general' ? (
                  <TextField
                    key={`name-field-${metric.id}`}
                    fullWidth
                    required
                    inputRef={nameRef}
                    defaultValue={metric.name || ''}
                    placeholder="Enter metric name"
                  />
                ) : (
                  <Typography>{metric.name}</Typography>
                )}
              </InfoRow>

              <InfoRow label="Description">
                {isEditing === 'general' ? (
                  <TextField
                    key={`description-field-${metric.id}`}
                    fullWidth
                    multiline
                    rows={4}
                    inputRef={descriptionRef}
                    defaultValue={metric.description || ''}
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
              icon={assessmentIcon}
              section="evaluation"
              isEditing={isEditing}
              onEdit={handleEdit}
              onCancel={handleCancelEdit}
              onConfirm={handleConfirmEdit}
              isSaving={isSaving}
            >
              <InfoRow label="LLM Judge Model">
                {isEditing === 'evaluation' ? (
                  <FormControl fullWidth>
                    <InputLabel>Model</InputLabel>
                    <Select
                      value={editData.model_id || ''}
                      onChange={e =>
                        setEditData(prev => ({
                          ...prev,
                          model_id: e.target.value as UUID,
                        }))
                      }
                      label="Model"
                    >
                      {models.map(model => (
                        <MenuItem key={model.id} value={model.id}>
                          <Box>
                            <Typography variant="subtitle2">
                              {model.name}
                            </Typography>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              display="block"
                            >
                              {model.description}
                            </Typography>
                          </Box>
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                ) : (
                  <>
                    <Typography>
                      {models.length > 0
                        ? models.find(model => model.id === metric.model_id)
                            ?.name || '-'
                        : metric.model_id
                          ? 'Loading model...'
                          : '-'}
                    </Typography>
                    {models.length > 0 && metric.model_id && (
                      <Typography variant="body2" color="text.secondary">
                        {models.find(model => model.id === metric.model_id)
                          ?.description || ''}
                      </Typography>
                    )}
                  </>
                )}
              </InfoRow>

              <InfoRow label="Evaluation Prompt">
                {isEditing === 'evaluation' ? (
                  <TextField
                    key={`evaluation-prompt-field-${metric.id}`}
                    fullWidth
                    multiline
                    rows={4}
                    inputRef={evaluationPromptRef}
                    defaultValue={metric.evaluation_prompt || ''}
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
                      borderRadius: theme => theme.shape.borderRadius * 0.25,
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
                  <Box
                    sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
                  >
                    {stepsWithIds.map((step, index) => (
                      <Box key={step.id} sx={{ display: 'flex', gap: 1 }}>
                        <TextField
                          fullWidth
                          multiline
                          rows={2}
                          inputRef={el => {
                            if (el) {
                              stepRefs.current.set(step.id, el);
                            }
                          }}
                          defaultValue={step.content}
                          placeholder={`Step ${index + 1}: Describe this evaluation step...`}
                        />
                        <IconButton
                          onClick={() => removeStep(step.id)}
                          disabled={stepsWithIds.length === 1}
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
                  <Box
                    sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
                  >
                    {metric.evaluation_steps ? (
                      metric.evaluation_steps
                        .split('\n---\n')
                        .map((step, index) => (
                          <Paper
                            key={index}
                            variant="outlined"
                            sx={{
                              p: 2,
                              bgcolor: 'background.paper',
                              position: 'relative',
                              pl: 6,
                            }}
                          >
                            <Typography
                              sx={{
                                position: 'absolute',
                                left: 16,
                                color: 'primary.main',
                                fontWeight: 'bold',
                              }}
                            >
                              {index + 1}
                            </Typography>
                            <Typography sx={{ whiteSpace: 'pre-wrap' }}>
                              {step.replace(/^Step \d+:\n?/, '').trim()}
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
                    key={`reasoning-field-${metric.id}`}
                    fullWidth
                    multiline
                    rows={4}
                    inputRef={reasoningRef}
                    defaultValue={metric.reasoning || ''}
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
                      borderRadius: theme => theme.shape.borderRadius * 0.25,
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
              icon={settingsIcon}
              section="configuration"
              isEditing={isEditing}
              onEdit={handleEdit}
              onCancel={handleCancelEdit}
              onConfirm={handleConfirmEdit}
              isSaving={isSaving}
            >
              <InfoRow label="Score Type">
                {isEditing === 'configuration' ? (
                  <FormControl fullWidth>
                    <InputLabel>Score Type</InputLabel>
                    <Select
                      value={editData.score_type || 'numeric'}
                      onChange={e =>
                        setEditData(prev => ({
                          ...prev,
                          score_type: e.target.value as ScoreType,
                        }))
                      }
                      label="Score Type"
                    >
                      <MenuItem value="numeric">Numeric</MenuItem>
                      <MenuItem value="categorical">Categorical</MenuItem>
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
                        borderRadius: theme => theme.shape.borderRadius * 0.25,
                        fontSize:
                          theme?.typography?.helperText?.fontSize || '0.75rem',
                        fontWeight: 'medium',
                      }}
                    >
                      {metric.score_type === 'categorical'
                        ? 'Categorical'
                        : 'Numeric'}
                    </Typography>
                  </Box>
                )}
              </InfoRow>

              {(metric.score_type === 'numeric' ||
                editData.score_type === 'numeric') && (
                <>
                  <Box sx={{ display: 'flex', gap: 4 }}>
                    <InfoRow label="Minimum Score">
                      {isEditing === 'configuration' ? (
                        <TextField
                          key={`min-score-field-${metric.id}`}
                          type="number"
                          value={editData.min_score || ''}
                          onChange={e =>
                            setEditData(prev => ({
                              ...prev,
                              min_score: Number(e.target.value),
                            }))
                          }
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
                          key={`max-score-field-${metric.id}`}
                          type="number"
                          value={editData.max_score || ''}
                          onChange={e =>
                            setEditData(prev => ({
                              ...prev,
                              max_score: Number(e.target.value),
                            }))
                          }
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
                        key={`threshold-field-${metric.id}`}
                        type="number"
                        value={editData.threshold || ''}
                        onChange={e =>
                          setEditData(prev => ({
                            ...prev,
                            threshold: Number(e.target.value),
                          }))
                        }
                        fullWidth
                        placeholder="Enter threshold score"
                        helperText="Minimum score required to pass"
                      />
                    ) : (
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 2 }}
                      >
                        <Typography
                          sx={{
                            bgcolor: 'success.main',
                            color: 'success.contrastText',
                            px: 2,
                            py: 0.5,
                            borderRadius: theme =>
                              theme.shape.borderRadius * 0.25,
                            fontSize:
                              theme?.typography?.helperText?.fontSize ||
                              '0.75rem',
                            fontWeight: 'medium',
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
                    key={`explanation-field-${metric.id}`}
                    fullWidth
                    multiline
                    rows={4}
                    inputRef={explanationRef}
                    defaultValue={metric.explanation || ''}
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
                      borderRadius: theme => theme.shape.borderRadius * 0.25,
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
      </Stack>
    </PageContainer>
  );
}
