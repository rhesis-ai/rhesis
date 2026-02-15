'use client';

import React, { useState, useEffect, useRef } from 'react';
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
  Chip,
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
import { useParams, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  MetricDetail,
  ScoreType,
  MetricScope,
  ThresholdOperator,
} from '@/utils/api-client/interfaces/metric';
import { Model } from '@/utils/api-client/interfaces/model';
import { useNotifications } from '@/components/common/NotificationContext';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { UUID } from 'crypto';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

type EditableSectionType = 'general' | 'evaluation' | 'configuration';

interface EditData {
  name?: string;
  description?: string;
  tags?: string[];
  model_id?: UUID;
  evaluation_prompt?: string;
  evaluation_steps?: string[];
  reasoning?: string;
  score_type?: ScoreType;
  categories?: string[];
  passing_categories?: string[];
  min_score?: number;
  max_score?: number;
  threshold?: number;
  threshold_operator?: ThresholdOperator;
  explanation?: string;
  metric_scope?: MetricScope[];
}

interface StepWithId {
  id: string;
  content: string;
}

export default function MetricDetailPage() {
  const params = useParams();
  const identifier = params.identifier as string;
  const { data: session } = useSession();
  const theme = useTheme();
  const router = useRouter();
  const [metric, setMetric] = useState<MetricDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const notifications = useNotifications();
  const [isEditing, setIsEditing] = useState<EditableSectionType | null>(null);
  const [editData, setEditData] = useState<Partial<EditData>>({});
  const [models, setModels] = useState<Model[]>([]);
  const [stepsWithIds, setStepsWithIds] = useState<StepWithId[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const dataFetchedRef = useRef(false);
  const [textFieldsTouched, setTextFieldsTouched] = useState(false);

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

        // Fetch metric data
        const metricData = await metricsClient.getMetric(identifier as UUID);

        setMetric(metricData);

        // Model data is already included in the metric response
        if (metricData.model) {
          setModels([metricData.model]);
        }

        // Check if this is NOT a rhesis or custom metric - redirect other metrics
        const backendType = metricData.backend_type?.type_value?.toLowerCase();
        if (backendType !== 'rhesis' && backendType !== 'custom') {
          notifications.show(
            'This metric type cannot be viewed through the detail page',
            {
              severity: 'warning',
            }
          );
          router.push('/metrics');
          return;
        }
      } catch (_error) {
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
  }, [identifier, session?.session_token, notifications, router]);

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

  const checkForChanges = React.useCallback((): boolean => {
    if (!metric || !isEditing) return false;

    if (textFieldsTouched) {
      const fieldValues = collectFieldValues();

      if (isEditing === 'general') {
        if (
          fieldValues.name?.trim() !== (metric.name || '').trim() ||
          fieldValues.description?.trim() !== (metric.description || '').trim()
        ) {
          return true;
        }
      } else if (isEditing === 'evaluation') {
        if (
          fieldValues.evaluation_prompt?.trim() !==
            (metric.evaluation_prompt || '').trim() ||
          fieldValues.reasoning?.trim() !== (metric.reasoning || '').trim()
        ) {
          return true;
        }

        const currentSteps = fieldValues.evaluation_steps || [];
        const originalSteps = metric.evaluation_steps
          ?.split('\n---\n')
          .map(step => step.replace(/^Step \d+:\n?/, '').trim()) || [''];

        if (currentSteps.length !== originalSteps.length) {
          return true;
        }

        for (let i = 0; i < currentSteps.length; i++) {
          if (currentSteps[i].trim() !== originalSteps[i].trim()) {
            return true;
          }
        }
      } else if (isEditing === 'configuration') {
        if (
          fieldValues.explanation?.trim() !== (metric.explanation || '').trim()
        ) {
          return true;
        }
      }
    }

    if (isEditing === 'general') {
      const currentTags = editData.tags || [];
      const originalTags = metric.tags?.map(tag => tag.name) || [];
      if (
        currentTags.length !== originalTags.length ||
        !currentTags.every(tag => originalTags.includes(tag))
      ) {
        return true;
      }
    } else if (isEditing === 'evaluation') {
      if (editData.model_id && editData.model_id !== metric.model_id) {
        return true;
      }
    } else if (isEditing === 'configuration') {
      if (editData.score_type && editData.score_type !== metric.score_type) {
        return true;
      }

      const currentCategories = editData.categories || metric.categories || [];
      const originalCategories = metric.categories || [];
      if (
        currentCategories.length !== originalCategories.length ||
        !currentCategories.every(cat => originalCategories.includes(cat))
      ) {
        return true;
      }

      const currentPassingCategories =
        editData.passing_categories || metric.passing_categories || [];
      const originalPassingCategories = metric.passing_categories || [];
      if (
        currentPassingCategories.length !== originalPassingCategories.length ||
        !currentPassingCategories.every(cat =>
          originalPassingCategories.includes(cat)
        )
      ) {
        return true;
      }

      if (
        editData.min_score !== undefined &&
        editData.min_score !== metric.min_score
      ) {
        return true;
      }
      if (
        editData.max_score !== undefined &&
        editData.max_score !== metric.max_score
      ) {
        return true;
      }
      if (
        editData.threshold !== undefined &&
        editData.threshold !== metric.threshold
      ) {
        return true;
      }
      if (
        editData.threshold_operator &&
        editData.threshold_operator !== metric.threshold_operator
      ) {
        return true;
      }

      const currentScope = editData.metric_scope || metric.metric_scope || [];
      const originalScope = metric.metric_scope || [];
      if (
        currentScope.length !== originalScope.length ||
        !currentScope.every(scope => originalScope.includes(scope))
      ) {
        return true;
      }
    }

    return false;
  }, [metric, isEditing, textFieldsTouched, editData, collectFieldValues]);

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

  // Memoize the tag names to prevent unnecessary re-renders in BaseTag
  const tagNames = React.useMemo(
    () => metric?.tags?.map(tag => tag.name) || [],
    [metric?.tags]
  );

  const handleEdit = React.useCallback(
    async (section: EditableSectionType) => {
      if (!metric) return;

      setIsEditing(section);
      setTextFieldsTouched(false);

      populateFieldRefs(section, metric);

      // Only set editData for select fields (model, score_type, etc.)
      let sectionData: Partial<EditData> = {};

      if (section === 'general') {
        sectionData = {
          tags: tagNames,
        };
      } else if (section === 'evaluation') {
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
                  session.session_token as string
                );
                const modelsClient = clientFactory.getModelsClient();
                const modelsData = await modelsClient.getModels({
                  limit: 100,
                  skip: 0,
                });
                setModels(modelsData.data || []);
              } catch (_error) {
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
          categories: metric.categories || [],
          passing_categories: metric.passing_categories || [],
          min_score: metric.min_score,
          max_score: metric.max_score,
          threshold: metric.threshold,
          threshold_operator: metric.threshold_operator || '>=',
        };
      }

      setEditData(sectionData);
    },
    [metric, session?.session_token, populateFieldRefs, notifications, tagNames]
  );

  const handleCancelEdit = React.useCallback(() => {
    setIsEditing(null);
    setEditData({});
    setStepsWithIds([]);
    setTextFieldsTouched(false);
    // Clear step refs
    stepRefs.current.clear();
  }, []);

  const handleConfirmEdit = React.useCallback(async () => {
    if (!session?.session_token || !metric) return;

    // Validate metric scope - at least one must be selected
    const currentMetricScope =
      editData.metric_scope || metric.metric_scope || [];
    if (currentMetricScope.length === 0) {
      notifications.show(
        'Please select at least one metric scope (Single-Turn or Multi-Turn)',
        {
          severity: 'error',
          autoHideDuration: 4000,
        }
      );
      return;
    }

    // Validate categorical metric fields
    const currentScoreType = editData.score_type || metric.score_type;
    if (currentScoreType === 'categorical') {
      const categories = editData.categories || metric.categories || [];
      const passingCategories =
        editData.passing_categories || metric.passing_categories || [];

      if (categories.length < 2) {
        notifications.show(
          'Please add at least 2 categories for categorical metrics',
          { severity: 'error', autoHideDuration: 4000 }
        );
        return;
      }
      if (passingCategories.length === 0) {
        notifications.show('Please select at least one passing category', {
          severity: 'error',
          autoHideDuration: 4000,
        });
        return;
      }
    }

    setIsSaving(true);
    try {
      // Collect current field values without triggering re-renders
      const fieldValues = collectFieldValues();

      // Also collect select field values from editData
      const dataToSend: Record<string, unknown> = {
        ...fieldValues,
        ...(editData.model_id && { model_id: editData.model_id }),
        ...(editData.score_type && { score_type: editData.score_type }),
        ...(editData.categories && { categories: editData.categories }),
        ...(editData.passing_categories && {
          passing_categories: editData.passing_categories,
        }),
        ...(editData.min_score !== undefined && {
          min_score: editData.min_score,
        }),
        ...(editData.max_score !== undefined && {
          max_score: editData.max_score,
        }),
        ...(editData.threshold !== undefined && {
          threshold: editData.threshold,
        }),
        ...(editData.threshold_operator && {
          threshold_operator: editData.threshold_operator,
        }),
        ...(editData.metric_scope && { metric_scope: editData.metric_scope }),
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

      // Handle tag updates separately if tags changed in general section
      if (isEditing === 'general' && editData.tags) {
        const tagsClient = clientFactory.getTagsClient();
        const currentTagNames = tagNames;
        const newTagNames = editData.tags;

        // Get current tag objects
        const currentTagObjects = metric.tags || [];
        const currentTagMap = new Map(
          currentTagObjects.map(tag => [tag.name, tag])
        );

        // Tags to remove
        const tagsToRemove = currentTagNames.filter(
          tagName => !newTagNames.includes(tagName)
        );

        // Tags to add
        const tagsToAdd = newTagNames.filter(
          tagName => !currentTagNames.includes(tagName)
        );

        // Remove tags
        for (const tagName of tagsToRemove) {
          const tag = currentTagMap.get(tagName);
          if (tag) {
            await tagsClient.removeTagFromEntity(
              EntityType.METRIC,
              metric.id,
              tag.id
            );
          }
        }

        // Add new tags
        for (const tagName of tagsToAdd) {
          await tagsClient.assignTagToEntity(EntityType.METRIC, metric.id, {
            name: tagName,
            organization_id: metric.organization_id,
            user_id: session.user?.id as UUID | undefined,
          });
        }
      }

      const updatedMetric = await metricsClient.getMetric(metric.id);
      setMetric(updatedMetric as MetricDetail);
      setIsEditing(null);
      setEditData({});
      setStepsWithIds([]);
      setTextFieldsTouched(false);

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
    session?.user?.id,
    metric,
    collectFieldValues,
    editData,
    notifications,
    isEditing,
    tagNames,
  ]);

  const addStep = React.useCallback(() => {
    setStepsWithIds(prev => {
      const newStep = { id: `step-${Date.now()}-${prev.length}`, content: '' };
      return [...prev, newStep];
    });
    setTextFieldsTouched(true);
  }, []);

  const removeStep = React.useCallback((stepId: string) => {
    setStepsWithIds(prev => prev.filter(step => step.id !== stepId));
    stepRefs.current.delete(stepId);
    setTextFieldsTouched(true);
  }, []);

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
      checkChanges,
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
      checkChanges: () => boolean;
    }) => {
      const hasChanges = isEditing === section ? checkChanges() : false;
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
                  disabled={isSaving || !hasChanges}
                  sx={{
                    bgcolor: theme.palette.primary.main,
                    '&:hover': {
                      bgcolor: theme.palette.primary.dark,
                    },
                    '&.Mui-disabled': {
                      bgcolor: theme.palette.action.disabledBackground,
                      color: theme.palette.action.disabled,
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
              checkChanges={checkForChanges}
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
                    onChange={() => setTextFieldsTouched(true)}
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
                    onChange={() => setTextFieldsTouched(true)}
                  />
                ) : (
                  <Typography>{metric.description || '-'}</Typography>
                )}
              </InfoRow>

              <InfoRow label="Tags">
                {isEditing === 'general' ? (
                  <BaseTag
                    value={editData.tags || []}
                    onChange={newTags =>
                      setEditData(prev => ({ ...prev, tags: newTags }))
                    }
                    placeholder="Add tags..."
                    chipColor="primary"
                    addOnBlur
                    delimiters={[',', 'Enter']}
                    size="small"
                  />
                ) : (
                  <BaseTag
                    value={tagNames}
                    onChange={() => {}}
                    placeholder="Add tags..."
                    chipColor="primary"
                    disableEdition={true}
                  />
                )}
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
              checkChanges={checkForChanges}
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
                            ?.name || 'Using default model'
                        : metric.model_id
                          ? 'Loading model...'
                          : 'Using default model'}
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
                    onChange={() => setTextFieldsTouched(true)}
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
                          onChange={() => setTextFieldsTouched(true)}
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
                        .map((step, index) => {
                          // Create stable key from step content
                          const stepKey = `step-${index}-${step.substring(0, 30).replace(/\s+/g, '-')}`;
                          return (
                            <Paper
                              key={stepKey}
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
                          );
                        })
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
                    onChange={() => setTextFieldsTouched(true)}
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
              checkChanges={checkForChanges}
            >
              <InfoRow label="Score Type">
                {isEditing === 'configuration' ? (
                  <Box>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ mb: 2 }}
                    >
                      Choose how this metric will be scored:
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      {(['numeric', 'categorical'] as const).map(type => {
                        const isSelected =
                          (editData.score_type || 'numeric') === type;
                        return (
                          <Chip
                            key={type}
                            label={
                              type === 'numeric' ? 'Numeric' : 'Categorical'
                            }
                            clickable
                            color={isSelected ? 'primary' : 'default'}
                            variant={isSelected ? 'filled' : 'outlined'}
                            onClick={() => {
                              setEditData(prev => ({
                                ...prev,
                                score_type: type,
                              }));
                            }}
                            sx={{
                              '&:hover': {
                                backgroundColor: isSelected
                                  ? 'primary.dark'
                                  : 'action.hover',
                              },
                            }}
                          />
                        );
                      })}
                    </Box>
                  </Box>
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
                          theme?.typography?.caption?.fontSize || '0.75rem',
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

              {(metric.score_type === 'categorical' ||
                editData.score_type === 'categorical') && (
                <>
                  <InfoRow label="Categories">
                    {isEditing === 'configuration' ? (
                      <Box>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ mb: 2 }}
                        >
                          Define the possible categorical values (minimum 2
                          required)
                        </Typography>
                        <BaseTag
                          value={editData.categories || []}
                          onChange={newCategories =>
                            setEditData(prev => ({
                              ...prev,
                              categories: newCategories,
                              // Clear passing categories if they're no longer valid
                              passing_categories: (
                                prev.passing_categories || []
                              ).filter(pc => newCategories.includes(pc)),
                            }))
                          }
                          label="Categories"
                          placeholder="Add category (e.g., Excellent, Good, Poor)"
                          chipColor="primary"
                          addOnBlur
                          delimiters={[',', 'Enter']}
                          size="small"
                        />
                      </Box>
                    ) : (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {metric.categories && metric.categories.length > 0 ? (
                          metric.categories.map(category => (
                            <Chip
                              key={category}
                              label={category}
                              color="primary"
                              variant="outlined"
                            />
                          ))
                        ) : (
                          <Typography color="text.secondary">
                            No categories defined
                          </Typography>
                        )}
                      </Box>
                    )}
                  </InfoRow>

                  <InfoRow label="Passing Categories">
                    {isEditing === 'configuration' ? (
                      <Box>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ mb: 2 }}
                        >
                          Select which categories indicate success (at least one
                          required)
                        </Typography>
                        {(editData.categories || []).length >= 2 ? (
                          <Box
                            sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}
                          >
                            {(editData.categories || []).map(category => {
                              const isSelected = (
                                editData.passing_categories || []
                              ).includes(category);
                              return (
                                <Chip
                                  key={category}
                                  label={category}
                                  clickable
                                  color={isSelected ? 'success' : 'default'}
                                  variant={isSelected ? 'filled' : 'outlined'}
                                  onClick={() => {
                                    const currentPassing =
                                      editData.passing_categories || [];
                                    const newPassing = isSelected
                                      ? currentPassing.filter(
                                          c => c !== category
                                        )
                                      : [...currentPassing, category];
                                    setEditData(prev => ({
                                      ...prev,
                                      passing_categories: newPassing,
                                    }));
                                  }}
                                  icon={isSelected ? <CheckIcon /> : undefined}
                                  sx={{
                                    '&:hover': {
                                      backgroundColor: isSelected
                                        ? 'success.dark'
                                        : 'action.hover',
                                    },
                                  }}
                                />
                              );
                            })}
                          </Box>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            Add at least 2 categories first
                          </Typography>
                        )}
                      </Box>
                    ) : (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {metric.passing_categories &&
                        metric.passing_categories.length > 0 ? (
                          metric.passing_categories.map(category => (
                            <Chip
                              key={category}
                              label={category}
                              color="success"
                              variant="filled"
                            />
                          ))
                        ) : (
                          <Typography color="text.secondary">
                            No passing categories defined
                          </Typography>
                        )}
                      </Box>
                    )}
                  </InfoRow>
                </>
              )}

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
                        <Typography variant="body1" color="text.primary">
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
                        <Typography variant="body1" color="text.primary">
                          {metric.max_score}
                        </Typography>
                      )}
                    </InfoRow>
                  </Box>

                  <InfoRow label="Threshold">
                    {isEditing === 'configuration' ? (
                      <Box>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ mb: 2 }}
                        >
                          Define the threshold condition for passing:
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 2 }}>
                          <TextField
                            key={`threshold-field-${metric.id}`}
                            required
                            type="number"
                            label="Threshold Value"
                            value={editData.threshold || ''}
                            onChange={e =>
                              setEditData(prev => ({
                                ...prev,
                                threshold: Number(e.target.value),
                              }))
                            }
                            fullWidth
                          />
                          <FormControl fullWidth>
                            <InputLabel required>Operator</InputLabel>
                            <Select
                              value={editData.threshold_operator || '>='}
                              label="Operator"
                              onChange={e =>
                                setEditData(prev => ({
                                  ...prev,
                                  threshold_operator: e.target
                                    .value as ThresholdOperator,
                                }))
                              }
                            >
                              <MenuItem value=">=">&gt;=</MenuItem>
                              <MenuItem value=">">&gt;</MenuItem>
                              <MenuItem value="<=">&lt;=</MenuItem>
                              <MenuItem value="<">&lt;</MenuItem>
                              <MenuItem value="=">=</MenuItem>
                              <MenuItem value="!=">!=</MenuItem>
                            </Select>
                          </FormControl>
                        </Box>
                      </Box>
                    ) : (
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 2 }}
                      >
                        <Typography
                          sx={{
                            bgcolor: 'success.main',
                            color: 'success.contrastText',
                            px: 1.5,
                            py: 0.5,
                            borderRadius: theme =>
                              theme.shape.borderRadius * 0.25,
                            fontSize:
                              theme?.typography?.caption?.fontSize || '0.75rem',
                            fontWeight: 'medium',
                          }}
                        >
                          {metric.threshold} {metric.threshold_operator || '>='}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Threshold condition for passing
                        </Typography>
                      </Box>
                    )}
                  </InfoRow>
                </>
              )}

              <InfoRow label="Metric Scope">
                {isEditing === 'configuration' ? (
                  <Box>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ mb: 1 }}
                    >
                      Select which test types this metric applies to (at least
                      one required):
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      {(['Single-Turn', 'Multi-Turn'] as MetricScope[]).map(
                        scope => {
                          const currentScope =
                            editData.metric_scope || metric.metric_scope || [];
                          const isSelected = currentScope.includes(scope);

                          return (
                            <Chip
                              key={scope}
                              label={scope}
                              clickable
                              color={isSelected ? 'primary' : 'default'}
                              variant={isSelected ? 'filled' : 'outlined'}
                              onClick={() => {
                                const newScope = isSelected
                                  ? currentScope.filter(s => s !== scope)
                                  : [...currentScope, scope];
                                setEditData(prev => ({
                                  ...prev,
                                  metric_scope: newScope as MetricScope[],
                                }));
                              }}
                              sx={{
                                '&:hover': {
                                  backgroundColor: isSelected
                                    ? 'primary.dark'
                                    : 'action.hover',
                                },
                              }}
                            />
                          );
                        }
                      )}
                    </Box>
                  </Box>
                ) : (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {metric.metric_scope && metric.metric_scope.length > 0 ? (
                      metric.metric_scope.map(scope => (
                        <Typography
                          key={scope}
                          sx={{
                            bgcolor: 'primary.main',
                            color: 'primary.contrastText',
                            px: 1.5,
                            py: 0.5,
                            borderRadius: theme =>
                              theme.shape.borderRadius * 0.25,
                            fontSize:
                              theme?.typography?.caption?.fontSize || '0.75rem',
                            fontWeight: 'medium',
                          }}
                        >
                          {scope}
                        </Typography>
                      ))
                    ) : (
                      <Typography variant="body1" color="text.secondary">
                        No scope defined
                      </Typography>
                    )}
                  </Box>
                )}
              </InfoRow>

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
                    onChange={() => setTextFieldsTouched(true)}
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
