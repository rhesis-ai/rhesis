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
  TextField,
  Checkbox,
  Alert,
  CircularProgress,
  Box,
  Chip,
  Divider,
  Paper,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Security as SecurityIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  GarakProbeModule,
  GarakProbeClass,
  GarakImportPreviewResponse,
  GarakProbeSelection,
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
  const [error, setError] = React.useState<string>();
  const [modules, setModules] = React.useState<GarakProbeModule[]>([]);
  // Track selected probes by full_name (e.g., "dan.Dan_11_0")
  const [selectedProbes, setSelectedProbes] = React.useState<Set<string>>(
    new Set()
  );
  const [namePrefix, setNamePrefix] = React.useState('Garak');
  const [preview, setPreview] =
    React.useState<GarakImportPreviewResponse | null>(null);
  const [garakVersion, setGarakVersion] = React.useState<string>('');
  const [expandedModules, setExpandedModules] = React.useState<Set<string>>(
    new Set()
  );

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
        name_prefix: namePrefix || 'Garak',
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

    try {
      setImporting(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();

      const response = await garakClient.importProbes({
        probes: buildProbeSelections(),
        name_prefix: namePrefix || 'Garak',
      });

      // Pass all created test set IDs
      onSuccess?.(response.test_sets.map(ts => ts.test_set_id));
      handleClose();
    } catch (err: any) {
      setError(err.message || 'Failed to import Garak probes');
    } finally {
      setImporting(false);
    }
  };

  const handleClose = () => {
    setSelectedProbes(new Set());
    setNamePrefix('Garak');
    setPreview(null);
    setError(undefined);
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

          {/* Probe Selection */}
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
                sx={{ maxHeight: 400, overflow: 'auto' }}
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
                          <Stack direction="row" spacing={0.5} flexWrap="wrap">
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
                            sx={{
                              transform: expandedModules.has(module.name)
                                ? 'rotate(180deg)'
                                : 'none',
                              transition: 'transform 0.2s',
                            }}
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
                                    sx={{ height: 20 }}
                                  />
                                </Stack>
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                  sx={{
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    maxWidth: 400,
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

          {/* Test Set Name Prefix */}
          <Box>
            <Typography variant="subtitle1" fontWeight="medium" mb={1}>
              Test Set Naming
            </Typography>
            <TextField
              label="Name Prefix"
              value={namePrefix}
              onChange={e => setNamePrefix(e.target.value)}
              placeholder="Garak"
              fullWidth
              helperText="Each probe creates a test set named '[Prefix]: [Probe Name]'"
            />
          </Box>

          {/* Preview */}
          {preview && (
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
        <Button onClick={handleClose} disabled={importing}>
          Cancel
        </Button>
        <Button
          onClick={handlePreview}
          disabled={loading || importing || selectedProbes.size === 0}
          variant="outlined"
        >
          {loading ? <CircularProgress size={20} /> : 'Preview'}
        </Button>
        <Button
          onClick={handleImport}
          disabled={importing || selectedProbes.size === 0}
          variant="contained"
          color="primary"
        >
          {importing ? (
            <CircularProgress size={20} />
          ) : (
            `Import ${selectedProbes.size} Probe${selectedProbes.size !== 1 ? 's' : ''}`
          )}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
