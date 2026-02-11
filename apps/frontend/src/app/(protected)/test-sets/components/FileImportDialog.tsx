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
  Alert,
  CircularProgress,
  Box,
  Stepper,
  Step,
  StepLabel,
  LinearProgress,
  TextField,
  Chip,
  IconButton,
  Tooltip,
  alpha,
  Paper,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Pagination,
  useTheme,
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  AutoFixHigh as AutoFixHighIcon,
  CheckCircle as CheckCircleIcon,
  ErrorOutline as ErrorOutlineIcon,
  WarningAmber as WarningAmberIcon,
  Close as CloseIcon,
  ArrowForward as ArrowForwardIcon,
} from '@mui/icons-material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import DragAndDropUpload from '@/components/common/DragAndDropUpload';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { getImportErrorMessage } from '@/utils/api-client/import-error-utils';
import type {
  AnalyzeResponse,
  ParseResponse,
  PreviewPage,
  PreviewRow,
  ValidationSummary,
  ConfirmResponse,
} from '@/utils/api-client/interfaces/import';

interface FileImportDialogProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
  onSuccess?: (testSetId: string) => void;
}

const STEPS = ['Upload & Map', 'Inspect Data', 'Import'];

const SUPPORTED_FORMATS = [
  { ext: '.json', label: 'JSON', desc: 'Nested or flat test data' },
  { ext: '.jsonl', label: 'JSONL', desc: 'One test per line' },
  { ext: '.csv', label: 'CSV', desc: 'Single-turn tests' },
  { ext: '.xlsx', label: 'Excel', desc: 'Single-turn tests' },
];

const ACCEPTED_EXTENSIONS = '.json,.jsonl,.csv,.xlsx,.xls';

