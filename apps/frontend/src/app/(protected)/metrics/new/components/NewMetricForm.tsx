'use client';

/* eslint-disable react/no-array-index-key -- evaluation steps are plain strings without stable IDs */

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { PageLayout } from '@/components/layout/PageLayout';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import { useTheme } from '@mui/material/styles';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CheckIcon from '@mui/icons-material/Check';
import { useNotifications } from '@/components/common/NotificationContext';
import Stepper from '@mui/material/Stepper';
import Step from '@mui/material/Step';
import StepLabel from '@mui/material/StepLabel';
import BaseTag from '@/components/common/BaseTag';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ConditionOperatorChoice,
  MetricCreate,
  MetricTargetChoice,
  ThresholdOperator,
} from '@/utils/api-client/interfaces/metric';
import type { UUID } from 'crypto';
import { Model } from '@/utils/api-client/interfaces/model';
import CircularProgress from '@mui/material/CircularProgress';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { SCORE_TYPES, ScoreTypeValue } from '@/constants/score-types';
import { useMetricTargetOptions, useTypeLookups } from '@/hooks/useLookups';
import {
  formatMetricTarget,
  METRIC_TARGET,
  offeredTargetsWithCustom,
} from '@/utils/metric-targets';
import {
  draftFromTarget,
  draftProblem,
  targetFromDraft,
  type TargetDraft,
} from '@/utils/metric-target-draft';
import MetricTargetBuilder from '../../components/MetricTargetBuilder';
import TargetSummaryText from '../../components/TargetSummaryText';
import RuleFields, { RuleSummary } from '../../components/RuleFields';
import { METRIC_TYPES } from '@/constants/metric-types';
import {
  describeRule,
  initialRuleDraft,
  RULE_CLASSES,
  ruleConfig,
  ruleDraftError,
  ruleTargetChoices,
  type RuleDraft,
} from '@/utils/metric-rules';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { validateScore } from '@/utils/validation';
import { formatEvaluationSteps } from '@/utils/evaluation-steps';
import {
  canJudgeScoreType,
  isEmbeddingModel,
} from '@/utils/model-capabilities';
import {
  NEW_METRIC_CRUMB,
  PAGE_HEADERS,
  directoryCrumb,
} from '@/constants/page-headers';
import { NEW_METRIC_STEPS, newMetricTitle } from './new-metric-header';

interface MetricFormData {
  name: string;
  description: string;
  tags: string[];
  evaluation_prompt: string;
  evaluation_steps: string[];
  reasoning: string;
  score_type: ScoreTypeValue;
  categories: string[];
  passing_categories: string[];
  // Raw text from the number inputs, not numbers: a partially typed value
  // ('', '-', '0.') has no numeric form. Parsed once in handleSubmit.
  min_score: string;
  max_score: string;
  threshold: string;
  threshold_operator: ThresholdOperator;
  explanation: string;
  model_id: string;
  target: TargetDraft;
  rule: RuleDraft;
}

const initialFormData: MetricFormData = {
  name: '',
  description: '',
  tags: [],
  evaluation_prompt: '',
  evaluation_steps: [''],
  reasoning: '',
  score_type: SCORE_TYPES.NUMERIC,
  categories: [],
  passing_categories: [],
  min_score: '',
  max_score: '',
  threshold: '',
  threshold_operator: '>=',
  explanation: '',
  model_id: '',
  target: draftFromTarget(null, METRIC_TARGET.TURN),
  rule: initialRuleDraft,
};

// A rule is fixed to pass at a score of 1; it reports 1 or 0.
const RULE_SCORE = { min: 0, max: 1, threshold: 1 } as const;

const NO_TARGETS: MetricTargetChoice[] = [];
const NO_OPERATORS: ConditionOperatorChoice[] = [];

/** The presets a new metric can take: a rule's, else every one. */
function ruleOrAllTargets(
  isRule: boolean,
  rule: RuleDraft,
  allTargets: MetricTargetChoice[]
): MetricTargetChoice[] {
  return isRule ? ruleTargetChoices(rule.ruleClass, allTargets) : allTargets;
}

/** The presets plus "Custom spans" when any of them judges single spans. */
function withCustomSpans(choices: MetricTargetChoice[]): MetricTargetChoice[] {
  return offeredTargetsWithCustom(choices);
}

