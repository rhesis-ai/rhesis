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
  FormControlLabel,
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
  GarakImportPreviewResponse,
} from '@/utils/api-client/garak-client';

interface GarakImportDialogProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  onSuccess?: (testSetId: string) => void;
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
  const [selectedModules, setSelectedModules] = React.useState<Set<string>>(
    new Set()
  );
  const [testSetName, setTestSetName] = React.useState('');
  const [description, setDescription] = React.useState('');
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

  const handleModuleToggle = (moduleName: string) => {
    const newSelected = new Set(selectedModules);
    if (newSelected.has(moduleName)) {
      newSelected.delete(moduleName);
    } else {
      newSelected.add(moduleName);
    }
    setSelectedModules(newSelected);
    setPreview(null); // Clear preview when selection changes
  };

  const handleSelectAll = () => {
    if (selectedModules.size === modules.length) {
      setSelectedModules(new Set());
    } else {
      setSelectedModules(new Set(modules.map(m => m.name)));
    }
    setPreview(null);
  };

  const handlePreview = async () => {
    if (selectedModules.size === 0) {
      setError('Please select at least one module');
      return;
    }

    try {
      setLoading(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();

      const previewResponse = await garakClient.previewImport({
        modules: Array.from(selectedModules),
        test_set_name: testSetName || 'Garak Import',
        description: description || undefined,
      });

      setPreview(previewResponse);

      // Auto-generate name if not set
      if (!testSetName) {
        const moduleNames = Array.from(selectedModules).join(', ');
        setTestSetName(`Garak: ${moduleNames}`);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to preview import');
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    if (selectedModules.size === 0) {
      setError('Please select at least one module');
      return;
    }

    if (!testSetName.trim()) {
      setError('Please enter a test set name');
      return;
    }

    try {
      setImporting(true);
      setError(undefined);

      const clientFactory = new ApiClientFactory(sessionToken);
      const garakClient = clientFactory.getGarakClient();

      const response = await garakClient.importProbes({
        modules: Array.from(selectedModules),
        test_set_name: testSetName,
        description: description || undefined,
      });

      onSuccess?.(response.test_set_id);
      handleClose();
    } catch (err: any) {
      setError(err.message || 'Failed to import Garak probes');
    } finally {
      setImporting(false);
    }
  };

  const handleClose = () => {
    setSelectedModules(new Set());
    setTestSetName('');
    setDescription('');
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

          {/* Module Selection */}
          <Box>
            <Stack
              direction="row"
              justifyContent="space-between"
              alignItems="center"
              mb={1}
            >
              <Typography variant="subtitle1" fontWeight="medium">
                Select Probe Modules
              </Typography>
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  onClick={handleSelectAll}
                  disabled={loadingModules}
                >
                  {selectedModules.size === modules.length
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
                sx={{ maxHeight: 300, overflow: 'auto' }}
              >
                <Stack divider={<Divider />}>
                  {modules.map(module => (
                    <Box key={module.name}>
                      <Stack
                        direction="row"
                        alignItems="center"
                        sx={{ p: 1.5, cursor: 'pointer' }}
                        onClick={() => handleModuleToggle(module.name)}
                      >
                        <Checkbox
                          checked={selectedModules.has(module.name)}
                          onClick={e => e.stopPropagation()}
                          onChange={() => handleModuleToggle(module.name)}
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
                            {module.tags.slice(0, 3).map(tag => (
                              <Chip
                                key={tag}
                                label={tag}
                                size="small"
                                variant="outlined"
                              />
                            ))}
                          </Stack>
                        </Stack>
                        <IconButton
                          size="small"
                          onClick={e => {
                            e.stopPropagation();
                            toggleModuleExpand(module.name);
                          }}
                        >
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
                      <Collapse in={expandedModules.has(module.name)}>
                        <Box sx={{ pl: 7, pr: 2, pb: 2 }}>
                          <Typography variant="caption" color="text.secondary">
                            Probe classes: {module.probe_count} | Default
                            detector: {module.default_detector || 'N/A'}
                          </Typography>
                        </Box>
                      </Collapse>
                    </Box>
                  ))}
                </Stack>
              </Paper>
            )}
          </Box>

          {/* Test Set Details */}
          <Box>
            <Typography variant="subtitle1" fontWeight="medium" mb={1}>
              Test Set Details
            </Typography>
            <Stack spacing={2}>
              <TextField
                label="Test Set Name"
                value={testSetName}
                onChange={e => setTestSetName(e.target.value)}
                placeholder="e.g., Garak Security Tests"
                fullWidth
                required
              />
              <TextField
                label="Description"
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Optional description..."
                fullWidth
                multiline
                rows={2}
              />
            </Stack>
          </Box>

          {/* Preview */}
          {preview && (
            <Alert severity="info" icon={false}>
              <Typography variant="subtitle2" gutterBottom>
                Import Preview
              </Typography>
              <Stack spacing={0.5}>
                <Typography variant="body2">
                  Total probe classes: <strong>{preview.total_probes}</strong>
                </Typography>
                <Typography variant="body2">
                  Total tests to create: <strong>{preview.total_tests}</strong>
                </Typography>
                <Typography variant="body2">
                  Detectors: <strong>{preview.detector_count}</strong>
                </Typography>
              </Stack>
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
          disabled={loading || importing || selectedModules.size === 0}
          variant="outlined"
        >
          {loading ? <CircularProgress size={20} /> : 'Preview'}
        </Button>
        <Button
          onClick={handleImport}
          disabled={
            importing || selectedModules.size === 0 || !testSetName.trim()
          }
          variant="contained"
          color="primary"
        >
          {importing ? <CircularProgress size={20} /> : 'Import'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
