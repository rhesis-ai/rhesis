'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useTheme } from '@mui/material/styles';
import {
  Box,
  Paper,
  Stack,
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
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckIcon from '@mui/icons-material/Check';
import { Fab, FabGroup } from '@/components/common/Fab';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import CloseIcon from '@mui/icons-material/Close';
import BaseTag from '@/components/common/BaseTag';
import { SectionCard } from '@/components/common/SectionCard';
import {
  SectionEditButton,
  SectionSaveCancelActions,
} from '@/components/common/SectionCardActions';
import EditableSectionCard from '@/components/common/EditableSection';
import TagsField from '@/components/common/TagsField';
import { PageLayout } from '@/components/layout/PageLayout';
import DetailEntityMissingState from '@/components/common/DetailEntityMissingState';
import { useRouter } from 'next/navigation';
import { isNotFoundApiError } from '@/utils/api-client/is-not-found-error';
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
import { TagsClient } from '@/utils/api-client/tags-client';
import { UUID } from 'crypto';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { generateCopyName } from '@/utils/entity-helpers';
import { TEST_TYPES } from '@/constants/test-types';
import { Can, useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

type EditableSectionType = 'general' | 'evaluation' | 'configuration';

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

const EditableSection = React.memo(
  ({
    title,
    section,
    children,
    isEditing,
    onEdit,
    onCancel,
    onConfirm,
    isSaving,
    checkChanges,
    editable = true,
  }: {
    title: string;
    section: EditableSectionType;
    children: React.ReactNode;
    isEditing: EditableSectionType | null;
    onEdit: (section: EditableSectionType) => void;
    onCancel: () => void;
    onConfirm: () => void;
    isSaving?: boolean;
    checkChanges: () => boolean;
    editable?: boolean;
  }) => {
    const hasChanges = isEditing === section ? checkChanges() : false;
    const actions =
      isEditing === section ? (
        <SectionSaveCancelActions
          onSave={onConfirm}
          onCancel={onCancel}
          isSaving={isSaving}
          saveDisabled={!hasChanges}
        />
      ) : isEditing === null && editable ? (
        <SectionEditButton onClick={() => onEdit(section)} />
      ) : null;

    return (
      <SectionCard title={title} actions={actions ?? undefined}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {children}
        </Box>
      </SectionCard>
    );
  }
);

EditableSection.displayName = 'EditableSection';

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

export type MetricDetailViewMode = 'page' | 'embedded' | 'content';

export interface MetricDetailViewProps {
  metricId: string;
  mode?: MetricDetailViewMode;
  /** Shown when mode is embedded (e.g. dialog close). */
  onClose?: () => void;
  /** Called after a successful save so the parent can refresh summaries. */
  onSaved?: () => void;
  /** Optional tab nav rendered above the detail body in page mode. */
  tabNav?: React.ReactNode;
  /** Optional content to replace the detail body (e.g. for secondary tabs). */
  tabBody?: React.ReactNode;
}

export function MetricDetailView({
  metricId,
  mode = 'page',
  onClose,
  onSaved,
  tabNav,
  tabBody,
}: MetricDetailViewProps) {
  const { data: session, status } = useSession();
  const theme = useTheme();
  const router = useRouter();
  const canEditMetric = useCan(Capability.Metric.UPDATE);
  const [metric, setMetric] = useState<MetricDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [missingError, setMissingError] = useState<unknown>(null);
  const notifications = useNotifications();
  const [isEditing, setIsEditing] = useState<EditableSectionType | null>(null);
  const [editData, setEditData] = useState<Partial<EditData>>({});
  const [models, setModels] = useState<Model[]>([]);
  const [stepsWithIds, setStepsWithIds] = useState<StepWithId[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const dataFetchedRef = useRef(false);
  const textFieldsDirtyRef = useRef(false);
  const [blurRevision, setBlurRevision] = useState(0);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Set document title dynamically (full page only)
  useDocumentTitle(mode === 'page' ? metric?.name || null : null);

  // Refs for uncontrolled text fields
  const nameRef = useRef<HTMLInputElement>(null);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);
  const evaluationPromptRef = useRef<HTMLTextAreaElement>(null);
  const reasoningRef = useRef<HTMLTextAreaElement>(null);
  const explanationRef = useRef<HTMLTextAreaElement>(null);
  const stepRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map());
  const stepRefCallbacks = useRef(
    new Map<string, (el: HTMLTextAreaElement | null) => void>()
  );

  useEffect(() => {
    dataFetchedRef.current = false;
    setLoading(true);
    setMetric(null);
    setMissingError(null);
  }, [metricId]);

  useEffect(() => {
    const fetchData = async () => {
      if (!isAuthenticated(status) || dataFetchedRef.current) return;

      dataFetchedRef.current = true;

      try {
        const clientFactory = new ApiClientFactory(
          session?.session_token ?? ''
        );
        const metricsClient = clientFactory.getMetricsClient();

        // Fetch metric data
        const metricData = await metricsClient.getMetric(metricId as UUID);

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
          if (mode === 'embedded') {
            onCloseRef.current?.();
          } else {
            router.push('/metrics');
          }
          return;
        }
      } catch (error: unknown) {
        if (isNotFoundApiError(error)) {
          setMissingError(error);
        } else {
          notifications.show('Failed to load metric details', {
            severity: 'error',
          });
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [metricId, mode, session?.session_token, notifications, router, status]);

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

    if (textFieldsDirtyRef.current) {
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

    if (isEditing === 'evaluation') {
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [metric, isEditing, blurRevision, editData, collectFieldValues]);

  const markTextFieldDirty = React.useCallback(() => {
    textFieldsDirtyRef.current = true;
  }, []);

  const handleTextFieldBlur = React.useCallback(() => {
    if (textFieldsDirtyRef.current) {
      setBlurRevision(c => c + 1);
    }
  }, []);

  // Returns a stable ref callback for each step ID so React doesn't
  // detach/reattach the ref on re-renders (which causes focus loss).
  const getStepRef = React.useCallback((stepId: string) => {
    const existingCallback = stepRefCallbacks.current.get(stepId);
    if (existingCallback) {
      return existingCallback;
    }
    const callback = (el: HTMLTextAreaElement | null) => {
      if (el) {
        stepRefs.current.set(stepId, el);
      } else {
        stepRefs.current.delete(stepId);
      }
    };
    stepRefCallbacks.current.set(stepId, callback);
    return callback;
  }, []);

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

  const tagNames = React.useMemo(
    () => metric?.tags?.map(tag => tag.name) || [],
    [metric?.tags]
  );

  const handleTagsSave = React.useCallback(
    async (draft: { tagNames: string[] }) => {
      if (!metric || !isAuthenticated(status)) return;
      const tagsClient = new TagsClient(session?.session_token);
      const currentTagObjects = metric.tags || [];
      const currentTagMap = new Map(
        currentTagObjects.map(tag => [tag.name, tag])
      );
      const toRemove = tagNames.filter(n => !draft.tagNames.includes(n));
      const toAdd = draft.tagNames.filter(n => !tagNames.includes(n));

      for (const name of toRemove) {
        const tag = currentTagMap.get(name);
        if (tag) {
          await tagsClient.removeTagFromEntity(
            EntityType.METRIC,
            metric.id,
            tag.id
          );
        }
      }
      for (const name of toAdd) {
        await tagsClient.assignTagToEntity(EntityType.METRIC, metric.id, {
          name,
          organization_id: metric.organization_id,
          user_id: session?.user?.id as UUID | undefined,
        });
      }

      const clientFactory = new ApiClientFactory(session?.session_token ?? '');
      const updatedMetric = await clientFactory
        .getMetricsClient()
        .getMetric(metric.id);
      setMetric(updatedMetric as MetricDetail);
      notifications.show('Tags updated', {
        severity: 'success',
        autoHideDuration: 4000,
      });
    },
    [metric, session, tagNames, notifications, status]
  );

  const handleEdit = React.useCallback(
    async (section: EditableSectionType) => {
      if (!metric) return;

      setIsEditing(section);
      textFieldsDirtyRef.current = false;

      populateFieldRefs(section, metric);

      // Only set editData for select fields (model, score_type, etc.)
      let sectionData: Partial<EditData> = {};

      if (section === 'evaluation') {
        sectionData = {
          model_id: metric.model_id,
        };

        // For editing, we need all available models, not just the current one
        setModels(currentModels => {
          if (currentModels.length <= 1 && isAuthenticated(status)) {
            // Fetch models asynchronously without blocking
            (async () => {
              try {
                const clientFactory = new ApiClientFactory(
                  session?.session_token as string
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
    [
      metric,
      session?.session_token,
      populateFieldRefs,
      notifications,
      tagNames,
      status,
    ]
  );

  const handleCancelEdit = React.useCallback(() => {
    setIsEditing(null);
    setEditData({});
    setStepsWithIds([]);
    textFieldsDirtyRef.current = false;
    // Clear step refs
    stepRefs.current.clear();
  }, []);

  const handleConfirmEdit = React.useCallback(async () => {
    if (!isAuthenticated(status) || !metric) return;

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

      const clientFactory = new ApiClientFactory(session?.session_token ?? '');
      const metricsClient = clientFactory.getMetricsClient();
      await metricsClient.updateMetric(metric.id, dataToSend);

      const updatedMetric = await metricsClient.getMetric(metric.id);
      setMetric(updatedMetric as MetricDetail);
      setIsEditing(null);
      setEditData({});
      setStepsWithIds([]);
      textFieldsDirtyRef.current = false;

      notifications.show('Metric updated successfully', {
        severity: 'success',
      });
      onSaved?.();
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
    onSaved,
    status,
  ]);

  const addStep = React.useCallback(() => {
    setStepsWithIds(prev => {
      const newStep = { id: `step-${Date.now()}-${prev.length}`, content: '' };
      return [...prev, newStep];
    });
    textFieldsDirtyRef.current = true;
    setBlurRevision(c => c + 1);
  }, []);

  const removeStep = React.useCallback((stepId: string) => {
    setStepsWithIds(prev => prev.filter(step => step.id !== stepId));
    stepRefs.current.delete(stepId);
    stepRefCallbacks.current.delete(stepId);
    textFieldsDirtyRef.current = true;
    setBlurRevision(c => c + 1);
  }, []);

  const [isDuplicating, setIsDuplicating] = React.useState(false);

  const handleDuplicate = React.useCallback(async () => {
    if (!isAuthenticated(status) || !metric) return;

    setIsDuplicating(true);
    try {
      const clientFactory = new ApiClientFactory(session?.session_token ?? '');
      const metricsClient = clientFactory.getMetricsClient();

      const created = await metricsClient.createMetric({
        name: generateCopyName(metric.name),
        description: metric.description || undefined,
        tags: metric.tags?.map(t => t.name) || [],
        evaluation_prompt: metric.evaluation_prompt || '',
        evaluation_steps: metric.evaluation_steps || undefined,
        evaluation_examples: metric.evaluation_examples || undefined,
        reasoning: metric.reasoning || undefined,
        score_type: metric.score_type || 'numeric',
        min_score: metric.min_score,
        max_score: metric.max_score,
        categories: metric.categories,
        passing_categories: metric.passing_categories,
        threshold: metric.threshold,
        threshold_operator: metric.threshold_operator,
        explanation: metric.explanation || '',
        ground_truth_required: metric.ground_truth_required,
        metric_scope: metric.metric_scope,
        metric_type_id: metric.metric_type?.id as UUID,
        backend_type_id: metric.backend_type?.id as UUID,
        model_id: metric.model_id,
      });

      notifications.show('Metric duplicated successfully', {
        severity: 'success',
        autoHideDuration: 4000,
      });

      router.push(`/metrics/${created.id}`);
    } catch (_error) {
      notifications.show('Failed to duplicate metric', {
        severity: 'error',
        autoHideDuration: 4000,
      });
    } finally {
      setIsDuplicating(false);
    }
  }, [session?.session_token, metric, notifications, router, status]);

  if (loading) {
    if (mode === 'embedded') {
      return (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: 280,
            px: 2,
          }}
        >
          <Typography color="text.secondary">
            Loading metric details…
          </Typography>
        </Box>
      );
    }
    return (
      <PageLayout title="Loading...">
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
      </PageLayout>
    );
  }

  if (!metric) {
    if (missingError && mode === 'page') {
      return (
        <DetailEntityMissingState
          error={missingError}
          entityLabel="Metric"
          entityId={metricId}
          entityTableName="metric"
          listUrl="/metrics"
          breadcrumbs={[
            { label: 'Metrics', href: '/metrics' },
            { label: 'Not Found', href: `/metrics/${metricId}` },
          ]}
          onBack={() => router.push('/metrics')}
        />
      );
    }

    if (mode === 'embedded') {
      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2,
            minHeight: 200,
            px: 2,
          }}
        >
          <Typography color="error">Failed to load metric details</Typography>
          {onClose ? (
            <Button variant="outlined" onClick={onClose}>
              Close
            </Button>
          ) : null}
        </Box>
      );
    }
    return (
      <PageLayout title="Error">
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
      </PageLayout>
    );
  }

  const detailBody = (
    <Stack direction="column" spacing={3}>
      {/* Main content */}
      <Box sx={{ flex: 1 }}>
        <Stack spacing={3}>
          {/* General Information Section */}
          <EditableSection
            editable={canEditMetric}
            title="General Information"
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
                  onChange={markTextFieldDirty}
                  onBlur={handleTextFieldBlur}
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
                  onChange={markTextFieldDirty}
                  onBlur={handleTextFieldBlur}
                />
              ) : (
                <Typography>{metric.description || '-'}</Typography>
              )}
            </InfoRow>
          </EditableSection>

          {/* Tags Section */}
          <EditableSectionCard
            editable={canEditMetric}
            title="Tags"
            initialValue={{ tagNames }}
            onSave={handleTagsSave}
            isDirty={(draft, initial) =>
              JSON.stringify(draft.tagNames.slice().sort()) !==
              JSON.stringify(initial.tagNames.slice().sort())
            }
          >
            {({ draft, setDraft, isEditing: isTagsEditing }) => (
              <TagsField
                tagNames={draft.tagNames}
                isEditing={isTagsEditing}
                onChange={names => setDraft(d => ({ ...d, tagNames: names }))}
                helperText="These tags help categorize and find this metric"
                emptyLabel="No tags"
              />
            )}
          </EditableSectionCard>

          {/* Evaluation Process Section */}
          <EditableSection
            editable={canEditMetric}
            title="Evaluation Process"
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
                  onChange={markTextFieldDirty}
                  onBlur={handleTextFieldBlur}
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
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {stepsWithIds.map((step, index) => (
                    <Box key={step.id} sx={{ display: 'flex', gap: 1 }}>
                      <TextField
                        fullWidth
                        multiline
                        rows={2}
                        inputRef={getStepRef(step.id)}
                        defaultValue={step.content}
                        placeholder={`Step ${index + 1}: Describe this evaluation step...`}
                        onChange={markTextFieldDirty}
                        onBlur={handleTextFieldBlur}
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
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
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
                  onChange={markTextFieldDirty}
                  onBlur={handleTextFieldBlur}
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
            editable={canEditMetric}
            title="Result Configuration"
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
                          label={type === 'numeric' ? 'Numeric' : 'Categorical'}
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
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
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
                                    ? currentPassing.filter(c => c !== category)
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
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
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
                    Select which test types this metric applies to (at least one
                    required):
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {(
                      [
                        TEST_TYPES.SINGLE_TURN,
                        TEST_TYPES.MULTI_TURN,
                        'Trace',
                      ] as MetricScope[]
                    ).map(scope => {
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
                    })}
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
                  onChange={markTextFieldDirty}
                  onBlur={handleTextFieldBlur}
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
  );

  if (mode === 'embedded') {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          minHeight: 0,
        }}
      >
        <Box
          sx={{
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1,
            px: 2,
            py: 1.5,
            borderBottom: 1,
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          <Typography variant="h6" component="span" sx={{ fontWeight: 600 }}>
            {metric.name}
          </Typography>
          {onClose ? (
            <IconButton
              aria-label="Close"
              onClick={onClose}
              edge="end"
              size="small"
            >
              <CloseIcon />
            </IconButton>
          ) : null}
        </Box>
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            overflow: 'auto',
            p: { xs: 1.5, sm: 2 },
          }}
        >
          {detailBody}
        </Box>
      </Box>
    );
  }

  if (mode === 'content') {
    return <>{detailBody}</>;
  }

  return (
    <PageLayout
      title={metric.name}
      breadcrumbs={[
        { label: 'Metrics', href: '/metrics' },
        { label: metric.name, href: `/metrics/${metricId}` },
      ]}
      actions={
        <FabGroup>
          <Can capability={Capability.Metric.CREATE}>
            <Fab
              icon={<ContentCopyIcon />}
              tooltip="Duplicate"
              aria-label="Duplicate metric"
              onClick={handleDuplicate}
              loading={isDuplicating}
              disabled={!!isEditing}
            />
          </Can>
        </FabGroup>
      }
    >
      {tabNav && <Box sx={{ mb: 2 }}>{tabNav}</Box>}
      {tabBody !== undefined ? tabBody : detailBody}
    </PageLayout>
  );
}
