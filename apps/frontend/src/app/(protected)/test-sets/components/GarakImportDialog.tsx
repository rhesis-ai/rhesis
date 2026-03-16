'use client';

import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Stack,
  Checkbox,
  Alert,
  CircularProgress,
  Box,
  Chip,
  Divider,
  Paper,
  IconButton,
  Collapse,
  LinearProgress,
  Tooltip,
  alpha,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Security as SecurityIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  AutoAwesome as AutoAwesomeIcon,
} from '@mui/icons-material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  GarakProbeModule,
  GarakProbeClass,
  GarakImportPreviewResponse,
  GarakProbeSelection,
  GarakProbePreview,
  GarakGenerateResponse,
} from '@/utils/api-client/garak-client';

interface GarakImportDialogProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  onSuccess?: (testSetIds: string[]) => void;
}

export default function GarakImportDialog({
  open,
  onClose,
  sessionToken,
  onSuccess,
}: GarakImportDialogProps) {
  const [loading, setLoading] = React.useState(false);
  const [loadingModules, setLoadingModules] = React.useState(false);
  const [importing, setImporting] = React.useState(false);
  const [preparingImport, setPreparingImport] = React.useState(false);
  const [error, setError] = React.useState<string>();
  const [modules, setModules] = React.useState<GarakProbeModule[]>([]);
  // Track selected probes by full_name (e.g., "dan.Dan_11_0")
  const [selectedProbes, setSelectedProbes] = React.useState<Set<string>>(
    new Set()
  );
  const [preview, setPreview] =
    React.useState<GarakImportPreviewResponse | null>(null);
  const [garakVersion, setGarakVersion] = React.useState<string>('');
  const [expandedModules, setExpandedModules] = React.useState<Set<string>>(
    new Set()
  );
  // Progress tracking during import
  const [importProgress, setImportProgress] = React.useState<{
    phase: 'static' | 'dynamic' | 'done';
    currentProbeIndex: number;
    totalProbes: number;
    currentTestCount: number;
    totalTests: number;
    currentProbe: GarakProbePreview | null;
    staticImported: number;
    dynamicLaunched: number;
    dynamicTotal: number;
    dynamicResults: GarakGenerateResponse[];
    isComplete: boolean;
  } | null>(null);

  const fetchModules = React.useCallback(async () => {
    try {
      setLoadingModules(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();

      const response = await garakClient.listProbeModules();
      setModules(response.modules);
      setGarakVersion(response.garak_version);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to load Garak modules'
      );
    } finally {
      setLoadingModules(false);
    }
  }, [sessionToken]);

  // Fetch available modules when dialog opens
  React.useEffect(() => {
    if (open && modules.length === 0) {
      fetchModules();
    }
  }, [open, fetchModules, modules.length]);

  // Get all probes from a module
  const getModuleProbes = (module: GarakProbeModule): GarakProbeClass[] => {
    return module.probes || [];
  };

  // Check if all probes in a module are selected
  const isModuleFullySelected = (module: GarakProbeModule): boolean => {
    const probes = getModuleProbes(module);
    return (
      probes.length > 0 && probes.every(p => selectedProbes.has(p.full_name))
    );
  };

  // Check if some probes in a module are selected
  const isModulePartiallySelected = (module: GarakProbeModule): boolean => {
    const probes = getModuleProbes(module);
    const selectedCount = probes.filter(p =>
      selectedProbes.has(p.full_name)
    ).length;
    return selectedCount > 0 && selectedCount < probes.length;
  };

  // Toggle individual probe selection
  const handleProbeToggle = (probe: GarakProbeClass) => {
    const newSelected = new Set(selectedProbes);
    if (newSelected.has(probe.full_name)) {
      newSelected.delete(probe.full_name);
    } else {
      newSelected.add(probe.full_name);
    }
    setSelectedProbes(newSelected);
    setPreview(null);
  };

  // Toggle all probes in a module
  const handleModuleToggle = (module: GarakProbeModule) => {
    const probes = getModuleProbes(module);
    const newSelected = new Set(selectedProbes);

    if (isModuleFullySelected(module)) {
      // Deselect all probes in module
      probes.forEach(p => newSelected.delete(p.full_name));
    } else {
      // Select all probes in module
      probes.forEach(p => newSelected.add(p.full_name));
    }

    setSelectedProbes(newSelected);
    setPreview(null);
  };

  const handleSelectAll = () => {
    const allProbes = modules.flatMap(m => getModuleProbes(m));
    if (selectedProbes.size === allProbes.length) {
      setSelectedProbes(new Set());
    } else {
      setSelectedProbes(new Set(allProbes.map(p => p.full_name)));
    }
    setPreview(null);
  };

  const getSelectedProbeObjects = () => {
    const staticProbes: GarakProbeClass[] = [];
    const dynamicProbes: GarakProbeClass[] = [];
    for (const module of modules) {
      for (const probe of getModuleProbes(module)) {
        if (selectedProbes.has(probe.full_name)) {
          if (probe.is_dynamic) {
            dynamicProbes.push(probe);
          } else {
            staticProbes.push(probe);
          }
        }
      }
    }
    return { staticProbes, dynamicProbes };
  };

  const buildProbeSelections = (
    probes?: GarakProbeClass[]
  ): GarakProbeSelection[] => {
    const source =
      probes ??
      modules
        .flatMap(m => getModuleProbes(m))
        .filter(p => selectedProbes.has(p.full_name));
    return source.map(p => ({
      module_name: p.module_name,
      class_name: p.class_name,
    }));
  };

  const handlePreview = async () => {
    if (selectedProbes.size === 0) {
      setError('Please select at least one probe');
      return;
    }

    try {
      setLoading(true);
      setError(undefined);

      const { staticProbes, dynamicProbes } = getSelectedProbeObjects();
      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();

      if (staticProbes.length > 0) {
        const previewResponse = await garakClient.previewImport({
          probes: buildProbeSelections(staticProbes),
          name_prefix: 'Garak',
        });
        setPreview(previewResponse);
      } else {
        setPreview({
          garak_version: garakVersion,
          total_test_sets: 0,
          total_tests: 0,
          detector_count: 0,
          detectors: [],
          probes: [],
        });
      }

      setDynamicPreviewProbes(dynamicProbes);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to preview import');
    } finally {
      setLoading(false);
    }
  };

  const [dynamicPreviewProbes, setDynamicPreviewProbes] = React.useState<
    GarakProbeClass[]
  >([]);

  const handleImport = async () => {
    if (selectedProbes.size === 0) {
      setError('Please select at least one probe');
      return;
    }

    const { staticProbes, dynamicProbes } = getSelectedProbeObjects();
    const totalProbes = staticProbes.length + dynamicProbes.length;

    if (totalProbes === 0) return;

    try {
      setImporting(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();
      const createdTestSetIds: string[] = [];

      // --- Phase 1: Import static probes ---
      if (staticProbes.length > 0) {
        let previewData = preview;
        if (!previewData || previewData.probes.length === 0) {
          setPreparingImport(true);
          previewData = await garakClient.previewImport({
            probes: buildProbeSelections(staticProbes),
            name_prefix: 'Garak',
          });
          setPreview(previewData);
          setPreparingImport(false);
        }

        const cumulativeTestCounts = previewData.probes.reduce<number[]>(
          (acc, probe, idx) => {
            const prevCount = idx > 0 ? acc[idx - 1] : 0;
            acc.push(prevCount + probe.prompt_count);
            return acc;
          },
          []
        );

        setImportProgress({
          phase: 'static',
          currentProbeIndex: 0,
          totalProbes,
          currentTestCount: 0,
          totalTests: previewData.total_tests,
          currentProbe: previewData.probes[0] || null,
          staticImported: 0,
          dynamicLaunched: 0,
          dynamicTotal: dynamicProbes.length,
          dynamicResults: [],
          isComplete: false,
        });

        const maxSimulated = Math.floor(previewData.total_tests * 0.95);
        const progressInterval = setInterval(() => {
          setImportProgress(prev => {
            if (
              !prev ||
              prev.phase !== 'static' ||
              prev.isComplete ||
              !previewData
            )
              return prev;
            const testsPerInterval = Math.max(
              1,
              Math.ceil(previewData.total_tests / 60)
            );
            const nextTestCount = Math.min(
              prev.currentTestCount + testsPerInterval,
              maxSimulated
            );
            let probeIndex = prev.currentProbeIndex;
            while (
              probeIndex < cumulativeTestCounts.length - 1 &&
              nextTestCount >= cumulativeTestCounts[probeIndex]
            ) {
              probeIndex++;
            }
            return {
              ...prev,
              currentProbeIndex: probeIndex,
              currentTestCount: nextTestCount,
              currentProbe: previewData.probes[probeIndex] || prev.currentProbe,
            };
          });
        }, 500);

        const response = await garakClient.importProbes({
          probes: buildProbeSelections(staticProbes),
          name_prefix: 'Garak',
        });

        clearInterval(progressInterval);
        createdTestSetIds.push(...response.test_sets.map(ts => ts.test_set_id));

        setImportProgress(prev =>
          prev
            ? {
                ...prev,
                currentTestCount: previewData!.total_tests,
                staticImported: staticProbes.length,
              }
            : prev
        );
      }

      // --- Phase 2: Launch dynamic probe generation ---
      if (dynamicProbes.length > 0) {
        setImportProgress(prev => ({
          phase: 'dynamic',
          currentProbeIndex: prev ? prev.staticImported : 0,
          totalProbes,
          currentTestCount: prev?.currentTestCount ?? 0,
          totalTests: prev?.totalTests ?? 0,
          currentProbe: null,
          staticImported: prev?.staticImported ?? 0,
          dynamicLaunched: 0,
          dynamicTotal: dynamicProbes.length,
          dynamicResults: [],
          isComplete: false,
        }));

        const dynamicResults: GarakGenerateResponse[] = [];

        for (let i = 0; i < dynamicProbes.length; i++) {
          const probe = dynamicProbes[i];
          setImportProgress(prev =>
            prev
              ? {
                  ...prev,
                  currentProbeIndex: (prev.staticImported || 0) + i,
                  currentProbe: {
                    module_name: probe.module_name,
                    class_name: probe.class_name,
                    full_name: probe.full_name,
                    test_set_name: `Garak Dynamic: ${probe.full_name}`,
                    prompt_count: 0,
                    detector: probe.detector,
                  },
                }
              : prev
          );

          const result = await garakClient.generateDynamicProbe({
            module_name: probe.module_name,
            class_name: probe.class_name,
          });
          dynamicResults.push(result);

          setImportProgress(prev =>
            prev
              ? {
                  ...prev,
                  dynamicLaunched: i + 1,
                  dynamicResults: [...dynamicResults],
                }
              : prev
          );
        }
      }

      // --- Done ---
      setImportProgress(prev =>
        prev
          ? {
              ...prev,
              phase: 'done',
              currentProbe: null,
              isComplete: true,
            }
          : prev
      );

      const hasDynamic = dynamicProbes.length > 0;
      if (!hasDynamic) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }

      if (createdTestSetIds.length > 0) {
        onSuccess?.(createdTestSetIds);
      }
      if (!hasDynamic) {
        handleClose();
      }
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to import Garak probes'
      );
      setImportProgress(null);
    } finally {
      setImporting(false);
      setPreparingImport(false);
    }
  };

  const handleClose = () => {
    onClose();
  };

  const resetState = () => {
    setSelectedProbes(new Set());
    setPreview(null);
    setError(undefined);
    setImportProgress(null);
    setPreparingImport(false);
    setDynamicPreviewProbes([]);
  };

  const toggleModuleExpand = (moduleName: string) => {
    const newExpanded = new Set(expandedModules);
    if (newExpanded.has(moduleName)) {
      newExpanded.delete(moduleName);
    } else {
      newExpanded.add(moduleName);
    }
    setExpandedModules(newExpanded);
  };

  // Count selected probes for display
  const allProbesCount = modules.flatMap(m => getModuleProbes(m)).length;

  const isCompleteWithDynamic =
    !!importProgress?.isComplete && importProgress.dynamicResults.length > 0;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      TransitionProps={{ onExited: resetState }}
    >
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={1}>
          <SecurityIcon color="primary" />
          <Typography variant="h6">Import from Garak</Typography>
          {garakVersion && (
            <Chip label={`v${garakVersion}`} size="small" variant="outlined" />
          )}
        </Stack>
      </DialogTitle>

      <DialogContent dividers>
        <Stack spacing={3}>
          {error && (
            <Alert severity="error" onClose={() => setError(undefined)}>
              {error}
            </Alert>
          )}

          {/* Probe Selection - Hide when importing or showing completion */}
          {!importing && !isCompleteWithDynamic && (
            <Box>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
                mb={1}
              >
                <Typography variant="subtitle1" fontWeight="medium">
                  Select Probes ({selectedProbes.size} of {allProbesCount}{' '}
                  selected)
                </Typography>
                <Stack direction="row" spacing={1}>
                  <Button
                    size="small"
                    onClick={handleSelectAll}
                    disabled={loadingModules}
                  >
                    {selectedProbes.size === allProbesCount
                      ? 'Deselect All'
                      : 'Select All'}
                  </Button>
                  <IconButton
                    size="small"
                    onClick={fetchModules}
                    disabled={loadingModules}
                  >
                    <RefreshIcon />
                  </IconButton>
                </Stack>
              </Stack>

              {loadingModules ? (
                <Box display="flex" justifyContent="center" p={4}>
                  <CircularProgress />
                </Box>
              ) : (
                <Paper
                  variant="outlined"
                  sx={{
                    maxHeight: theme => theme.spacing(50),
                    overflow: 'auto',
                  }}
                >
                  <Stack divider={<Divider />}>
                    {modules.map(module => (
                      <Box key={module.name}>
                        {/* Module Header */}
                        <Stack
                          direction="row"
                          alignItems="center"
                          sx={{
                            p: 1.5,
                            cursor: 'pointer',
                            bgcolor: 'action.hover',
                          }}
                          onClick={() => toggleModuleExpand(module.name)}
                        >
                          <Checkbox
                            checked={isModuleFullySelected(module)}
                            indeterminate={isModulePartiallySelected(module)}
                            onClick={e => e.stopPropagation()}
                            onChange={() => handleModuleToggle(module)}
                          />
                          <Stack flex={1} spacing={0.5}>
                            <Stack
                              direction="row"
                              alignItems="center"
                              spacing={1}
                            >
                              <Typography variant="body1" fontWeight="medium">
                                {module.name}
                              </Typography>
                              <Chip
                                label={`${module.probe_count} probes`}
                                size="small"
                                variant="outlined"
                              />
                              {module.has_dynamic_probes &&
                              module.total_prompt_count === 0 ? (
                                <Tooltip title="Prompts are generated at runtime using your LLM">
                                  <Chip
                                    icon={<AutoAwesomeIcon />}
                                    label="Dynamic"
                                    size="small"
                                    color="warning"
                                    variant="outlined"
                                  />
                                </Tooltip>
                              ) : module.has_dynamic_probes ? (
                                <>
                                  <Chip
                                    label={`${module.total_prompt_count} prompts`}
                                    size="small"
                                    variant="outlined"
                                  />
                                  <Tooltip title="Some probes generate prompts at runtime using your LLM">
                                    <Chip
                                      icon={<AutoAwesomeIcon />}
                                      label="+ Dynamic"
                                      size="small"
                                      color="warning"
                                      variant="outlined"
                                    />
                                  </Tooltip>
                                </>
                              ) : (
                                <Chip
                                  label={`${module.total_prompt_count} prompts`}
                                  size="small"
                                  variant="outlined"
                                />
                              )}
                            </Stack>
                            <Typography variant="body2" color="text.secondary">
                              {module.description}
                            </Typography>
                            <Stack
                              direction="row"
                              spacing={0.5}
                              flexWrap="wrap"
                            >
                              <Chip
                                label={module.rhesis_category}
                                size="small"
                                color="primary"
                                variant="outlined"
                              />
                              <Chip
                                label={module.rhesis_topic}
                                size="small"
                                color="secondary"
                                variant="outlined"
                              />
                            </Stack>
                          </Stack>
                          <IconButton size="small">
                            <ExpandMoreIcon
                              sx={theme => ({
                                transform: expandedModules.has(module.name)
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

                        {/* Individual Probes */}
                        <Collapse in={expandedModules.has(module.name)}>
                          <Stack sx={{ pl: 4 }} divider={<Divider />}>
                            {getModuleProbes(module).map(probe => (
                              <Stack
                                key={probe.full_name}
                                direction="row"
                                alignItems="center"
                                sx={{ p: 1, pl: 2, cursor: 'pointer' }}
                                onClick={() => handleProbeToggle(probe)}
                              >
                                <Checkbox
                                  size="small"
                                  checked={selectedProbes.has(probe.full_name)}
                                  onClick={e => e.stopPropagation()}
                                  onChange={() => handleProbeToggle(probe)}
                                />
                                <Stack flex={1} spacing={0.25}>
                                  <Stack
                                    direction="row"
                                    alignItems="center"
                                    spacing={1}
                                  >
                                    <Typography
                                      variant="body2"
                                      fontWeight="medium"
                                    >
                                      {probe.class_name}
                                    </Typography>
                                    {probe.is_dynamic ? (
                                      <Tooltip title="Prompts will be generated at runtime using your LLM">
                                        <Chip
                                          icon={<AutoAwesomeIcon />}
                                          label="Dynamic"
                                          size="small"
                                          color="warning"
                                          variant="outlined"
                                          sx={{
                                            height: theme => theme.spacing(2.5),
                                          }}
                                        />
                                      </Tooltip>
                                    ) : (
                                      <Chip
                                        label={`${probe.prompt_count} tests`}
                                        size="small"
                                        variant="outlined"
                                        sx={{
                                          height: theme => theme.spacing(2.5),
                                        }}
                                      />
                                    )}
                                  </Stack>
                                  <Typography
                                    variant="caption"
                                    color="text.secondary"
                                    sx={{
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                      whiteSpace: 'nowrap',
                                      maxWidth: theme => theme.spacing(50),
                                    }}
                                  >
                                    {probe.description}
                                  </Typography>
                                </Stack>
                              </Stack>
                            ))}
                          </Stack>
                        </Collapse>
                      </Box>
                    ))}
                  </Stack>
                </Paper>
              )}
            </Box>
          )}

          {/* Import Progress */}
          {(importing || isCompleteWithDynamic) && importProgress && (
            <Paper
              elevation={0}
              sx={theme => ({
                p: 3,
                bgcolor: alpha(theme.palette.primary.main, 0.08),
                border: 1,
                borderColor: alpha(theme.palette.primary.main, 0.24),
                borderRadius: 2,
              })}
            >
              <Stack spacing={2}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  {!importProgress.isComplete && <CircularProgress size={20} />}
                  <Typography variant="subtitle1" fontWeight="medium">
                    {importProgress.phase === 'static' &&
                      'Importing static probes...'}
                    {importProgress.phase === 'dynamic' &&
                      'Generating dynamic probes...'}
                    {importProgress.phase === 'done' && 'Complete'}
                  </Typography>
                </Stack>

                {importProgress.phase === 'static' &&
                  importProgress.totalTests > 0 && (
                    <Box>
                      <Stack
                        direction="row"
                        justifyContent="space-between"
                        mb={0.5}
                      >
                        <Typography variant="body2" color="text.secondary">
                          {importProgress.currentTestCount.toLocaleString()} of{' '}
                          {importProgress.totalTests.toLocaleString()} tests
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {Math.min(
                            importProgress.currentProbeIndex + 1,
                            importProgress.totalProbes
                          )}{' '}
                          of {importProgress.totalProbes} probes
                        </Typography>
                      </Stack>
                      <LinearProgress
                        variant="determinate"
                        value={
                          (importProgress.currentTestCount /
                            importProgress.totalTests) *
                          100
                        }
                        sx={theme => ({
                          height: theme.spacing(1),
                          borderRadius: theme.spacing(0.5),
                        })}
                      />
                    </Box>
                  )}

                {importProgress.phase === 'dynamic' && (
                  <Box>
                    <Stack
                      direction="row"
                      justifyContent="space-between"
                      mb={0.5}
                    >
                      <Typography variant="body2" color="text.secondary">
                        Launching LLM generation tasks...
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {importProgress.dynamicLaunched} of{' '}
                        {importProgress.dynamicTotal} probes
                      </Typography>
                    </Stack>
                    <LinearProgress
                      variant="determinate"
                      value={
                        (importProgress.dynamicLaunched /
                          importProgress.dynamicTotal) *
                        100
                      }
                      sx={theme => ({
                        height: theme.spacing(1),
                        borderRadius: theme.spacing(0.5),
                      })}
                      color="warning"
                    />
                  </Box>
                )}

                {importProgress.currentProbe && (
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Stack spacing={1}>
                      <Stack direction="row" alignItems="center" spacing={1}>
                        {importProgress.phase === 'dynamic' ? (
                          <AutoAwesomeIcon fontSize="small" color="warning" />
                        ) : (
                          <SecurityIcon fontSize="small" color="primary" />
                        )}
                        <Typography variant="body1" fontWeight="medium">
                          {importProgress.currentProbe.test_set_name}
                        </Typography>
                      </Stack>
                      <Stack direction="row" spacing={2}>
                        {importProgress.phase === 'dynamic' ? (
                          <Chip
                            icon={<AutoAwesomeIcon />}
                            label="Generating via LLM"
                            size="small"
                            color="warning"
                            variant="outlined"
                          />
                        ) : (
                          <Chip
                            label={`${importProgress.currentProbe.prompt_count} prompts`}
                            size="small"
                            variant="outlined"
                          />
                        )}
                        {importProgress.currentProbe.detector && (
                          <Chip
                            label={importProgress.currentProbe.detector}
                            size="small"
                            color="secondary"
                            variant="outlined"
                          />
                        )}
                      </Stack>
                      <Typography variant="caption" color="text.secondary">
                        Module: {importProgress.currentProbe.module_name}
                      </Typography>
                    </Stack>
                  </Paper>
                )}

                {importProgress.isComplete && (
                  <Stack spacing={1}>
                    <Stack
                      direction="row"
                      alignItems="center"
                      spacing={1}
                      sx={{ color: 'success.main' }}
                    >
                      <CheckCircleIcon />
                      <Typography variant="body1" fontWeight="medium">
                        Import complete!
                      </Typography>
                    </Stack>
                    {importProgress.staticImported > 0 && (
                      <Stack spacing={0.5}>
                        <Typography variant="body2" color="text.secondary">
                          {importProgress.staticImported} static probe
                          {importProgress.staticImported !== 1 ? 's' : ''}{' '}
                          imported:
                        </Typography>
                        {preview?.probes.map(p => (
                          <Typography
                            key={p.full_name}
                            variant="body2"
                            color="text.secondary"
                            sx={{ pl: 2 }}
                          >
                            • {p.test_set_name} ({p.prompt_count} tests)
                          </Typography>
                        ))}
                      </Stack>
                    )}
                    {importProgress.dynamicResults.length > 0 && (
                      <Stack spacing={0.5}>
                        <Typography variant="body2" color="text.secondary">
                          {importProgress.dynamicResults.length} dynamic probe
                          {importProgress.dynamicResults.length !== 1
                            ? 's'
                            : ''}{' '}
                          — generation started in background:
                        </Typography>
                        {importProgress.dynamicResults.map(result => (
                          <Typography
                            key={result.task_id}
                            variant="body2"
                            color="text.secondary"
                            sx={{ pl: 2 }}
                          >
                            • {result.probe_full_name}
                          </Typography>
                        ))}
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ mt: 0.5 }}
                        >
                          Once generation completes, the test sets will appear
                          in your test sets list.
                        </Typography>
                      </Stack>
                    )}
                  </Stack>
                )}
              </Stack>
            </Paper>
          )}

          {/* Preview */}
          {preview && !importing && !isCompleteWithDynamic && (
            <Alert severity="info" icon={false}>
              <Typography variant="subtitle2" gutterBottom>
                Import Preview
              </Typography>
              <Stack spacing={0.5}>
                {preview.total_test_sets > 0 && (
                  <>
                    <Typography variant="body2">
                      Static test sets:{' '}
                      <strong>{preview.total_test_sets}</strong>
                    </Typography>
                    <Typography variant="body2">
                      Static tests: <strong>{preview.total_tests}</strong>
                    </Typography>
                  </>
                )}
                {dynamicPreviewProbes.length > 0 && (
                  <>
                    <Typography variant="body2">
                      Dynamic probes (LLM generation):{' '}
                      <strong>{dynamicPreviewProbes.length}</strong>
                    </Typography>
                    {dynamicPreviewProbes.map(probe => (
                      <Typography
                        key={probe.full_name}
                        variant="body2"
                        sx={{ pl: 2 }}
                      >
                        • {probe.full_name}
                      </Typography>
                    ))}
                  </>
                )}
                {preview.detector_count > 0 && (
                  <Typography variant="body2">
                    Unique detectors: <strong>{preview.detector_count}</strong>
                  </Typography>
                )}
              </Stack>
              {preview.probes.length > 0 && preview.probes.length <= 5 && (
                <Box mt={1}>
                  <Typography variant="caption" color="text.secondary">
                    Test sets:{' '}
                    {preview.probes.map(p => p.test_set_name).join(', ')}
                  </Typography>
                </Box>
              )}
            </Alert>
          )}
        </Stack>
      </DialogContent>

      <DialogActions>
        <Button
          onClick={handleClose}
          disabled={(importing || preparingImport) && !isCompleteWithDynamic}
          sx={{
            '&.Mui-disabled': {
              color: 'text.disabled',
            },
          }}
        >
          {isCompleteWithDynamic ? 'Close' : 'Cancel'}
        </Button>
        {!isCompleteWithDynamic && (
          <>
            <Button
              onClick={handlePreview}
              disabled={
                loading ||
                importing ||
                preparingImport ||
                selectedProbes.size === 0
              }
              variant="outlined"
              sx={{
                '&.Mui-disabled': {
                  color: 'text.disabled',
                  borderColor: 'action.disabled',
                },
              }}
            >
              Preview
            </Button>
            <Button
              onClick={handleImport}
              disabled={
                loading ||
                importing ||
                preparingImport ||
                selectedProbes.size === 0
              }
              variant="contained"
              color="primary"
              startIcon={
                preparingImport || importing ? (
                  <CircularProgress size={16} />
                ) : undefined
              }
            >
              {(() => {
                if (preparingImport || importing) return 'Importing...';
                const { staticProbes, dynamicProbes } =
                  getSelectedProbeObjects();
                if (staticProbes.length > 0 && dynamicProbes.length > 0)
                  return `Import ${selectedProbes.size} Probes`;
                if (dynamicProbes.length > 0 && staticProbes.length === 0)
                  return `Generate ${dynamicProbes.length} Probe${dynamicProbes.length !== 1 ? 's' : ''}`;
                return `Import ${selectedProbes.size} Probe${selectedProbes.size !== 1 ? 's' : ''}`;
              })()}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}
