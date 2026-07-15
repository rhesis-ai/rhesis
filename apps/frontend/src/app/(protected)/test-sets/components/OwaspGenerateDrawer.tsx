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
  IconButton,
  Paper,
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
import BaseDrawer from '@/components/common/BaseDrawer';
import ModelSelector from '@/components/common/ModelSelector';
import { OwaspIcon } from '@/components/icons';

interface OwaspGenerateDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  onSuccess?: (taskIds: string[]) => void;
}

interface FrameworkGroup {
  framework: OwaspFramework;
  label: string;
}

const FRAMEWORK_GROUPS: FrameworkGroup[] = [
  { framework: 'llm', label: 'OWASP LLM Top 10' },
  { framework: 'agentic', label: 'OWASP Agentic Top 10' },
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

export default function OwaspGenerateDrawer({
  open,
  onClose,
  sessionToken,
  onSuccess,
}: OwaspGenerateDrawerProps) {
  const [testSetName, setTestSetName] = React.useState('');
  const [purpose, setPurpose] = React.useState('');
  const [categoriesByFramework, setCategoriesByFramework] =
    React.useState<Record<OwaspFramework, OwaspCategory[]>>(EMPTY_CATEGORIES);
  const [loadingCategories, setLoadingCategories] = React.useState(false);
  const [selectedKeys, setSelectedKeys] = React.useState<Set<string>>(
    new Set()
  );
  const [expandedFrameworks, setExpandedFrameworks] = React.useState<
    Set<OwaspFramework>
  >(new Set(FRAMEWORK_GROUPS.map(g => g.framework)));
  const [numTests, setNumTests] = React.useState(DEFAULT_TESTS);
  const [modelId, setModelId] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string>();
  const [results, setResults] = React.useState<OwaspGenerateResponse[] | null>(
    null
  );

  const fetchCategories = React.useCallback(async () => {
    try {
      setLoadingCategories(true);
      setError(undefined);
      const clientFactory = new ApiClientFactory(sessionToken);
      const owaspClient = clientFactory.getOwaspClient();
      const [llmResponse, agenticResponse] = await Promise.all([
        owaspClient.listCategories('llm'),
        owaspClient.listCategories('agentic'),
      ]);
      setCategoriesByFramework({
        llm: llmResponse.categories,
        agentic: agenticResponse.categories,
      });
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Failed to load OWASP categories'));
      setCategoriesByFramework(EMPTY_CATEGORIES);
    } finally {
      setLoadingCategories(false);
    }
  }, [sessionToken]);

  React.useEffect(() => {
    if (open) fetchCategories();
  }, [open, fetchCategories]);

  // Prefill "System under test" from the active project's description —
  // only when the field is still empty, so it never clobbers a user edit.
  React.useEffect(() => {
    if (!open) return;
    const projectId = readActiveProjectId();
    if (!projectId) return;

    const clientFactory = new ApiClientFactory(sessionToken);
    clientFactory
      .getProjectsClient()
      .getProject(projectId)
      .then(project => {
        const description = project?.description?.trim();
        if (description) {
          setPurpose(prev => prev || description);
        }
      })
      .catch(() => {});
  }, [open, sessionToken]);

  const resetState = React.useCallback(() => {
    setTestSetName('');
    setPurpose('');
    setCategoriesByFramework(EMPTY_CATEGORIES);
    setSelectedKeys(new Set());
    setExpandedFrameworks(new Set(FRAMEWORK_GROUPS.map(g => g.framework)));
    setNumTests(DEFAULT_TESTS);
    setModelId('');
    setSubmitting(false);
    setError(undefined);
    setResults(null);
  }, []);

  React.useEffect(() => {
    if (!open) resetState();
  }, [open, resetState]);

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

  const handleSelectAll = () => {
    if (totalSelected === totalCategories && totalCategories > 0) {
      setSelectedKeys(new Set());
    } else {
      const all = new Set<string>();
      FRAMEWORK_GROUPS.forEach(group => {
        categoriesByFramework[group.framework].forEach(c =>
          all.add(categoryKey(group.framework, c.id))
        );
      });
      setSelectedKeys(all);
    }
  };

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [categoriesByFramework, selectedKeys]
  );

  const handleGenerate = async () => {
    if (!purpose.trim()) {
      setError('Please describe what your system under test does');
      return;
    }
    if (selectionsByFramework.length === 0) {
      setError('Please select at least one risk category');
      return;
    }

    try {
      setSubmitting(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
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
            purpose: purpose.trim(),
            categories: isFullFramework ? undefined : selection.categoryIds,
            num_tests: numTests,
            name,
            model_id: modelId || undefined,
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
  };

  const handleClose = () => {
    onClose();
  };

  const saveButtonText =
    selectionsByFramework.length > 1
      ? `Generate ${selectionsByFramework.length} Test Sets`
      : `Generate ${numTests} Tests`;

  return (
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title="Generate from OWASP"
      titleIcon={<OwaspIcon sx={{ fontSize: 28 }} />}
      width={640}
      closeButtonText={results ? 'Close' : 'Cancel'}
      loading={submitting}
      onSave={results ? undefined : handleGenerate}
      saveDisabled={submitting || loadingCategories}
      saveButtonText={saveButtonText}
    >
      <Stack spacing={3} sx={{ flex: 1, minHeight: 0 }}>
        {error && (
          <Alert severity="error" onClose={() => setError(undefined)}>
            {error}
          </Alert>
        )}

        {results ? (
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
              The test set{results.length > 1 ? 's' : ''} will appear in your
              test sets list once generation completes.
            </Typography>
          </Stack>
        ) : (
          <>
            <TextField
              label="Test Set Name (optional)"
              placeholder="Defaults to the OWASP report name and system under test"
              value={testSetName}
              onChange={e => setTestSetName(e.target.value)}
              fullWidth
              size="small"
              disabled={submitting}
            />

            <TextField
              label="System under test"
              placeholder="e.g. Customer service chatbot for a retail bank with access to account balances and transfers"
              value={purpose}
              onChange={e => setPurpose(e.target.value)}
              fullWidth
              multiline
              rows={3}
              disabled={submitting}
              helperText="Describe what the system does — attacks are tailored to this description."
            />

            <Box>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                mb={1}
              >
                <Typography variant="subtitle2">
                  Risk Categories ({totalSelected} of {totalCategories}{' '}
                  selected)
                </Typography>
                <Chip
                  size="small"
                  label={
                    totalSelected === totalCategories && totalCategories > 0
                      ? 'Deselect all'
                      : 'Select all'
                  }
                  onClick={handleSelectAll}
                  disabled={loadingCategories || totalCategories === 0}
                  variant="outlined"
                />
              </Stack>

              {loadingCategories ? (
                <Stack alignItems="center" spacing={1} sx={{ p: 3 }}>
                  <CircularProgress size={24} />
                  <Typography variant="caption" color="text.secondary">
                    Downloading and parsing the OWASP reports — first load can
                    take up to a minute, later loads are instant.
                  </Typography>
                </Stack>
              ) : (
                <Paper
                  variant="outlined"
                  sx={{ maxHeight: 320, overflow: 'auto' }}
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
                              p: 1,
                              cursor: 'pointer',
                              bgcolor: 'action.hover',
                            }}
                            onClick={() => toggleExpand(group.framework)}
                          >
                            <Checkbox
                              checked={isFrameworkFullySelected(
                                group.framework
                              )}
                              indeterminate={isFrameworkPartiallySelected(
                                group.framework
                              )}
                              disabled={submitting || cats.length === 0}
                              onClick={e => e.stopPropagation()}
                              onChange={() =>
                                handleFrameworkToggle(group.framework)
                              }
                            />
                            <Stack
                              flex={1}
                              direction="row"
                              alignItems="center"
                              spacing={1}
                            >
                              <Typography variant="body1" fontWeight="medium">
                                {group.label}
                              </Typography>
                              <Chip
                                label={`${frameworkSelectedCount(group.framework)}/${cats.length}`}
                                size="small"
                                variant="outlined"
                              />
                            </Stack>
                            <IconButton size="small">
                              <ExpandMoreIcon
                                sx={theme => ({
                                  transform: expandedFrameworks.has(
                                    group.framework
                                  )
                                    ? 'rotate(180deg)'
                                    : 'none',
                                  transition: theme.transitions.create(
                                    'transform',
                                    {
                                      duration:
                                        theme.transitions.duration.short,
                                    }
                                  ),
                                })}
                              />
                            </IconButton>
                          </Stack>

                          <Collapse
                            in={expandedFrameworks.has(group.framework)}
                          >
                            <Stack sx={{ pl: 4 }} divider={<Divider />}>
                              {cats.map(category => (
                                <Stack
                                  key={category.id}
                                  direction="row"
                                  alignItems="center"
                                  sx={{ p: 0.5, pl: 2, cursor: 'pointer' }}
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
                                  />
                                  <Typography variant="body2">
                                    {category.id.toUpperCase()}: {category.name}
                                  </Typography>
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

            <Box>
              <Stack direction="row" justifyContent="space-between" mb={1}>
                <Typography variant="subtitle2">
                  Number of Tests{' '}
                  {selectionsByFramework.length > 1 && '(per test set)'}
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

            <ModelSelector
              sessionToken={sessionToken}
              value={modelId}
              onChange={setModelId}
              label="Generation Model"
              purpose="generation"
              disabled={submitting}
              compact
            />
          </>
        )}
      </Stack>
    </BaseDrawer>
  );
}