const steps = NEW_METRIC_STEPS;

interface NewMetricFormProps {
  type: string;
  /** Server-fetched data -- when present, skips the initial client fetch. */
  initialModels?: Model[];
}

export default function NewMetricForm({
  type,
  initialModels,
}: NewMetricFormProps) {
  const a11yId = React.useId();
  const router = useRouter();
  const notifications = useNotifications();
  const { data: session, status } = useSession();
  const theme = useTheme();
  const isRule = type === METRIC_TYPES.RULE;
  // Rules run in Rhesis itself; judges written here are the organization's own.
  const backendTypeValue = isRule ? 'rhesis' : 'custom';
  const { data: allTypeLookups } = useTypeLookups(
    `(type_name eq 'MetricType' and type_value eq '${type}') or (type_name eq 'BackendType' and type_value eq '${backendTypeValue}')`
  );
  const { data: targetOptions } = useMetricTargetOptions();
  const allTargets = targetOptions?.targets ?? NO_TARGETS;
  const operators = targetOptions?.operators ?? NO_OPERATORS;
  const [activeStep, setActiveStep] = React.useState(0);
  const [formData, setFormData] =
    React.useState<MetricFormData>(initialFormData);
  // The draft's summary as the preview words it, for the confirmation step.
  const [targetSummary, setTargetSummary] = React.useState<string | null>(null);
  // The form has no "ground truth required" field, so only a rule narrows this.
  const targetChoices = React.useMemo(
    () => withCustomSpans(ruleOrAllTargets(isRule, formData.rule, allTargets)),
    [allTargets, isRule, formData.rule]
  );
  const spanKinds = React.useMemo(
    () => allTargets.filter(choice => choice.per_span),
    [allTargets]
  );

  const handleRuleChange = (rule: RuleDraft) => {
    setFormData(prev => {
      const choices = withCustomSpans(ruleOrAllTargets(true, rule, allTargets));
      // A target the new kind of rule can't take falls back to each turn.
      const target =
        choices.length === 0 || choices.some(c => c.on === prev.target.on)
          ? prev.target
          : draftFromTarget(null, METRIC_TARGET.TURN);
      return { ...prev, rule, target };
    });
  };
  const [models, setModels] = React.useState<Model[]>(initialModels ?? []);
  const [isLoadingModels, setIsLoadingModels] = React.useState(
    initialModels === undefined
  );
  const [isCreating, setIsCreating] = React.useState(false);
  // Any model that can judge some score type is listed; picking a decision model
  // (Jev) moves the score type to categorical, the only one it can judge.
  const judgeModels = React.useMemo(
    () => models.filter(model => !isEmbeddingModel(model)),
    [models]
  );
  const [showErrors, setShowErrors] = React.useState(false);

  // Fetch models on component mount
  React.useEffect(() => {
    if (initialModels !== undefined) return;

    const fetchModels = async () => {
      if (!isAuthenticated(status)) return;

      try {
        setIsLoadingModels(true);
        const apiClient = new ApiClientFactory();
        const modelsClient = apiClient.getModelsClient();
        const response = await modelsClient.getModels({
          sort_by: 'name',
          sort_order: 'asc',
          skip: 0,
          limit: 100,
        });
        setModels(response.data || []); // Use .data instead of .items
      } catch (_error) {
        notifications.show('Failed to load evaluation models', {
          severity: 'error',
        });
      } finally {
        setIsLoadingModels(false);
      }
    };

    fetchModels();
  }, [notifications, status, initialModels]);

  const handleChange =
    (field: keyof MetricFormData) =>
    (
      event:
        | React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
        | SelectChangeEvent<string>
    ) => {
      const value = event.target.value;
      setFormData(prev => ({
        ...prev,
        [field]: value,
      }));
    };

  const handleModelChange = (event: SelectChangeEvent<string>) => {
    const modelId = event.target.value;
    const selected = models.find(model => model.id === modelId);
    const toCategorical =
      !!selected && !canJudgeScoreType(selected, formData.score_type);
    setFormData(prev => ({
      ...prev,
      model_id: modelId,
      ...(toCategorical && { score_type: SCORE_TYPES.CATEGORICAL }),
    }));
    if (toCategorical && selected) {
      notifications.show(
        `${selected.name} can only judge categorical metrics, so the score type was set to Categorical.`,
        { severity: 'info' }
      );
    }
  };

  const handleStepChange =
    (index: number) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      // Use prev.evaluation_steps instead of the formData closure so concurrent
      // edits (e.g. rapid keystrokes batched in the same tick) are not lost.
      setFormData(prev => {
        const newSteps = [...prev.evaluation_steps];
        newSteps[index] = event.target.value;
        return { ...prev, evaluation_steps: newSteps };
      });
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

  // Only rendered for numeric metrics, so computing them unconditionally is harmless.
  const minScoreError = showErrors
    ? validateScore(formData.min_score, 'Minimum Score').message
    : undefined;
  const maxScoreError = showErrors
    ? validateScore(formData.max_score, 'Maximum Score').message
    : undefined;
  const thresholdError = showErrors
    ? validateScore(formData.threshold, 'Threshold Value').message
    : undefined;

  const isStepValid = React.useCallback((): boolean => {
    // Common required fields
    if (!formData.name.trim()) return false;
    if (draftProblem(formData.target, allTargets, operators) !== null) {
      return false;
    }
    if (isRule) return ruleDraftError(formData.rule) === null;
    if (!formData.evaluation_prompt.trim()) return false;

    // Score type conditional validation
    if (formData.score_type === SCORE_TYPES.NUMERIC) {
      if (!validateScore(formData.min_score).isValid) return false;
      if (!validateScore(formData.max_score).isValid) return false;
      if (!validateScore(formData.threshold).isValid) return false;
    }

    if (formData.score_type === SCORE_TYPES.CATEGORICAL) {
      if (!formData.categories || formData.categories.length < 2) return false;
      if (
        !formData.passing_categories ||
        formData.passing_categories.length < 1
      )
        return false;
    }

    return true;
  }, [formData, isRule, allTargets, operators]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (activeStep !== steps.length - 1) {
      // If not on the final step, don't submit
      return;
    }

    setIsCreating(true);

    try {
      if (!isAuthenticated(status)) {
        throw new Error(
          'No session token available. Please try logging in again.'
        );
      }

      const apiClient = new ApiClientFactory();
      const metricsClient = apiClient.getMetricsClient();

      const typeLookups = (allTypeLookups ?? []).filter(
        lookup =>
          lookup.type_name === 'MetricType' && lookup.type_value === type
      );
      const backendTypes = (allTypeLookups ?? []).filter(
        lookup =>
          lookup.type_name === 'BackendType' &&
          lookup.type_value === backendTypeValue
      );

      if (!typeLookups.length) {
        throw new Error('Invalid metric type');
      }

      if (!backendTypes.length) {
        throw new Error(`Backend type "${backendTypeValue}" not found`);
      }

      const target = targetFromDraft(formData.target, allTargets, operators);
      // Tags are added separately, after the metric exists.
      const metricRequest: MetricCreate = isRule
        ? {
            name: formData.name,
            description: formData.description || '',
            tags: [],
            // The column needs text; for a rule it is the rule in one line.
            evaluation_prompt: describeRule(formData.rule),
            score_type: SCORE_TYPES.NUMERIC,
            min_score: RULE_SCORE.min,
            max_score: RULE_SCORE.max,
            threshold: RULE_SCORE.threshold,
            threshold_operator: '>=',
            explanation: '',
            class_name: formData.rule.ruleClass,
            // Lets the metric pickers leave a response rule off multi-turn sets.
            ground_truth_required:
              formData.rule.ruleClass === RULE_CLASSES.RESPONSE,
            metric_type_id: typeLookups[0].id as UUID,
            backend_type_id: backendTypes[0].id as UUID,
            owner_id: session?.user?.id as UUID,
            config: { ...ruleConfig(formData.rule), target },
          }
        : {
            name: formData.name,
            description: formData.description || '',
            tags: [], // Tags will be assigned separately after creation
            evaluation_prompt: formData.evaluation_prompt,
            evaluation_steps: formatEvaluationSteps(formData.evaluation_steps),
            reasoning: formData.reasoning || '',
            score_type: formData.score_type,
            // Categorical metric fields
            categories:
              formData.score_type === SCORE_TYPES.CATEGORICAL
                ? formData.categories
                : undefined,
            passing_categories:
              formData.score_type === SCORE_TYPES.CATEGORICAL
                ? formData.passing_categories
                : undefined,
            // Numeric metric fields
            // Number, not parseFloat: validateScore rejects what Number rejects, so
            // the two agree on what reaches the API. parseFloat would accept more.
            min_score:
              formData.score_type === SCORE_TYPES.NUMERIC
                ? Number(formData.min_score)
                : undefined,
            max_score:
              formData.score_type === SCORE_TYPES.NUMERIC
                ? Number(formData.max_score)
                : undefined,
            threshold:
              formData.score_type === SCORE_TYPES.NUMERIC
                ? Number(formData.threshold)
                : undefined,
            threshold_operator:
              formData.score_type === SCORE_TYPES.NUMERIC
                ? formData.threshold_operator
                : undefined,
            explanation: formData.explanation || '',
            metric_type_id: typeLookups[0].id as UUID,
            backend_type_id: backendTypes[0].id as UUID,
            model_id: formData.model_id
              ? (formData.model_id as UUID)
              : undefined,
            owner_id: session?.user?.id as UUID,
            config: { target },
          };

      // Create the metric
      const createdMetric = await metricsClient.createMetric(metricRequest);

      // If tags are present, assign them to the metric
      if (formData.tags && formData.tags.length > 0) {
        const tagsClient = apiClient.getTagsClient();

        // Assign each tag to the metric
        for (const tagName of formData.tags) {
          try {
            await tagsClient.assignTagToEntity(
              EntityType.METRIC,
              createdMetric.id,
              {
                name: tagName,
                organization_id: session?.user?.organization_id as UUID,
                user_id: session?.user?.id as UUID,
              }
            );
          } catch (tagError) {
            // Log error but don't fail the whole operation
            console.error(`Failed to assign tag "${tagName}":`, tagError);
          }
        }
      }

      // What the create noticed, such as a condition on a key no recent span carries.
      const warnings = createdMetric.warnings ?? [];
      notifications.show(
        warnings.length
          ? `Metric created. ${warnings.join(' ')}`
          : 'Metric created successfully',
        { severity: warnings.length ? 'warning' : 'success' }
      );
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
    if (!isStepValid()) {
      setShowErrors(true);
      return;
    }
    setShowErrors(false);
    setActiveStep(prevStep => prevStep + 1);
  };

  const handleBack = (event: React.MouseEvent) => {
    event.preventDefault(); // Prevent any form submission
    setShowErrors(false);
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
          error={showErrors && !formData.name.trim()}
          helperText={
            showErrors && !formData.name.trim()
              ? 'Name is required'
              : 'Your custom metric name is simply for identification purposes only. It must not be one of the built-in metric names, and cannot already be taken by another custom metric.'
          }
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

      {isRule ? renderRuleSection() : renderJudgeSections()}
    </>
  );

  const renderTargetPicker = () =>
    targetChoices.length > 0 && (
      <Box sx={{ mb: 3 }}>
        <Typography variant="body1" sx={{ mb: 1, fontWeight: 'medium' }}>
          Target
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Choose the part of the trace this metric looks at.
        </Typography>
        <MetricTargetBuilder
          choices={targetChoices}
          value={formData.target}
          onChange={target => setFormData(prev => ({ ...prev, target }))}
          showErrors={showErrors}
          onSummaryChange={setTargetSummary}
        />
      </Box>
    );

  const renderRuleSection = () => (
    <Box>
      <Typography variant="h6" sx={{ mb: 1, color: 'primary.main' }}>
        Rule
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        A rule checks a value in the trace, or the output against the expected
        response, with no model. It passes or fails, and is not applicable when
        the trace doesn&apos;t have the value.
      </Typography>
      <Box sx={{ mb: 4 }}>
        <RuleFields
          draft={formData.rule}
          onChange={handleRuleChange}
          spanKinds={spanKinds}
          showErrors={showErrors}
          allowClassChoice
        />
      </Box>
      {renderTargetPicker()}
    </Box>
  );

  const renderJudgeSections = () => (
    <>
      {/* Evaluation Section */}
      <Box sx={{ mb: 5 }}>
        <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
          Evaluation Process
        </Typography>

        <FormControl fullWidth sx={{ mb: 3 }}>
          <InputLabel id={`${a11yId}-evaluation-model`}>
            Evaluation Model
          </InputLabel>
          <Select
            labelId={`${a11yId}-evaluation-model`}
            value={formData.model_id}
            label="Evaluation Model"
            onChange={handleModelChange}
          >
            {isLoadingModels ? (
              <MenuItem disabled>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CircularProgress size={20} />
                  <Typography>Loading models...</Typography>
                </Box>
              </MenuItem>
            ) : judgeModels.length === 0 ? (
              <MenuItem disabled>
                <Typography>No models available</Typography>
              </MenuItem>
            ) : (
              judgeModels.map(model => (
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
          error={showErrors && !formData.evaluation_prompt.trim()}
          helperText={
            showErrors && !formData.evaluation_prompt.trim()
              ? 'Evaluation prompt is required'
              : 'The main prompt that will guide the evaluation process. This should clearly state what needs to be evaluated.'
          }
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
              multiline
              rows={2}
              label={`Step ${index + 1}`}
              placeholder="Describe this evaluation step..."
              value={step}
              onChange={handleStepChange(index)}
            />
            <IconButton
              aria-label={`Remove step ${index + 1}`}
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

        {/* Score Type Selection */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="body1" sx={{ mb: 1, fontWeight: 'medium' }}>
            Score Type{' '}
            <Typography component="span" sx={{ color: 'error.main' }}>
              *
            </Typography>
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Choose how this metric will be scored:
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {([SCORE_TYPES.NUMERIC, SCORE_TYPES.CATEGORICAL] as const).map(
              scoreType => {
                const isSelected = formData.score_type === scoreType;
                return (
                  <Chip
                    key={scoreType}
                    label={
                      scoreType === SCORE_TYPES.NUMERIC
                        ? 'Numeric'
                        : 'Categorical'
                    }
                    clickable
                    color={isSelected ? 'primary' : 'default'}
                    variant={isSelected ? 'filled' : 'outlined'}
                    onClick={() => {
                      const selected = models.find(
                        model => model.id === formData.model_id
                      );
                      // A decision model (Jev) can't judge the new score type, so drop it
                      const dropModel =
                        !!selected && !canJudgeScoreType(selected, scoreType);
                      setFormData(prev => ({
                        ...prev,
                        score_type: scoreType,
                        ...(dropModel && { model_id: '' }),
                      }));
                      if (dropModel && selected) {
                        notifications.show(
                          `${selected.name} can only judge categorical metrics, so it was unselected as the evaluation model.`,
                          { severity: 'info' }
                        );
                      }
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

        {formData.score_type === SCORE_TYPES.CATEGORICAL && (
          <>
            {/* Categories Input */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="body1" sx={{ mb: 1, fontWeight: 'medium' }}>
                Categories{' '}
                <Typography component="span" sx={{ color: 'error.main' }}>
                  *
                </Typography>
              </Typography>
              <Typography
                variant="body2"
                color={
                  showErrors &&
                  (!formData.categories || formData.categories.length < 2)
                    ? 'error'
                    : 'text.secondary'
                }
                sx={{ mb: 2 }}
              >
                {showErrors &&
                (!formData.categories || formData.categories.length < 2)
                  ? 'At least 2 categories are required'
                  : 'Define the possible categorical values the LLM can return (minimum 2 required)'}
              </Typography>
              <BaseTag
                value={formData.categories || []}
                onChange={newCategories =>
                  setFormData(prev => ({
                    ...prev,
                    categories: newCategories,
                    // Clear passing categories if they're no longer valid
                    passing_categories: (prev.passing_categories || []).filter(
                      pc => newCategories.includes(pc)
                    ),
                  }))
                }
                label="Categories"
                placeholder="Add category (e.g., Excellent, Good, Poor)"
                helperText="Press Enter or comma to add each category"
                chipColor="primary"
                addOnBlur
                delimiters={[',', 'Enter']}
                size="small"
              />
            </Box>

            {/* Passing Categories Selection */}
            {formData.categories?.length >= 2 && (
              <Box sx={{ mb: 3 }}>
                <Typography
                  variant="body1"
                  sx={{ mb: 1, fontWeight: 'medium' }}
                >
                  Passing Categories{' '}
                  <Typography component="span" sx={{ color: 'error.main' }}>
                    *
                  </Typography>
                </Typography>
                <Typography
                  variant="body2"
                  color={
                    showErrors &&
                    (!formData.passing_categories ||
                      formData.passing_categories.length < 1)
                      ? 'error'
                      : 'text.secondary'
                  }
                  sx={{ mb: 2 }}
                >
                  {showErrors &&
                  (!formData.passing_categories ||
                    formData.passing_categories.length < 1)
                    ? 'At least one passing category must be selected'
                    : 'Select which categories indicate a successful/passing result (at least one required)'}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {(formData.categories || []).map(category => {
                    const isSelected = (
                      formData.passing_categories || []
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
                            formData.passing_categories || [];
                          const newPassing = isSelected
                            ? currentPassing.filter(c => c !== category)
                            : [...currentPassing, category];
                          setFormData(prev => ({
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
              </Box>
            )}
          </>
        )}

        {formData.score_type === SCORE_TYPES.NUMERIC && (
          <>
            <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
              <TextField
                required
                type="number"
                label="Minimum Score"
                value={formData.min_score}
                onChange={handleChange('min_score')}
                error={minScoreError !== undefined}
                helperText={minScoreError}
                fullWidth
              />
              <TextField
                required
                type="number"
                label="Maximum Score"
                value={formData.max_score}
                onChange={handleChange('max_score')}
                error={maxScoreError !== undefined}
                helperText={maxScoreError}
                fullWidth
              />
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Define the threshold condition for passing:
              </Typography>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <TextField
                  required
                  type="number"
                  label="Threshold Value"
                  value={formData.threshold}
                  onChange={handleChange('threshold')}
                  error={thresholdError !== undefined}
                  helperText={thresholdError}
                  fullWidth
                />
                <FormControl fullWidth>
                  <InputLabel id={`${a11yId}-operator`} required>
                    Operator
                  </InputLabel>
                  <Select
                    labelId={`${a11yId}-operator`}
                    value={formData.threshold_operator}
                    label="Operator"
                    onChange={e =>
                      setFormData(prev => ({
                        ...prev,
                        threshold_operator: e.target.value as ThresholdOperator,
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
          </>
        )}

        {renderTargetPicker()}

        <TextField
          fullWidth
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
      {/* General Section Review */}
      <Box sx={{ mb: 5 }}>
        <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
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
                <Chip key={tag} label={tag} color="primary" variant="filled" />
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
      </Box>

      {isRule ? renderRuleConfirmation() : renderJudgeConfirmation()}
    </Box>
  );

  const renderTargetConfirmation = () => (
    <Box sx={{ mb: 3 }}>
      <Typography
        variant="subtitle2"
        color="text.secondary"
        sx={{ fontWeight: 'medium', mb: 1 }}
      >
        Target
      </Typography>
      <Chip
        label={formatMetricTarget(
          targetFromDraft(formData.target, allTargets, operators),
          targetChoices
        )}
        color="primary"
        variant="filled"
      />
      {targetSummary && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          Judges <TargetSummaryText summary={targetSummary} />.
        </Typography>
      )}
    </Box>
  );

  const renderRuleConfirmation = () => (
    <Box>
      <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
        Rule
      </Typography>
      <Box sx={{ mb: 3 }}>
        <Typography
          variant="subtitle2"
          color="text.secondary"
          sx={{ fontWeight: 'medium', mb: 1 }}
        >
          Passes when
        </Typography>
        <RuleSummary draft={formData.rule} />
      </Box>
      {renderTargetConfirmation()}
    </Box>
  );

  const renderJudgeConfirmation = () => (
    <>
      {/* Evaluation Section Review */}
      <Box sx={{ mb: 5 }}>
        <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
          Evaluation Process
        </Typography>

        <Box sx={{ mb: 3 }}>
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{ fontWeight: 'medium', mb: 1 }}
          >
            Evaluation Model
          </Typography>
          <Typography sx={{ color: 'text.primary' }}>
            {models.find(model => model.id === formData.model_id)?.name ||
              'No model selected'}
          </Typography>
        </Box>

        <Box sx={{ mb: 3 }}>
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{ fontWeight: 'medium', mb: 1 }}
          >
            Evaluation Prompt
          </Typography>
          <Box
            sx={{
              p: 2,
              bgcolor: 'action.hover',
              borderRadius: theme.shape.borderRadius / 4,
              border: 1,
              borderColor: 'divider',
            }}
          >
            <Typography
              sx={{
                fontFamily: 'monospace',
                fontSize: theme.typography.body2.fontSize,
                whiteSpace: 'pre-wrap',
                color: 'text.primary',
              }}
            >
              {formData.evaluation_prompt}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ mb: 3 }}>
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{ fontWeight: 'medium', mb: 1 }}
          >
            Evaluation Steps
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {formData.evaluation_steps
              ?.filter(step => step.trim())
              .map((step, index) => (
                <Box
                  key={index}
                  sx={{
                    p: 2,
                    bgcolor: 'action.hover',
                    borderRadius: theme.shape.borderRadius / 4,
                    position: 'relative',
                    pl: 4,
                    border: 1,
                    borderColor: 'divider',
                  }}
                >
                  <Typography
                    sx={{
                      position: 'absolute',
                      left: 12,
                      top: 12,
                      color: 'text.secondary',
                      fontWeight: 'bold',
                      fontSize: theme.typography.body2.fontSize,
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
                </Box>
              ))}
          </Box>
        </Box>

        <Box>
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{ fontWeight: 'medium', mb: 1 }}
          >
            Reasoning Instructions
          </Typography>
          <Box
            sx={{
              p: 2,
              bgcolor: 'action.hover',
              borderRadius: theme.shape.borderRadius / 4,
              border: 1,
              borderColor: 'divider',
            }}
          >
            <Typography
              sx={{
                fontFamily: 'monospace',
                fontSize: theme.typography.body2.fontSize,
                whiteSpace: 'pre-wrap',
                color: 'text.primary',
              }}
            >
              {formData.reasoning}
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Result Configuration */}
      <Box>
        <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
          Result Configuration
        </Typography>

        <Box sx={{ mb: 3 }}>
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{ fontWeight: 'medium', mb: 1 }}
          >
            Score Type
          </Typography>
          <Chip
            label={
              formData.score_type === SCORE_TYPES.CATEGORICAL
                ? 'Categorical'
                : 'Numeric'
            }
            color="primary"
            variant="filled"
          />
        </Box>

        {formData.score_type === SCORE_TYPES.CATEGORICAL && (
          <>
            <Box sx={{ mb: 3 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ fontWeight: 'medium', mb: 1 }}
              >
                Categories
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {formData.categories && formData.categories.length > 0 ? (
                  formData.categories.map(category => (
                    <Chip
                      key={category}
                      label={category}
                      color="primary"
                      variant="outlined"
                    />
                  ))
                ) : (
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    No categories defined
                  </Typography>
                )}
              </Box>
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ fontWeight: 'medium', mb: 1 }}
              >
                Passing Categories
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {formData.passing_categories &&
                formData.passing_categories.length > 0 ? (
                  formData.passing_categories.map(category => (
                    <Chip
                      key={category}
                      label={category}
                      color="success"
                      variant="filled"
                    />
                  ))
                ) : (
                  <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                    No passing categories selected
                  </Typography>
                )}
              </Box>
            </Box>
          </>
        )}

        {formData.score_type === SCORE_TYPES.NUMERIC && (
          <Box sx={{ display: 'flex', gap: 3, mb: 3 }}>
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
                {formData.threshold} {formData.threshold_operator}
              </Typography>
            </Box>
          </Box>
        )}

        {renderTargetConfirmation()}

        <Box>
          <Typography
            variant="subtitle2"
            color="text.secondary"
            sx={{ fontWeight: 'medium', mb: 1 }}
          >
            Result Explanation
          </Typography>
          <Box
            sx={{
              p: 2,
              bgcolor: 'action.hover',
              borderRadius: theme.shape.borderRadius / 4,
              border: 1,
              borderColor: 'divider',
            }}
          >
            <Typography
              sx={{
                fontFamily: 'monospace',
                fontSize: theme.typography.body2.fontSize,
                whiteSpace: 'pre-wrap',
                color: 'text.primary',
              }}
            >
              {formData.explanation}
            </Typography>
          </Box>
        </Box>
      </Box>
    </>
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

  const getTitle = () => newMetricTitle(type);

  useDocumentTitle(getTitle());

  return (
    <PageLayout
      title={getTitle()}
      breadcrumbs={[
        directoryCrumb(PAGE_HEADERS.metrics),
        { label: NEW_METRIC_CRUMB },
      ]}
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
          <Box sx={{ maxWidth: theme => theme.spacing(75), width: '100%' }}>
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

            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: 2,
                mt: 4,
              }}
            >
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
    </PageLayout>
  );
}
