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
  alpha,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Security as SecurityIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  GarakProbeModule,
  GarakProbeClass,
  GarakImportPreviewResponse,
  GarakProbeSelection,
  GarakProbePreview,
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
    currentProbeIndex: number;
    totalProbes: number;
    currentTestCount: number;
    totalTests: number;
    currentProbe: GarakProbePreview | null;
    isComplete: boolean;
  } | null>(null);

  // Fetch available modules when dialog opens
  React.useEffect(() => {
    if (open && modules.length === 0) {
      fetchModules();
    }
  }, [open]);

  const fetchModules = async () => {
    try {
      setLoadingModules(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();

      const response = await garakClient.listProbeModules();
      setModules(response.modules);
      setGarakVersion(response.garak_version);
    } catch (err: any) {
      setError(err.message || 'Failed to load Garak modules');
    } finally {
      setLoadingModules(false);
    }
  };

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

  // Build probe selections for API
  const buildProbeSelections = (): GarakProbeSelection[] => {
    const selections: GarakProbeSelection[] = [];
    for (const module of modules) {
      for (const probe of getModuleProbes(module)) {
        if (selectedProbes.has(probe.full_name)) {
          selections.push({
            module_name: probe.module_name,
            class_name: probe.class_name,
          });
        }
      }
    }
    return selections;
  };

  const handlePreview = async () => {
    if (selectedProbes.size === 0) {
      setError('Please select at least one probe');
      return;
    }

    try {
      setLoading(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();

      const previewResponse = await garakClient.previewImport({
        probes: buildProbeSelections(),
        name_prefix: 'Garak',
      });

      setPreview(previewResponse);
    } catch (err: any) {
      setError(err.message || 'Failed to preview import');
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    if (selectedProbes.size === 0) {
      setError('Please select at least one probe');
      return;
    }

    // First get preview to show progress
    let previewData = preview;
    if (!previewData) {
      try {
        setPreparingImport(true);
        const clientFactory = new ApiClientFactory(sessionToken);
        const garakClient = clientFactory.getGarakClient();
        previewData = await garakClient.previewImport({
          probes: buildProbeSelections(),
          name_prefix: 'Garak',
        });
        setPreview(previewData);
      } catch (err: any) {
        setError(err.message || 'Failed to get import preview');
        setPreparingImport(false);
        return;
      } finally {
        setPreparingImport(false);
      }
    }

    try {
      setImporting(true);
      setError(undefined);

      // Calculate cumulative test counts for progress tracking
      const cumulativeTestCounts = previewData.probes.reduce<number[]>(
        (acc, probe, idx) => {
          const prevCount = idx > 0 ? acc[idx - 1] : 0;
          acc.push(prevCount + probe.prompt_count);
          return acc;
        },
        []
      );

      // Initialize progress tracking with total tests
      setImportProgress({
        currentProbeIndex: 0,
        totalProbes: previewData.probes.length,
        currentTestCount: 0,
        totalTests: previewData.total_tests,
        currentProbe: previewData.probes[0] || null,
        isComplete: false,
      });

      // Simulate progress updates while import happens
      // Cap at 95% until the import actually completes
      const maxSimulatedProgress = Math.floor(previewData.total_tests * 0.95);
      const progressInterval = setInterval(() => {
        setImportProgress(prev => {
          if (!prev || !previewData || prev.isComplete) return prev;

          // Calculate estimated tests per interval based on total tests
          // Aim to reach ~95% over the expected import time
          const testsPerInterval = Math.max(
            1,
            Math.ceil(previewData.total_tests / 60)
          ); // ~30 seconds to reach 95%
          const nextTestCount = Math.min(
            prev.currentTestCount + testsPerInterval,
            maxSimulatedProgress
          );

          // Find which probe we're on based on cumulative test count
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

      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();

      const response = await garakClient.importProbes({
        probes: buildProbeSelections(),
        name_prefix: 'Garak',
      });

      clearInterval(progressInterval);

      // Show completion at 100%
      setImportProgress({
        currentProbeIndex: previewData.probes.length,
        totalProbes: previewData.probes.length,
        currentTestCount: previewData.total_tests,
        totalTests: previewData.total_tests,
        currentProbe: null,
        isComplete: true,
      });

      // Small delay to show completion before closing
      await new Promise(resolve => setTimeout(resolve, 500));

      // Pass all created test set IDs
      onSuccess?.(response.test_sets.map(ts => ts.test_set_id));
      handleClose();
    } catch (err: any) {
      setError(err.message || 'Failed to import Garak probes');
      setImportProgress(null);
    } finally {
      setImporting(false);
    }
  };

  const handleClose = () => {
    setSelectedProbes(new Set());
    setPreview(null);
    setError(undefined);
    setImportProgress(null);
    setPreparingImport(false);
    onClose();
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

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
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

          {/* Probe Selection - Hide when importing */}
          {!importing && (
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
                              <Chip
                                label={`${module.total_prompt_count} prompts`}
                                size="small"
                                variant="outlined"
                              />
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
                                    <Chip
                                      label={`${probe.prompt_count} tests`}
                                      size="small"
                                      variant="outlined"
                                      sx={{
                                        height: theme => theme.spacing(2.5),
                                      }}
                                    />
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
          {importing && importProgress && (
            <Paper
              elevation={0}
              sx={theme => ({
                p: 3,
                bgcolor: alpha(theme.palette.primary.main, 0.08),
                border: '1px solid',
                borderColor: alpha(theme.palette.primary.main, 0.24),
                borderRadius: theme.shape.borderRadius / 4,
              })}
            >
              <Stack spacing={2}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <CircularProgress size={20} />
                  <Typography variant="subtitle1" fontWeight="medium">
                    Importing Garak Probes...
                  </Typography>
                </Stack>

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
                      {importProgress.currentProbeIndex + 1} of{' '}
                      {importProgress.totalProbes} probes
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

                {importProgress.currentProbe && (
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Stack spacing={1}>
                      <Stack direction="row" alignItems="center" spacing={1}>
                        <SecurityIcon fontSize="small" color="primary" />
                        <Typography variant="body1" fontWeight="medium">
                          {importProgress.currentProbe.test_set_name}
                        </Typography>
                      </Stack>
                      <Stack direction="row" spacing={2}>
                        <Chip
                          label={`${importProgress.currentProbe.prompt_count} prompts`}
                          size="small"
                          variant="outlined"
                        />
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
                )}
              </Stack>
            </Paper>
          )}

          {/* Preview */}
          {preview && !importing && (
            <Alert severity="info" icon={false}>
              <Typography variant="subtitle2" gutterBottom>
                Import Preview
              </Typography>
              <Stack spacing={0.5}>
                <Typography variant="body2">
                  Test sets to create:{' '}
                  <strong>{preview.total_test_sets}</strong>
                </Typography>
                <Typography variant="body2">
                  Total tests: <strong>{preview.total_tests}</strong>
                </Typography>
                <Typography variant="body2">
                  Unique detectors: <strong>{preview.detector_count}</strong>
                </Typography>
              </Stack>
              {preview.probes.length <= 5 && (
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
          disabled={importing || preparingImport}
          sx={{
            '&.Mui-disabled': {
              color: 'text.disabled',
            },
          }}
        >
          Cancel
        </Button>
        <Button
          onClick={handlePreview}
          disabled={
            loading || importing || preparingImport || selectedProbes.size === 0
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
            loading || importing || preparingImport || selectedProbes.size === 0
          }
          variant="contained"
          color="primary"
          startIcon={
            preparingImport || importing ? (
              <CircularProgress size={16} />
            ) : undefined
          }
        >
          {preparingImport || importing
            ? 'Importing...'
            : `Import ${selectedProbes.size} Probe${selectedProbes.size !== 1 ? 's' : ''}`}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
