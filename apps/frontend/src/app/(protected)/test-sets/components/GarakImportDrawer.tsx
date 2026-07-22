'use client';

import React from 'react';
import {
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
  Tooltip,
  TextField,
  InputAdornment,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  AutoAwesome as AutoAwesomeIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  GarakProbeModule,
  GarakProbeClass,
  GarakImportPreviewResponse,
  GarakProbeSelection,
  GarakGenerateResponse,
} from '@/utils/api-client/garak-client';
import BaseDrawer from '@/components/common/BaseDrawer';

interface GarakImportDrawerProps {
  open: boolean;
  onClose: () => void;
  /**
   * Called once the import/generation task(s) have been queued. Import and
   * generation both run as background tasks, so this fires on "started",
   * not "completed" — no test set IDs are available yet.
   */
  onImportStarted?: () => void;
}

export default function GarakImportDrawer({
  open,
  onClose,
  onImportStarted,
}: GarakImportDrawerProps) {
  const [loading, setLoading] = React.useState(false);
  const [loadingModules, setLoadingModules] = React.useState(false);
  const [importing, setImporting] = React.useState(false);
  const [preparingImport, setPreparingImport] = React.useState(false);
  const [error, setError] = React.useState<string>();
  const [modules, setModules] = React.useState<GarakProbeModule[]>([]);
  const [selectedProbes, setSelectedProbes] = React.useState<Set<string>>(
    new Set()
  );
  const [preview, setPreview] =
    React.useState<GarakImportPreviewResponse | null>(null);
  const [garakVersion, setGarakVersion] = React.useState<string>('');
  const [expandedModules, setExpandedModules] = React.useState<Set<string>>(
    new Set()
  );
  const [searchQuery, setSearchQuery] = React.useState('');
  // Both static import and dynamic generation are pure fire-and-forget
  // dispatch calls (fast 202 responses) — there's no real incremental
  // progress to report, so this only ever gets set once, after every
  // dispatch call has resolved.
  const [importResult, setImportResult] = React.useState<{
    staticImported: number;
    dynamicResults: GarakGenerateResponse[];
  } | null>(null);
  const [dynamicPreviewProbes, setDynamicPreviewProbes] = React.useState<
    GarakProbeClass[]
  >([]);

  const fetchModules = React.useCallback(async () => {
    try {
      setLoadingModules(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory();
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
  }, []);

  React.useEffect(() => {
    if (open && modules.length === 0) {
      fetchModules();
    }
  }, [open, fetchModules, modules.length]);

  const filteredModules = React.useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return modules;

    return modules.reduce<GarakProbeModule[]>((acc, module) => {
      const moduleMatches =
        module.name.toLowerCase().includes(q) ||
        (module.description?.toLowerCase().includes(q) ?? false) ||
        (module.rhesis_category?.toLowerCase().includes(q) ?? false) ||
        (module.rhesis_topic?.toLowerCase().includes(q) ?? false);

      const probes = module.probes || [];
      const matchingProbes = probes.filter(
        p =>
          p.class_name.toLowerCase().includes(q) ||
          p.full_name.toLowerCase().includes(q) ||
          (p.description?.toLowerCase().includes(q) ?? false)
      );

      if (moduleMatches) {
        acc.push(module);
      } else if (matchingProbes.length > 0) {
        acc.push({ ...module, probes: matchingProbes });
      }
      return acc;
    }, []);
  }, [modules, searchQuery]);

  const getModuleProbes = (module: GarakProbeModule): GarakProbeClass[] => {
    return module.probes || [];
  };

  const isModuleFullySelected = (module: GarakProbeModule): boolean => {
    const probes = getModuleProbes(module);
    return (
      probes.length > 0 && probes.every(p => selectedProbes.has(p.full_name))
    );
  };

  const isModulePartiallySelected = (module: GarakProbeModule): boolean => {
    const probes = getModuleProbes(module);
    const selectedCount = probes.filter(p =>
      selectedProbes.has(p.full_name)
    ).length;
    return selectedCount > 0 && selectedCount < probes.length;
  };

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

  const handleModuleToggle = (module: GarakProbeModule) => {
    const probes = getModuleProbes(module);
    const newSelected = new Set(selectedProbes);

    if (isModuleFullySelected(module)) {
      probes.forEach(p => newSelected.delete(p.full_name));
    } else {
      probes.forEach(p => newSelected.add(p.full_name));
    }

    setSelectedProbes(newSelected);
    setPreview(null);
  };

  const handleSelectAll = () => {
    const visibleProbes = filteredModules.flatMap(m => getModuleProbes(m));
    const allVisible = visibleProbes.every(p =>
      selectedProbes.has(p.full_name)
    );
    const newSelected = new Set(selectedProbes);
    if (allVisible) {
      visibleProbes.forEach(p => newSelected.delete(p.full_name));
    } else {
      visibleProbes.forEach(p => newSelected.add(p.full_name));
    }
    setSelectedProbes(newSelected);
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
      const clientFactory = new ApiClientFactory();
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

  const handleImport = async () => {
    if (selectedProbes.size === 0) {
      setError('Please select at least one probe');
      return;
    }

    const { staticProbes, dynamicProbes } = getSelectedProbeObjects();
    if (staticProbes.length + dynamicProbes.length === 0) return;

    try {
      setImporting(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory();
      const garakClient = clientFactory.getGarakClient();

      let staticImported = 0;
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

        // Import runs as a background task (some probes produce thousands of
        // tests) — this only confirms the task was queued, not that it
        // finished. The resulting test set(s) appear in the test sets list
        // once the task completes.
        await garakClient.importProbes({
          probes: buildProbeSelections(staticProbes),
          name_prefix: 'Garak',
        });
        staticImported = staticProbes.length;
      }

      // Dynamic generation is also just a queue-and-return dispatch per
      // probe — fire them concurrently rather than one at a time, since
      // there's no per-probe work to wait on here.
      const dynamicResults =
        dynamicProbes.length > 0
          ? await Promise.all(
              dynamicProbes.map(probe =>
                garakClient.generateDynamicProbe({
                  module_name: probe.module_name,
                  class_name: probe.class_name,
                })
              )
            )
          : [];

      // Both static import and dynamic generation are fire-and-forget
      // background tasks — neither completes synchronously, so we don't
      // auto-close or report created test set IDs here. The resulting test
      // set(s) appear in the test sets list once their tasks finish; the
      // user closes this drawer manually after seeing the confirmation below.
      setImportResult({ staticImported, dynamicResults });
      onImportStarted?.();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to import Garak probes'
      );
    } finally {
      setImporting(false);
      setPreparingImport(false);
    }
  };

  const handleClose = () => {
    onClose();
  };

  const resetState = React.useCallback(() => {
    setSelectedProbes(new Set());
    setPreview(null);
    setError(undefined);
    setImportResult(null);
    setPreparingImport(false);
    setDynamicPreviewProbes([]);
    setSearchQuery('');
  }, []);

  // Reset on the opening transition, not on close: BaseDrawer keeps children
  // mounted through its close animation, so clearing state the instant
  // `open` goes false would re-render the probe-selection screen underneath
  // the still-visible confirmation panel — a brief flash of stale content
  // during the slide-out. Resetting on (re)open instead gives every session
  // a clean slate without touching state while the drawer is animating shut.
  const wasOpenRef = React.useRef(false);
  React.useEffect(() => {
    if (open && !wasOpenRef.current) resetState();
    wasOpenRef.current = open;
  }, [open, resetState]);

  const toggleModuleExpand = (moduleName: string) => {
    const newExpanded = new Set(expandedModules);
    if (newExpanded.has(moduleName)) {
      newExpanded.delete(moduleName);
    } else {
      newExpanded.add(moduleName);
    }
    setExpandedModules(newExpanded);
  };

  const allProbesCount = modules.flatMap(m => getModuleProbes(m)).length;
  const visibleProbesCount = filteredModules.flatMap(m =>
    getModuleProbes(m)
  ).length;
  const allVisibleSelected =
    visibleProbesCount > 0 &&
    filteredModules
      .flatMap(m => getModuleProbes(m))
      .every(p => selectedProbes.has(p.full_name));

  // Both static import and dynamic generation are fire-and-forget background
  // tasks — once queued, the drawer must show the "started" summary and wait
  // for the user to close it explicitly (not just for the dynamic case: a
  // static-only import needs the same persistent confirmation).
  const isImportComplete = !!importResult;

  const saveButtonText = (() => {
    const { staticProbes, dynamicProbes } = getSelectedProbeObjects();
    if (staticProbes.length > 0 && dynamicProbes.length > 0)
      return `Import ${selectedProbes.size} Probes`;
    if (dynamicProbes.length > 0 && staticProbes.length === 0)
      return `Generate ${dynamicProbes.length} Probe${dynamicProbes.length !== 1 ? 's' : ''}`;
    return `Import ${selectedProbes.size} Probe${selectedProbes.size !== 1 ? 's' : ''}`;
  })();

  return (
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title="Import from Garak"
      width={720}
      closeButtonText={isImportComplete ? 'Close' : 'Cancel'}
      loading={importing || preparingImport}
      onSave={isImportComplete ? undefined : handleImport}
      saveDisabled={loading || selectedProbes.size === 0}
      saveButtonText={saveButtonText}
    >
      <Stack spacing={3} sx={{ flex: 1, minHeight: 0 }}>
        {error && (
          <Alert severity="error" onClose={() => setError(undefined)}>
            {error}
          </Alert>
        )}

        {/* Probe Selection - Hide when importing or showing completion */}
        {!importing && !isImportComplete && (
          <Box
            sx={{
              flex: 1,
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Stack
              direction="row"
              justifyContent="space-between"
              alignItems="center"
              mb={1}
            >
              <Stack direction="row" alignItems="center" spacing={1}>
                <Typography variant="subtitle1" fontWeight="medium">
                  Select Probes ({selectedProbes.size} of {allProbesCount}{' '}
                  selected)
                </Typography>
                {garakVersion && (
                  <Chip
                    label={`v${garakVersion}`}
                    size="small"
                    variant="outlined"
                  />
                )}
              </Stack>
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  onClick={handlePreview}
                  disabled={
                    loading ||
                    importing ||
                    preparingImport ||
                    selectedProbes.size === 0
                  }
                  variant="outlined"
                >
                  Preview
                </Button>
                <Button
                  size="small"
                  onClick={handleSelectAll}
                  disabled={loadingModules || visibleProbesCount === 0}
                >
                  {allVisibleSelected ? 'Deselect All' : 'Select All'}
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
              <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
                <TextField
                  size="small"
                  placeholder="Search probes by name, description, category..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  fullWidth
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon fontSize="small" color="action" />
                      </InputAdornment>
                    ),
                    endAdornment: searchQuery ? (
                      <InputAdornment position="end">
                        <IconButton
                          size="small"
                          onClick={() => setSearchQuery('')}
                          edge="end"
                        >
                          <ClearIcon fontSize="small" />
                        </IconButton>
                      </InputAdornment>
                    ) : null,
                  }}
                />
                {filteredModules.length === 0 ? (
                  <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
                    <Typography color="text.secondary">
                      No probes matching &ldquo;{searchQuery}&rdquo;
                    </Typography>
                  </Paper>
                ) : (
                  <Paper
                    variant="outlined"
                    sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}
                  >
                    <Stack divider={<Divider />}>
                      {filteredModules.map(module => (
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
                              <Typography
                                variant="body2"
                                color="text.secondary"
                              >
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
                                      duration:
                                        theme.transitions.duration.short,
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
                                    checked={selectedProbes.has(
                                      probe.full_name
                                    )}
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
                                              height: theme =>
                                                theme.spacing(2.5),
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
              </Stack>
            )}
          </Box>
        )}

        {/* Import Result — mirrors the completion screen in this same
            folder's FileImportDrawer (centered check icon + headline)
            instead of the old "in-progress" panel: both static import and
            dynamic generation are now pure fire-and-forget dispatch calls
            (fast 202 responses), so there's no meaningful in-between state
            to show while `importing` — the Save button's own spinner (via
            BaseDrawer's `loading` prop) covers that brief window, and this
            only ever renders once every dispatch call has resolved. */}
        {isImportComplete && importResult && (
          <Stack spacing={3} alignItems="center" sx={{ py: 4 }}>
            <CheckCircleIcon
              sx={theme => ({
                fontSize: theme.spacing(8),
                color: theme.palette.success.main,
              })}
            />
            <Stack spacing={0.5} alignItems="center">
              <Typography variant="h6">Import Started!</Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                textAlign="center"
              >
                Running in the background — the test set(s) will appear in your
                test sets list once complete.
              </Typography>
            </Stack>

            {(importResult.staticImported > 0 ||
              importResult.dynamicResults.length > 0) && (
              <Paper variant="outlined" sx={{ p: 2, width: '100%' }}>
                <Stack spacing={2}>
                  {importResult.staticImported > 0 && (
                    <Stack spacing={0.5}>
                      <Typography variant="body2" fontWeight="medium">
                        {importResult.staticImported} static probe
                        {importResult.staticImported !== 1 ? 's' : ''}
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
                  {importResult.dynamicResults.length > 0 && (
                    <Stack spacing={0.5}>
                      <Typography variant="body2" fontWeight="medium">
                        {importResult.dynamicResults.length} dynamic probe
                        {importResult.dynamicResults.length !== 1 ? 's' : ''}
                      </Typography>
                      {importResult.dynamicResults.map(result => (
                        <Typography
                          key={result.task_id}
                          variant="body2"
                          color="text.secondary"
                          sx={{ pl: 2 }}
                        >
                          • {result.probe_full_name}
                        </Typography>
                      ))}
                    </Stack>
                  )}
                </Stack>
              </Paper>
            )}
          </Stack>
        )}

        {/* Preview */}
        {preview && !importing && !isImportComplete && (
          <Alert severity="info" icon={false}>
            <Typography variant="subtitle2" gutterBottom>
              Import Preview
            </Typography>
            <Stack spacing={0.5}>
              {preview.total_test_sets > 0 && (
                <>
                  <Typography variant="body2">
                    Static test sets: <strong>{preview.total_test_sets}</strong>
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
    </BaseDrawer>
  );
}