export default function FileImportDialog({
  open,
  onClose,
  sessionToken,
  onSuccess,
}: FileImportDialogProps) {
  const theme = useTheme();

  // Step tracking
  const [activeStep, setActiveStep] = React.useState(0);

  // Step 1: Upload & Map
  const [testType, setTestType] = React.useState<'Single-Turn' | 'Multi-Turn'>(
    'Single-Turn'
  );
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [analyzing, setAnalyzing] = React.useState(false);
  const [analyzeResult, setAnalyzeResult] =
    React.useState<AnalyzeResponse | null>(null);
  const [mapping, setMapping] = React.useState<Record<string, string>>({});

  // Step 2: Inspect
  const [parsing, setParsing] = React.useState(false);
  const [parseResult, setParseResult] = React.useState<ParseResponse | null>(
    null
  );
  const [previewPage, setPreviewPage] = React.useState<PreviewPage | null>(
    null
  );
  const [currentPage, setCurrentPage] = React.useState(1);
  const [loadingPage, setLoadingPage] = React.useState(false);

  // Step 3: Import
  const [testSetName, setTestSetName] = React.useState('');
  const [testSetDescription, setTestSetDescription] = React.useState('');
  const [importing, setImporting] = React.useState(false);
  const [importResult, setImportResult] =
    React.useState<ConfirmResponse | null>(null);

  // Common
  const [error, setError] = React.useState<string>();
  const [importId, setImportId] = React.useState<string>('');

  const clientFactory = React.useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  // ── Clean up on close ──────────────────────────────────────────

  const handleClose = async () => {
    if (importId && !importResult) {
      try {
        await clientFactory.getImportClient().cancelImport(importId);
      } catch {
        // Ignore cleanup errors
      }
    }
    resetState();
    onClose();
  };

  const resetState = () => {
    setActiveStep(0);
    setTestType('Single-Turn');
    setSelectedFile(null);
    setAnalyzing(false);
    setAnalyzeResult(null);
    setMapping({});
    setParsing(false);
    setParseResult(null);
    setPreviewPage(null);
    setCurrentPage(1);
    setLoadingPage(false);
    setTestSetName('');
    setTestSetDescription('');
    setImporting(false);
    setImportResult(null);
    setError(undefined);
    setImportId('');
  };

  // ── Step 1: Upload & Analyze ───────────────────────────────────

  const handleFileSelect = async (file: File) => {
    setSelectedFile(file);
    setError(undefined);
    setAnalyzeResult(null);
    setMapping({});

    try {
      setAnalyzing(true);
      const result = await clientFactory.getImportClient().analyzeFile(file);
      setAnalyzeResult(result);
      setImportId(result.import_id);
      setMapping(result.suggested_mapping);
      setTestSetName(`Import: ${file.name}`);

      if (result.confidence >= 1) {
        await handleParse(result.suggested_mapping, result.import_id);
      }
    } catch (err: any) {
      setError(getImportErrorMessage(err, 'Failed to analyze file'));
    } finally {
      setAnalyzing(false);
    }
  };

  const handleFileRemove = () => {
    setSelectedFile(null);
    setAnalyzeResult(null);
    setMapping({});
    setError(undefined);
  };

  const handleMappingChange = (sourceCol: string, targetField: string) => {
    setMapping(prev => {
      const next = { ...prev };
      if (targetField === '') {
        delete next[sourceCol];
      } else {
        next[sourceCol] = targetField;
      }
      return next;
    });
  };

  const handleRemapWithLlm = async () => {
    if (!importId) return;
    try {
      setAnalyzing(true);
      setError(undefined);
      const result = await clientFactory
        .getImportClient()
        .remapWithLlm(importId);
      if (!result.llm_available) {
        setError(result.message || 'No LLM available for AI-assisted mapping');
      } else {
        setMapping(result.mapping);
      }
    } catch (err: any) {
      setError(getImportErrorMessage(err, 'Failed to remap with AI'));
    } finally {
      setAnalyzing(false);
    }
  };

  // ── Step 2: Parse & Preview ────────────────────────────────────

  const handleParse = async (
    overrideMapping?: Record<string, string>,
    overrideImportId?: string
  ) => {
    const mappingToUse = overrideMapping ?? mapping;
    const importIdToUse = overrideImportId ?? importId;
    if (!importIdToUse) return;
    try {
      setParsing(true);
      setError(undefined);
      const result = await clientFactory
        .getImportClient()
        .parseWithMapping(importIdToUse, mappingToUse, testType);
      setParseResult(result);
      setPreviewPage(result.preview);
      setCurrentPage(1);
      setActiveStep(1);
    } catch (err: any) {
      setError(getImportErrorMessage(err, 'Failed to parse file'));
    } finally {
      setParsing(false);
    }
  };

  const handlePageChange = async (
    _event: React.ChangeEvent<unknown>,
    page: number
  ) => {
    if (!importId) return;
    try {
      setLoadingPage(true);
      const result = await clientFactory
        .getImportClient()
        .getPreviewPage(importId, page);
      setPreviewPage(result);
      setCurrentPage(page);
    } catch (err: any) {
      setError(getImportErrorMessage(err, 'Failed to load page'));
    } finally {
      setLoadingPage(false);
    }
  };

  // ── Step 3: Confirm Import ─────────────────────────────────────

  const handleConfirm = async () => {
    if (!importId) return;
    try {
      setImporting(true);
      setError(undefined);
      const result = await clientFactory
        .getImportClient()
        .confirmImport(importId, {
          name: testSetName || undefined,
          description: testSetDescription || undefined,
        });
      setImportResult(result);
      onSuccess?.(result.id);
    } catch (err: any) {
      setError(getImportErrorMessage(err, 'Failed to create test set'));
    } finally {
      setImporting(false);
    }
  };

  // ── Target field options for mapping dropdowns ─────────────────

  const TARGET_FIELDS = [
    { value: '', label: '(skip)' },
    { value: 'category', label: 'Category' },
    { value: 'topic', label: 'Topic' },
    { value: 'behavior', label: 'Behavior' },
    { value: 'prompt_content', label: 'Prompt Content' },
    { value: 'expected_response', label: 'Expected Response' },
    { value: 'language_code', label: 'Language Code' },
    ...(testType === 'Multi-Turn'
      ? [{ value: 'test_configuration', label: 'Test Configuration' }]
      : []),
    { value: 'metadata', label: 'Metadata' },
  ];

  // ── Preview DataGrid columns ───────────────────────────────────

  const getPreviewColumns = (): GridColDef[] => {
    const indexColWidth = Number(theme.spacing(7.5).replace('px', ''));
    const statusColWidth = Number(theme.spacing(10).replace('px', ''));
    const dataColMinWidth = Number(theme.spacing(15).replace('px', ''));
    const cols: GridColDef[] = [
      {
        field: 'index',
        headerName: '#',
        width: indexColWidth,
        sortable: false,
      },
      {
        field: 'status',
        headerName: 'Status',
        width: statusColWidth,
        sortable: false,
        renderCell: params => {
          const row = params.row as PreviewRow;
          if (row.errors.length > 0) {
            return (
              <Tooltip title={row.errors.map(e => e.message).join(', ')}>
                <ErrorOutlineIcon color="error" fontSize="small" />
              </Tooltip>
            );
          }
          if (row.warnings.length > 0) {
            return (
              <Tooltip title={row.warnings.map(w => w.message).join(', ')}>
                <WarningAmberIcon color="warning" fontSize="small" />
              </Tooltip>
            );
          }
          return <CheckCircleIcon color="success" fontSize="small" />;
        },
      },
    ];

    // Add columns for the mapped data keys
    const allKeys = new Set<string>();
    previewPage?.rows.forEach(row => {
      Object.keys(row.data).forEach(k => allKeys.add(k));
    });

    for (const key of Array.from(allKeys).sort()) {
      // Capitalize header: convert snake_case to Title Case
      const headerName = key
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');

      cols.push({
        field: `data_${key}`,
        headerName,
        flex: 1,
        minWidth: dataColMinWidth,
        sortable: false,
        valueGetter: (value, row) => {
          const cellValue = row.data?.[key];
          if (cellValue === null || cellValue === undefined) return '';

          // Special handling for prompt: show just the content
          if (
            key === 'prompt' &&
            typeof cellValue === 'object' &&
            cellValue.content
          ) {
            return String(cellValue.content);
          }

          // For other objects, stringify
          if (typeof cellValue === 'object') return JSON.stringify(cellValue);
          return String(cellValue);
        },
      });
    }

    return cols;
  };

  const getPreviewRows = () => {
    if (!previewPage) return [];
    return previewPage.rows.map(row => ({
      ...row,
      id: row.index,
      index: row.index + 1, // Display row numbers starting from 1
    }));
  };

  // ── Render ─────────────────────────────────────────────────────

  const renderStep0 = () => (
    <Stack spacing={3}>
      {/* Format info */}
      <Box>
        <Typography variant="subtitle2" gutterBottom>
          Supported Formats
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {SUPPORTED_FORMATS.map(f => (
            <Tooltip key={f.ext} title={f.desc}>
              <Chip label={f.label} size="small" variant="outlined" />
            </Tooltip>
          ))}
        </Stack>
      </Box>

      {/* Test type selection */}
      <Box>
        <Typography variant="subtitle2" gutterBottom>
          Test Type
        </Typography>
        <Stack direction="row" spacing={1}>
          <Chip
            label="Single-Turn"
            color={testType === 'Single-Turn' ? 'primary' : 'default'}
            variant={testType === 'Single-Turn' ? 'filled' : 'outlined'}
            onClick={() => setTestType('Single-Turn')}
            sx={{
              fontWeight: testType === 'Single-Turn' ? 'bold' : 'normal',
            }}
          />
          <Chip
            label="Multi-Turn"
            color={testType === 'Multi-Turn' ? 'primary' : 'default'}
            variant={testType === 'Multi-Turn' ? 'filled' : 'outlined'}
            onClick={() => setTestType('Multi-Turn')}
            sx={{
              fontWeight: testType === 'Multi-Turn' ? 'bold' : 'normal',
            }}
          />
        </Stack>
      </Box>

      {/* Expected data structure (adapts to selected test type) */}
      <Alert severity="info" variant="outlined">
        {testType === 'Single-Turn' ? (
          <Typography variant="body2">
            <strong>Single-turn tests:</strong> Each row should have a prompt,
            category, topic, and behavior. Optionally include expected_response
            and language_code.
          </Typography>
        ) : (
          <>
            <Typography variant="body2">
              <strong>Multi-turn tests:</strong> Each row should have category,
              topic, and behavior. Additionally, include <strong>goal</strong>{' '}
              (required), <strong>instructions</strong> (optional),{' '}
              <strong>restrictions</strong> (optional), and{' '}
              <strong>scenario</strong> (optional) to configure multi-turn
              conversation testing.
            </Typography>
            <Typography variant="caption" component="div" sx={{ mt: 0.5 }}>
              • <strong>goal:</strong> The objective of the conversation test
              <br />• <strong>instructions:</strong> How the test agent should
              conduct the test
              <br />• <strong>restrictions:</strong> Forbidden behaviors for the
              target system
              <br />• <strong>scenario:</strong> Contextual framing for the test
            </Typography>
            <Typography
              variant="body2"
              sx={{ mt: 1, fontStyle: 'italic', color: 'text.secondary' }}
            >
              Note: Multi-turn tests do not require a prompt field. The
              conversation is driven by the test configuration.
            </Typography>
          </>
        )}
      </Alert>

      {/* File upload */}
      <DragAndDropUpload
        onFileSelect={handleFileSelect}
        onFileRemove={handleFileRemove}
        selectedFile={selectedFile}
        accept={ACCEPTED_EXTENSIONS}
        maxSize={10 * 1024 * 1024}
        disabled={analyzing}
      />

      {analyzing && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CircularProgress size="small" />
          <Typography variant="body2" color="text.secondary">
            Analyzing file...
          </Typography>
        </Box>
      )}

      {/* Mapping section */}
      {analyzeResult && (
        <Box>
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            sx={{ mb: 1 }}
          >
            <Typography variant="subtitle2">Column Mapping</Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip
                label={`Confidence: ${Math.round(analyzeResult.confidence * 100)}%`}
                size="small"
                color={analyzeResult.confidence >= 0.7 ? 'success' : 'warning'}
              />
              {analyzeResult.llm_available && (
                <Tooltip title="Re-map using AI">
                  <IconButton
                    size="small"
                    onClick={handleRemapWithLlm}
                    disabled={analyzing}
                  >
                    <AutoFixHighIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}
            </Stack>
          </Stack>

          <Paper
            variant="outlined"
            sx={{ p: 2, maxHeight: theme.spacing(37.5), overflow: 'auto' }}
          >
            <Stack spacing={1.5}>
              {analyzeResult.headers.map(header => (
                <Stack
                  key={header}
                  direction="row"
                  spacing={2}
                  alignItems="center"
                >
                  <Typography
                    variant="body2"
                    sx={{
                      minWidth: theme.spacing(18),
                      fontFamily: 'monospace',
                      fontWeight: 'medium',
                    }}
                  >
                    {header}
                  </Typography>
                  <ArrowForwardIcon
                    sx={{ color: 'text.disabled' }}
                    fontSize="small"
                  />
                  <FormControl
                    size="small"
                    sx={{ minWidth: theme.spacing(22) }}
                  >
                    <Select
                      value={mapping[header] || ''}
                      onChange={e =>
                        handleMappingChange(header, e.target.value)
                      }
                      displayEmpty
                    >
                      {TARGET_FIELDS.map(tf => (
                        <MenuItem key={tf.value} value={tf.value}>
                          {tf.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Stack>
              ))}
            </Stack>
          </Paper>

          {/* Sample data preview */}
          {analyzeResult.sample_rows.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Sample Data (first {analyzeResult.sample_rows.length} rows)
              </Typography>
              <Paper
                variant="outlined"
                sx={{
                  p: 1,
                  maxHeight: theme.spacing(25),
                  overflow: 'auto',
                  backgroundColor: themeArg =>
                    alpha(themeArg.palette.background.default, 0.5),
                }}
              >
                <Typography
                  component="pre"
                  variant="caption"
                  sx={{
                    m: 0,
                    fontFamily: 'monospace',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(analyzeResult.sample_rows, null, 2)}
                </Typography>
              </Paper>
            </Box>
          )}
        </Box>
      )}
    </Stack>
  );

  const renderStep1 = () => {
    const summary = parseResult?.validation_summary;
    return (
      <Stack spacing={2}>
        {/* Validation summary */}
        {summary && (
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <Chip
              icon={<CheckCircleIcon />}
              label={`${summary.valid_rows} valid`}
              color="success"
              variant="outlined"
              size="small"
            />
            {summary.error_count > 0 && (
              <Chip
                icon={<ErrorOutlineIcon />}
                label={`${summary.error_count} errors`}
                color="error"
                variant="outlined"
                size="small"
              />
            )}
            {summary.warning_count > 0 && (
              <Chip
                icon={<WarningAmberIcon />}
                label={`${summary.warning_count} warnings`}
                color="warning"
                variant="outlined"
                size="small"
              />
            )}
            <Chip
              label={`${summary.total_rows} total rows`}
              variant="outlined"
              size="small"
            />
          </Stack>
        )}

        {/* Data preview grid */}
        {previewPage && (
          <Box sx={{ height: theme.spacing(50), width: '100%' }}>
            {loadingPage && <LinearProgress />}
            <DataGrid
              rows={getPreviewRows()}
              columns={getPreviewColumns()}
              hideFooter
              disableColumnMenu
              density="compact"
              loading={loadingPage}
              sx={{
                '& .MuiDataGrid-cell': {
                  fontSize: theme.typography.body2.fontSize,
                },
              }}
            />
            {previewPage.total_pages > 1 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
                <Pagination
                  count={previewPage.total_pages}
                  page={currentPage}
                  onChange={handlePageChange}
                  size="small"
                />
              </Box>
            )}
          </Box>
        )}
      </Stack>
    );
  };

  const renderStep2 = () => {
    if (importResult) {
      return (
        <Stack spacing={2} alignItems="center" sx={{ py: 4 }}>
          <CheckCircleIcon
            sx={{ fontSize: theme.spacing(8), color: 'success.main' }}
          />
          <Typography variant="h6">Import Complete!</Typography>
          <Typography variant="body2" color="text.secondary">
            Test set &quot;{importResult.name}&quot; has been created
            successfully.
          </Typography>
        </Stack>
      );
    }

    const summary = parseResult?.validation_summary;
    return (
      <Stack spacing={3}>
        <TextField
          label="Test Set Name"
          fullWidth
          value={testSetName}
          onChange={e => setTestSetName(e.target.value)}
          size="small"
        />
        <TextField
          label="Description (optional)"
          fullWidth
          multiline
          rows={2}
          value={testSetDescription}
          onChange={e => setTestSetDescription(e.target.value)}
          size="small"
        />

        {summary && (
          <Alert
            severity={summary.error_count > 0 ? 'warning' : 'success'}
            variant="outlined"
          >
            <Typography variant="body2">
              {summary.valid_rows} of {summary.total_rows} rows will be
              imported.
              {summary.error_count > 0 && (
                <>
                  {' '}
                  {summary.total_rows - summary.valid_rows} row(s) with errors
                  will be excluded.
                </>
              )}
            </Typography>
          </Alert>
        )}

        {importing && (
          <Box sx={{ width: '100%' }}>
            <LinearProgress />
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mt: 1, textAlign: 'center' }}
            >
              Creating test set...
            </Typography>
          </Box>
        )}
      </Stack>
    );
  };

  const canProceed = () => {
    switch (activeStep) {
      case 0:
        return (
          analyzeResult !== null &&
          Object.keys(mapping).length > 0 &&
          !analyzing
        );
      case 1:
        return parseResult !== null && !loadingPage;
      case 2:
        return !importing && !importResult;
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (activeStep === 0) {
      handleParse();
    } else if (activeStep === 1) {
      setActiveStep(2);
    } else if (activeStep === 2) {
      handleConfirm();
    }
  };

  const handleBack = () => {
    if (activeStep > 0) {
      setActiveStep(activeStep - 1);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { minHeight: theme.spacing(62.5) },
      }}
    >
      <DialogTitle>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
        >
          <Typography variant="h6">Import Test Set from File</Typography>
          <IconButton onClick={handleClose} size="small">
            <CloseIcon />
          </IconButton>
        </Stack>
      </DialogTitle>

      <DialogContent dividers>
        <Box sx={{ mb: 3 }}>
          <Stepper activeStep={activeStep} alternativeLabel>
            {STEPS.map(label => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Box>

        {error && (
          <Alert
            severity="error"
            onClose={() => setError(undefined)}
            sx={{ mb: 2 }}
          >
            {error}
          </Alert>
        )}

        {activeStep === 0 && renderStep0()}
        {activeStep === 1 && renderStep1()}
        {activeStep === 2 && renderStep2()}
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        {importResult ? (
          <Button onClick={handleClose} variant="contained">
            Done
          </Button>
        ) : (
          <>
            <Button onClick={handleClose} disabled={importing}>
              Cancel
            </Button>
            {activeStep > 0 && (
              <Button
                variant="outlined"
                onClick={handleBack}
                disabled={importing || parsing}
              >
                Back
              </Button>
            )}
            <Button
              variant="contained"
              onClick={handleNext}
              disabled={!canProceed()}
              startIcon={
                activeStep === 2 && importing ? (
                  <CircularProgress size="small" />
                ) : undefined
              }
            >
              {activeStep === 0 && (parsing ? 'Parsing...' : 'Next')}
              {activeStep === 1 && 'Next'}
              {activeStep === 2 && (importing ? 'Importing...' : 'Import')}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}
