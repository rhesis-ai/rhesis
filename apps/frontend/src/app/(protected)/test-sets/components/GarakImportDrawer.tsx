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
  LinearProgress,
  Tooltip,
  alpha,
  TextField,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material/Select';
import {
  ExpandMore as ExpandMoreIcon,
  Security as SecurityIcon,
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
  GarakProbePreview,
  GarakGenerateResponse,
} from '@/utils/api-client/garak-client';
import BaseDrawer from '@/components/common/BaseDrawer';
import {
  drawerFieldsSx,
  drawerListChipSx,
  drawerOutlinedFieldSx,
  drawerSectionSx,
} from '@/components/common/drawerFormFieldSx';
import OwaspGenerateForm, {
  type OwaspGenerateFooterState,
} from './OwaspGenerateForm';

/** Garak/OWASP lists need extra room vs the default 578 form drawer. */
const SECURITY_DRAWER_WIDTH = 680;

/** Strip light markdown emphasis markers from Garak probe copy. */
const stripMarkdown = (value: string) =>
  value.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1').trim();


interface GarakImportDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  onSuccess?: (testSetIds: string[]) => void;
  onOwaspSuccess?: (taskIds: string[]) => void;
  /** When false, the Garak option is hidden from the source dropdown. Default true. */
  canUseGarak?: boolean;
  /** When false, the OWASP option is hidden from the source dropdown. Default false. */
  canUseOwasp?: boolean;
}

