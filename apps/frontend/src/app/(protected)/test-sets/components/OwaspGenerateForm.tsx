'use client';

import React from 'react';
import {
  Alert,
  Box,
  Checkbox,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Slider,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  OwaspCategory,
  OwaspFramework,
  OwaspGenerateResponse,
} from '@/utils/api-client/owasp-client';
import { getApiErrorMessage } from '@/utils/error-utils';
import { readActiveProjectId } from '@/utils/active-project';
import ModelSelector from '@/components/common/ModelSelector';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import {
  drawerFieldsSx,
  drawerListChipSx,
  drawerOutlinedFieldSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';
import { TEST_TYPES, type TestTypeValue } from '@/constants/test-types';

export interface OwaspGenerateFooterState {
  onSave?: () => void;
  saveDisabled: boolean;
  saveButtonText: string;
  loading: boolean;
  closeButtonText: string;
  isComplete: boolean;
}

interface OwaspGenerateFormProps {
  /** When true, load categories and keep state alive. */
  active: boolean;
  onSuccess?: (taskIds: string[]) => void;
  onFooterChange?: (footer: OwaspGenerateFooterState) => void;
}

interface FrameworkGroup {
  framework: OwaspFramework;
  label: string;
  description: string;
}

const FRAMEWORK_GROUPS: FrameworkGroup[] = [
  {
    framework: 'llm',
    label: 'OWASP LLM Top 10',
    description:
      'Risks for applications built on large language models (LLM01–LLM10).',
  },
  {
    framework: 'agentic',
    label: 'OWASP Agentic Top 10',
    description: 'Risks for autonomous and agentic AI systems (ASI01–ASI10).',
  },
];

const EMPTY_CATEGORIES: Record<OwaspFramework, OwaspCategory[]> = {
  llm: [],
  agentic: [],
};

const MIN_TESTS = 5;
const MAX_TESTS = 100;
const DEFAULT_TESTS = 20;

const categoryKey = (framework: OwaspFramework, id: string) =>
  `${framework}:${id}`;

export default function OwaspGenerateForm({
  active,
  onSuccess,
  onFooterChange,
}: OwaspGenerateFormProps) {
  const [testSetName, setTestSetName] = React.useState('');
  const [categoriesByFramework, setCategoriesByFramework] =
    React.useState<Record<OwaspFramework, OwaspCategory[]>>(EMPTY_CATEGORIES);
  const [loadingCategories, setLoadingCategories] = React.useState(false);
  const [selectedKeys, setSelectedKeys] = React.useState<Set<string>>(
    new Set()
  );
  const [expandedFrameworks, setExpandedFrameworks] = React.useState<
    Set<OwaspFramework>
  >(new Set());
  const [numTests, setNumTests] = React.useState(DEFAULT_TESTS);
  const [testType, setTestType] = React.useState<TestTypeValue>(
    TEST_TYPES.SINGLE_TURN
  );
  const [modelId, setModelId] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string>();
  const [results, setResults] = React.useState<OwaspGenerateResponse[] | null>(
    null
  );
  const hasLoadedCategories = React.useRef(false);

  const fetchCategories = React.useCallback(async () => {
    try {
      setLoadingCategories(true);
      setError(undefined);
      const clientFactory = new ApiClientFactory();
      const owaspClient = clientFactory.getOwaspClient();
      const [llmResponse, agenticResponse] = await Promise.all([
        owaspClient.listCategories('llm'),
        owaspClient.listCategories('agentic'),
      ]);
      setCategoriesByFramework({
        llm: llmResponse.categories,
        agentic: agenticResponse.categories,
      });
      hasLoadedCategories.current = true;
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Failed to load OWASP categories'));
      setCategoriesByFramework(EMPTY_CATEGORIES);
    } finally {
      setLoadingCategories(false);
    }
  }, []);

  React.useEffect(() => {
    if (active && !hasLoadedCategories.current) {
      fetchCategories();
    }
  }, [active, fetchCategories]);

  const resetState = React.useCallback(() => {
    setTestSetName('');
    setCategoriesByFramework(EMPTY_CATEGORIES);
    setSelectedKeys(new Set());
    setExpandedFrameworks(new Set());
    setNumTests(DEFAULT_TESTS);
    setTestType(TEST_TYPES.SINGLE_TURN);
    setModelId('');
    setSubmitting(false);
    setError(undefined);
    setResults(null);
    hasLoadedCategories.current = false;
  }, []);

  React.useEffect(() => {
    if (!active) resetState();
  }, [active, resetState]);

  const isCategorySelected = (framework: OwaspFramework, id: string) =>
    selectedKeys.has(categoryKey(framework, id));

  const frameworkSelectedCount = (framework: OwaspFramework) =>
    categoriesByFramework[framework].filter(c =>
      isCategorySelected(framework, c.id)
    ).length;

  const isFrameworkFullySelected = (framework: OwaspFramework) => {
    const cats = categoriesByFramework[framework];
    return (
      cats.length > 0 && cats.every(c => isCategorySelected(framework, c.id))
    );
  };

  const isFrameworkPartiallySelected = (framework: OwaspFramework) => {
    const count = frameworkSelectedCount(framework);
    return count > 0 && count < categoriesByFramework[framework].length;
  };

  const handleCategoryToggle = (framework: OwaspFramework, id: string) => {
    setSelectedKeys(prev => {
      const next = new Set(prev);
      const k = categoryKey(framework, id);
      if (next.has(k)) {
        next.delete(k);
      } else {
        next.add(k);
      }
      return next;
    });
  };

  const handleFrameworkToggle = (framework: OwaspFramework) => {
    const cats = categoriesByFramework[framework];
    const allSelected = isFrameworkFullySelected(framework);
    setSelectedKeys(prev => {
      const next = new Set(prev);
      cats.forEach(c => {
        const k = categoryKey(framework, c.id);
        if (allSelected) {
          next.delete(k);
        } else {
          next.add(k);
        }
      });
      return next;
    });
  };

  const toggleExpand = (framework: OwaspFramework) => {
    setExpandedFrameworks(prev => {
      const next = new Set(prev);
      if (next.has(framework)) {
        next.delete(framework);
      } else {
        next.add(framework);
      }
      return next;
    });
  };

  const totalCategories =
    categoriesByFramework.llm.length + categoriesByFramework.agentic.length;
  const totalSelected = selectedKeys.size;

  // One generate call per framework that has at least one selected category —
  // each OWASP report becomes its own test set.
  const selectionsByFramework = React.useMemo(
    () =>
      FRAMEWORK_GROUPS.map(group => ({
        framework: group.framework,
        label: group.label,
        categoryIds: categoriesByFramework[group.framework]
          .filter(c => isCategorySelected(group.framework, c.id))
          .map(c => c.id),
      })).filter(selection => selection.categoryIds.length > 0),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- isCategorySelected closes over selectedKeys
    [categoriesByFramework, selectedKeys]
  );

  const handleGenerate = React.useCallback(async () => {
    if (selectionsByFramework.length === 0) {
      setError('Please select at least one risk category');
      return;
    }

    const projectId = readActiveProjectId();
    if (!projectId) {
      setError(
        'Select an active project first — its description is used as the system under test'
      );
      return;
    }

    try {
      setSubmitting(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory();
      const project = await clientFactory
        .getProjectsClient()
        .getProject(projectId);
      const purpose = project?.description?.trim();
      if (!purpose) {
        setError(
          'Add a description to the active project — it is used as the system under test'
        );
        setSubmitting(false);
        return;
      }

      const owaspClient = clientFactory.getOwaspClient();
      const multiple = selectionsByFramework.length > 1;
      const baseName = testSetName.trim();

      const responses = await Promise.all(
        selectionsByFramework.map(selection => {
          const isFullFramework =
            selection.categoryIds.length ===
            categoriesByFramework[selection.framework].length;
          const name = baseName
            ? multiple
              ? `${baseName} — ${selection.label}`
              : baseName
            : undefined;

          return owaspClient.generateTestSet({
            framework: selection.framework,
            purpose,
            categories: isFullFramework ? undefined : selection.categoryIds,
            num_tests: numTests,
            name,
            model_id: modelId || undefined,
            test_type: testType,
          });
        })
      );

      setResults(responses);
      onSuccess?.(responses.map(r => r.task_id));
    } catch (err: unknown) {
      setError(
        getApiErrorMessage(err, 'Failed to start OWASP test set generation')
      );
    } finally {
      setSubmitting(false);
    }
  }, [
    selectionsByFramework,
    testSetName,
    categoriesByFramework,
    numTests,
    modelId,
    testType,
    onSuccess,
  ]);

  const saveButtonText =
    selectionsByFramework.length > 1
      ? `Generate ${selectionsByFramework.length} Test Sets`
      : `Generate ${numTests} Tests`;

  React.useEffect(() => {
    if (!active) return;
    onFooterChange?.({
      onSave: results ? undefined : handleGenerate,
      saveDisabled: submitting || loadingCategories,
      saveButtonText,
      loading: submitting,
      closeButtonText: results ? 'Close' : 'Cancel',
      isComplete: !!results,
    });
  }, [
    active,
    results,
    handleGenerate,
    submitting,
    loadingCategories,
    saveButtonText,
    onFooterChange,
  ]);

  if (results) {
    return (
      <Stack spacing={2} alignItems="center" sx={{ py: 4 }}>
        <CheckCircleIcon sx={{ fontSize: 56, color: 'success.main' }} />
        <Typography variant="h6">Generation started!</Typography>
        <Stack spacing={0.5} sx={{ textAlign: 'center' }}>
          {results.map(result => (
            <Typography
              key={result.task_id}
              variant="body2"
              color="text.secondary"
            >
              {result.message}
            </Typography>
          ))}
        </Stack>
        <Typography variant="caption" color="text.secondary">
          The test set{results.length > 1 ? 's' : ''} will appear in your test
          sets list once generation completes.
        </Typography>
      </Stack>
    );
  }

  return (
    <>
      {error && (
        <Alert severity="error" onClose={() => setError(undefined)}>
          {error}
        </Alert>
      )}

      <Box sx={drawerSectionSx}>
        <FormSectionDivider
          headline="Risk Categories"
          descriptiveText={`Select which OWASP risks to cover (${totalSelected} of ${totalCategories} selected).`}
        />
        <Box sx={drawerFieldsSx}>
          {loadingCategories ? (
            <Stack alignItems="center" spacing={1} sx={{ p: 3 }}>
              <CircularProgress size={24} />
              <Typography variant="caption" color="text.secondary">
                Downloading and parsing the OWASP reports — first load can take
                up to a minute, later loads are instant.
              </Typography>
            </Stack>
          ) : (
            <Paper
              variant="outlined"
              sx={{
                maxHeight: 360,
                overflow: 'auto',
                bgcolor: 'background.paper',
                '& .MuiChip-root': drawerListChipSx,
              }}
            >
              <Stack divider={<Divider />}>
                {FRAMEWORK_GROUPS.map(group => {
                  const cats = categoriesByFramework[group.framework];
                  return (
                    <Box key={group.framework}>
                      <Stack
                        direction="row"
                        alignItems="center"
                        sx={{
                          px: 1.5,
                          py: 1.5,
                          cursor: 'pointer',
                          bgcolor: 'action.hover',
                        }}
                        onClick={() => toggleExpand(group.framework)}
                      >
                        <Checkbox
                          checked={isFrameworkFullySelected(group.framework)}
                          indeterminate={isFrameworkPartiallySelected(
                            group.framework
                          )}
                          disabled={submitting || cats.length === 0}
                          onClick={e => e.stopPropagation()}
                          onChange={() =>
                            handleFrameworkToggle(group.framework)
                          }
                        />
                        <Stack flex={1} spacing={0.25} minWidth={0}>
                          <Stack
                            direction="row"
                            alignItems="center"
                            spacing={1}
                          >
                            <Typography variant="bodyMBold">
                              {group.label}
                            </Typography>
                            <Chip
                              label={`${frameworkSelectedCount(group.framework)}/${cats.length}`}
                              size="small"
                              variant="outlined"
                            />
                          </Stack>
                          <Typography variant="caption" color="text.secondary">
                            {group.description}
                          </Typography>
                        </Stack>
                        <IconButton size="small">
                          <ExpandMoreIcon
                            sx={theme => ({
                              transform: expandedFrameworks.has(group.framework)
                                ? 'rotate(180deg)'
                                : 'none',
                              transition: theme.transitions.create(
                                'transform',
                                {
                                  duration: theme.transitions.duration.short,
                                }
                              ),
                            })}
                          />
                        </IconButton>
                      </Stack>

                      <Collapse in={expandedFrameworks.has(group.framework)}>
                        <Stack divider={<Divider />}>
                          {cats.map(category => (
                            <Stack
                              key={category.id}
                              direction="row"
                              alignItems="flex-start"
                              sx={{
                                pl: 6,
                                pr: 1.5,
                                py: 1,
                                cursor: 'pointer',
                              }}
                              onClick={() =>
                                handleCategoryToggle(
                                  group.framework,
                                  category.id
                                )
                              }
                            >
                              <Checkbox
                                size="small"
                                checked={isCategorySelected(
                                  group.framework,
                                  category.id
                                )}
                                disabled={submitting}
                                onClick={e => e.stopPropagation()}
                                onChange={() =>
                                  handleCategoryToggle(
                                    group.framework,
                                    category.id
                                  )
                                }
                                sx={{ pt: 0.25 }}
                              />
                              <Stack flex={1} spacing={0.25} minWidth={0}>
                                <Typography variant="bodyMBold">
                                  {category.id.toUpperCase()}: {category.name}
                                </Typography>
                                {category.description ? (
                                  <Typography
                                    variant="caption"
                                    color="text.secondary"
                                    sx={{
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                      display: '-webkit-box',
                                      WebkitLineClamp: 2,
                                      WebkitBoxOrient: 'vertical',
                                    }}
                                  >
                                    {category.description}
                                  </Typography>
                                ) : null}
                              </Stack>
                            </Stack>
                          ))}
                        </Stack>
                      </Collapse>
                    </Box>
                  );
                })}
              </Stack>
            </Paper>
          )}
        </Box>
      </Box>

      <Box sx={drawerSectionSx}>
        <FormSectionDivider
          headline="Advanced Options"
          descriptiveText="Optional overrides — defaults work well for most generations."
        />
        <Box sx={drawerFieldsSx}>
          <ModelSelector
            value={modelId}
            onChange={setModelId}
            label="Generation Model"
            purpose="generation"
            disabled={submitting}
            compact
            hideHelperText
            fieldSx={drawerOutlinedFieldSx}
            enabled={active}
          />

          <FormControl fullWidth sx={drawerOutlinedFieldSx}>
            <InputLabel shrink>Test Type</InputLabel>
            <Select
              value={testType}
              onChange={e => setTestType(e.target.value as TestTypeValue)}
              label="Test Type"
              disabled={submitting}
            >
              <MenuItem value={TEST_TYPES.SINGLE_TURN}>Single-Turn</MenuItem>
              <MenuItem value={TEST_TYPES.MULTI_TURN}>Multi-Turn</MenuItem>
            </Select>
          </FormControl>

          <Box>
            <Stack direction="row" justifyContent="space-between" mb={1}>
              <Typography
                sx={{
                  fontSize: 12,
                  lineHeight: '18px',
                  color: theme => theme.palette.greyscale.subtitle,
                }}
              >
                Number of Tests
                {selectionsByFramework.length > 1 ? ' (per test set)' : ''}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {numTests} tests
              </Typography>
            </Stack>
            <Slider
              value={numTests}
              onChange={(_e, value) => setNumTests(value as number)}
              min={MIN_TESTS}
              max={MAX_TESTS}
              step={1}
              valueLabelDisplay="auto"
              disabled={submitting}
            />
          </Box>

          <TextField
            label="Test Set Name"
            placeholder="Defaults to the OWASP report name and project description"
            value={testSetName}
            onChange={e => setTestSetName(e.target.value)}
            fullWidth
            disabled={submitting}
            sx={drawerOutlinedFieldSx}
          />
        </Box>
      </Box>
    </>
  );
}