export default function GarakImportDrawer({
  open,
  onClose,
  sessionToken,
  onSuccess,
  onOwaspSuccess,
  canUseGarak = true,
  canUseOwasp = false,
}: GarakImportDrawerProps) {
  const availableSources = React.useMemo(() => {
    const sources: SecuritySource[] = [];
    if (canUseGarak) sources.push('garak');
    if (canUseOwasp) sources.push('owasp');
    return sources;
  }, [canUseGarak, canUseOwasp]);

  const [source, setSource] = React.useState<SecuritySource>(
    availableSources[0] ?? 'garak'
  );
  const [owaspFooter, setOwaspFooter] =
    React.useState<OwaspGenerateFooterState | null>(null);

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

  React.useEffect(() => {
    if (open && source === 'garak' && modules.length === 0) {
      fetchModules();
    }
  }, [open, source, fetchModules, modules.length]);

  // Keep the selected source valid when permissions change.
  React.useEffect(() => {
    if (availableSources.length === 0) return;
    if (!availableSources.includes(source)) {
      setSource(availableSources[0]);
    }
  }, [availableSources, source]);

  const handleSourceChange = (event: SelectChangeEvent<SecuritySource>) => {
    setSource(event.target.value as SecuritySource);
  };

  const showSourceSelector = availableSources.length > 1;

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

        const totalTests = previewData.total_tests;
        const maxSimulated = Math.floor(totalTests * 0.95);
        const progressInterval = setInterval(() => {
          setImportProgress(prev => {
            if (
              !prev ||
              prev.phase !== 'static' ||
              prev.isComplete ||
              !previewData
            )
              return prev;
            const testsPerInterval = Math.max(1, Math.ceil(totalTests / 60));
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
                currentTestCount: totalTests,
                staticImported: staticProbes.length,
              }
            : prev
        );
      }

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

  const resetState = React.useCallback(() => {
    setSelectedProbes(new Set());
    setPreview(null);
    setError(undefined);
    setImportProgress(null);
    setPreparingImport(false);
    setSearchQuery('');
    setOwaspFooter(null);
    setSource(availableSources[0] ?? 'garak');
  }, [availableSources]);

  React.useEffect(() => {
    if (!open) resetState();
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

  const isCompleteWithDynamic =
    !!importProgress?.isComplete &&
    (importProgress?.dynamicResults.length ?? 0) > 0;

  const saveButtonText = (() => {
    const { staticProbes, dynamicProbes } = getSelectedProbeObjects();
    if (staticProbes.length > 0 && dynamicProbes.length > 0)
      return `Import ${selectedProbes.size} Probes`;
    if (dynamicProbes.length > 0 && staticProbes.length === 0)
      return `Generate ${dynamicProbes.length} Probe${dynamicProbes.length !== 1 ? 's' : ''}`;
    return `Import ${selectedProbes.size} Probe${selectedProbes.size !== 1 ? 's' : ''}`;
  })();

  const isOwasp = source === 'owasp';
  const drawerTitle = isOwasp ? 'Generate from OWASP' : 'Import from Garak';
  const isGarakListMode =
    !isOwasp && !importing && !isCompleteWithDynamic;

  const hideSourceSelector =
    (isOwasp && owaspFooter?.isComplete) || isCompleteWithDynamic;

  return (
    <BaseDrawer
      open={open}
      onClose={handleClose}
      title={drawerTitle}
      width={SECURITY_DRAWER_WIDTH}
      contentLayout={isGarakListMode ? 'fill' : 'form'}
      closeButtonText={
        isOwasp
          ? (owaspFooter?.closeButtonText ?? 'Cancel')
          : isCompleteWithDynamic
            ? 'Close'
            : 'Cancel'
      }
      loading={
        isOwasp
          ? (owaspFooter?.loading ?? false)
          : importing || preparingImport
      }
      onSave={
        isOwasp
          ? owaspFooter?.onSave
          : isCompleteWithDynamic
            ? undefined
            : handleImport
      }
      saveDisabled={
        isOwasp
          ? (owaspFooter?.saveDisabled ?? true)
          : selectedProbes.size === 0
      }
      saveButtonText={
        isOwasp ? (owaspFooter?.saveButtonText ?? 'Generate') : saveButtonText
      }
    >
      {showSourceSelector && !hideSourceSelector && (
        <FormControl
          fullWidth
          sx={{
            ...drawerOutlinedFieldSx,
            flexShrink: 0,
            ...(isGarakListMode ? { mt: '10px', mb: '40px' } : {}),
          }}
        >
          <InputLabel shrink id="security-source-label">
            Source
          </InputLabel>
          <Select
            labelId="security-source-label"
            label="Source"
            value={source}
            onChange={handleSourceChange}
          >
            {canUseGarak && <MenuItem value="garak">Garak</MenuItem>}
            {canUseOwasp && <MenuItem value="owasp">OWASP</MenuItem>}
          </Select>
        </FormControl>
      )}

        {isOwasp ? (
          <OwaspGenerateForm
            active={open && isOwasp}
            sessionToken={sessionToken}
            onSuccess={onOwaspSuccess}
            onFooterChange={setOwaspFooter}
          />
        ) : (
          <>
        {error && (
          <Alert severity="error" onClose={() => setError(undefined)}>
            {error}
          </Alert>
        )}

        {/* Probe Selection - Hide when importing or showing completion */}
        {!importing && !isCompleteWithDynamic && (
          <Box
            sx={{
              ...drawerSectionSx,
              flex: 1,
              minHeight: 0,
            }}
          >
            <Box sx={{ flexShrink: 0 }}>
              <Stack
                direction="row"
                alignItems="center"
                justifyContent="space-between"
                spacing={2}
              >
                <Typography
                  sx={{
                    fontSize: 18,
                    lineHeight: '25px',
                    fontWeight: 700,
                    color: theme => theme.palette.greyscale.title,
                  }}
                >
                  Select Probes
                </Typography>
                <Button
                  size="small"
                  onClick={handleSelectAll}
                  disabled={loadingModules || visibleProbesCount === 0}
                  sx={{
                    flexShrink: 0,
                    fontSize: 14,
                    fontWeight: 700,
                    lineHeight: '22px',
                    textTransform: 'none',
                  }}
                >
                  {allVisibleSelected ? 'Deselect All' : 'Select All'}
                </Button>
              </Stack>
              <Typography
                sx={{
                  fontSize: 12,
                  lineHeight: '18px',
                  color: theme => theme.palette.greyscale.subtitle,
                }}
              >
                {`${selectedProbes.size} of ${allProbesCount} probes selected${garakVersion ? ` · Garak v${garakVersion}` : ''}.`}
              </Typography>
            </Box>
            <Box
              sx={{
                ...drawerFieldsSx,
                flex: 1,
                minHeight: 0,
              }}
            >
            <TextField
              placeholder="Search probes..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              fullWidth
              label="Search"
              sx={{ ...drawerOutlinedFieldSx, flexShrink: 0 }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
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
                ) : undefined,
              }}
            />

            {loadingModules ? (
              <Box display="flex" justifyContent="center" p={4}>
                <CircularProgress />
              </Box>
            ) : (
              <Stack spacing={1} sx={{ flex: 1, minHeight: 0 }}>
                {filteredModules.length === 0 ? (
                  <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
                    <Typography color="text.secondary">
                      No probes matching &ldquo;{searchQuery}&rdquo;
                    </Typography>
                  </Paper>
                ) : (
                  <Paper
                    variant="outlined"
                    sx={{
                      flex: 1,
                      minHeight: 0,
                      overflow: 'auto',
                      bgcolor: 'background.paper',
                      '& .MuiChip-root': drawerListChipSx,
                    }}
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
                            <Stack flex={1} spacing={0.5} minWidth={0}>
                              <Stack
                                direction="row"
                                alignItems="center"
                                spacing={1}
                                flexWrap="wrap"
                              >
                                <Typography variant="bodyMBold">
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
                                {stripMarkdown(module.description)}
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
                            <Stack divider={<Divider />}>
                              {getModuleProbes(module).map(probe => (
                                <Stack
                                  key={probe.full_name}
                                  direction="row"
                                  alignItems="flex-start"
                                  sx={{ px: 1.5, py: 1, pl: 6, cursor: 'pointer' }}
                                  onClick={() => handleProbeToggle(probe)}
                                >
                                  <Checkbox
                                    size="small"
                                    checked={selectedProbes.has(
                                      probe.full_name
                                    )}
                                    onClick={e => e.stopPropagation()}
                                    onChange={() => handleProbeToggle(probe)}
                                    sx={{ pt: 0.25 }}
                                  />
                                  <Stack flex={1} spacing={0.25} minWidth={0}>
                                    <Stack
                                      direction="row"
                                      alignItems="center"
                                      spacing={1}
                                    >
                                      <Typography variant="bodyMBold">
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
                                          />
                                        </Tooltip>
                                      ) : (
                                        <Chip
                                          label={`${probe.prompt_count} tests`}
                                          size="small"
                                          variant="outlined"
                                        />
                                      )}
                                    </Stack>
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
                                      {stripMarkdown(probe.description)}
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
              borderRadius: `${theme.shape.borderRadius}px`,
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
                        Once generation completes, the test sets will appear in
                        your test sets list.
                      </Typography>
                    </Stack>
                  )}
                </Stack>
              )}
            </Stack>
          </Paper>
        )}
          </>
        )}
    </BaseDrawer>
  );
}
