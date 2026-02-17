'use client';

import React, { useMemo, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Alert,
  Chip,
  Switch,
  FormControlLabel,
  Collapse,
  IconButton,
  Stepper,
  Step,
  StepLabel,
} from '@mui/material';
import { LoadingButton } from '@mui/lab';
import { useTheme } from '@mui/material/styles';
import dynamic from 'next/dynamic';
import { AutoFixHighIcon, CloseIcon, RefreshIcon } from '@/components/icons';
import { AutoConfigureResult } from '@/utils/api-client/interfaces/endpoint';
import { autoConfigureEndpoint } from '@/actions/endpoints/auto-configure';

// Lazy load Monaco Editor
const Editor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => (
    <Box
      sx={{
        height: '200px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        border: 1,
        borderColor: 'divider',
        borderRadius: theme => `${theme.shape.borderRadius}px`,
        backgroundColor: 'background.default',
      }}
    >
      <Typography variant="body2" color="text.secondary">
        Loading editor...
      </Typography>
    </Box>
  ),
});

const STEPS = ['Provide Input', 'Review Mappings'];

/**
 * Detect likely API keys/tokens in user input.
 * Environment-variable references ($VAR, ${VAR}) are excluded.
 */
const SECRET_PATTERNS = [
  /sk-proj-[A-Za-z0-9_-]{20,}/,
  /sk-ant-[A-Za-z0-9_-]{20,}/,
  /sk-[A-Za-z0-9_-]{20,}/,
  /AKIA[0-9A-Z]{16}/,
  /AIza[0-9A-Za-z_-]{35}/,
  /Bearer\s+[A-Za-z0-9._-]{20,}/,
];

/** Environment-variable placeholder pattern. */
const ENV_VAR_RE = /\$\{?\w+\}?/g;

function containsApiKey(text: string): boolean {
  if (!text) return false;
  // Strip env-var references so they don't trigger false positives
  const stripped = text.replace(ENV_VAR_RE, '');
  return SECRET_PATTERNS.some(pattern => pattern.test(stripped));
}

interface AutoConfigureModalProps {
  open: boolean;
  onClose: () => void;
  onApply: (result: AutoConfigureResult) => void;
  url: string;
  authToken: string;
  method: string;
}

export default function AutoConfigureModal({
  open,
  onClose,
  onApply,
  url,
  authToken,
  method,
}: AutoConfigureModalProps) {
  const theme = useTheme();
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';

  const [activeStep, setActiveStep] = useState(0);
  const [inputText, setInputText] = useState('');
  const [probe, setProbe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AutoConfigureResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showProbeResponse, setShowProbeResponse] = useState(false);
  const [showReasoning, setShowReasoning] = useState(false);

  const handleAutoConfigure = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await autoConfigureEndpoint({
        input_text: inputText,
        url,
        auth_token: authToken,
        method,
        probe,
      });

      if (!response.success) {
        setError(response.error || 'Auto-configure failed');
        return;
      }

      if (response.data) {
        setResult(response.data);
        setActiveStep(1);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'An unexpected error occurred'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setActiveStep(0);
    setResult(null);
    setError(null);
    setShowProbeResponse(false);
    setShowReasoning(false);
    onClose();
  };

  const handleApply = () => {
    if (result) {
      onApply(result);
      setActiveStep(0);
      setResult(null);
      setError(null);
      setInputText('');
    }
  };

  const handleBack = () => {
    setActiveStep(0);
    setResult(null);
    setError(null);
    setShowProbeResponse(false);
    setShowReasoning(false);
  };

  const getConfidenceColor = (
    confidence: number
  ): 'success' | 'warning' | 'error' => {
    if (confidence >= 0.7) return 'success';
    if (confidence >= 0.4) return 'warning';
    return 'error';
  };

  const getConfidenceLabel = (confidence: number): string => {
    if (confidence >= 0.7) return 'High';
    if (confidence >= 0.4) return 'Medium';
    return 'Low';
  };

  const hasApiKey = useMemo(() => containsApiKey(inputText), [inputText]);

  const editorWrapperStyle = {
    border: 1,
    borderColor: 'divider',
    borderRadius: `${theme.shape.borderRadius}px`,
    overflow: 'hidden',
  };

  // Monaco expects fontSize as a plain number in pixels.
  // Convert theme rem value (e.g. "0.875rem") to px using the root font size.
  const htmlFontSize = theme.typography.htmlFontSize ?? 16;
  const rawSize = theme.typography.body2.fontSize;
  const editorFontSize =
    typeof rawSize === 'string' && rawSize.endsWith('rem')
      ? parseFloat(rawSize) * htmlFontSize
      : typeof rawSize === 'number'
        ? rawSize
        : 14;

  const readOnlyEditorOptions = {
    readOnly: true,
    minimap: { enabled: false },
    lineNumbers: 'off' as const,
    folding: true,
    scrollBeyondLastLine: false,
    automaticLayout: true,
    wordWrap: 'on' as const,
    padding: {
      top: Number(theme.spacing(1)),
      bottom: Number(theme.spacing(1)),
    },
    fontSize: editorFontSize,
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      fullWidth
      maxWidth="md"
      aria-labelledby="auto-configure-dialog-title"
    >
      <DialogTitle
        id="auto-configure-dialog-title"
        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
      >
        <AutoFixHighIcon />
        Auto-configure Endpoint
        <Box sx={{ flexGrow: 1 }} />
        <IconButton onClick={handleClose} size="small" aria-label="close">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        {/* Stepper */}
        <Stepper activeStep={activeStep} alternativeLabel sx={{ py: 2, mb: 2 }}>
          {STEPS.map(label => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {/* Step 1: Provide Input */}
        {activeStep === 0 && (
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Paste anything about your endpoint
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Paste a curl command, Python code, route definition, API docs, or
              any description of your endpoint. The AI will analyze it and
              generate request/response mappings.
            </Typography>
            <Box sx={editorWrapperStyle}>
              <Editor
                height="200px"
                defaultLanguage="plaintext"
                theme={editorTheme}
                value={inputText}
                onChange={value => setInputText(value || '')}
                options={{
                  minimap: { enabled: false },
                  lineNumbers: 'off',
                  folding: false,
                  scrollBeyondLastLine: false,
                  automaticLayout: true,
                  wordWrap: 'on',
                  padding: {
                    top: Number(theme.spacing(1)),
                    bottom: Number(theme.spacing(1)),
                  },
                  fontSize: editorFontSize,
                }}
              />
            </Box>

            {/* API key warning */}
            {hasApiKey && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  <strong>API key detected.</strong> Remove real API keys before
                  continuing — they are not needed here. Use environment
                  variable placeholders like <code>$API_KEY</code> instead. Any
                  remaining keys will be redacted automatically before analysis.
                </Typography>
              </Alert>
            )}

            {/* Probe toggle */}
            <FormControlLabel
              control={
                <Switch
                  checked={probe}
                  onChange={e => setProbe(e.target.checked)}
                  size="small"
                />
              }
              label={
                <Typography variant="body2" color="text.secondary">
                  Send a test request to verify the configuration
                </Typography>
              }
              sx={{ mt: 2 }}
            />

            {/* Error display (stays on step 1) */}
            {error && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {error}
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Try pasting a curl command, a sample request/response JSON, or
                  the source code of your endpoint&apos;s route handler.
                </Typography>
              </Alert>
            )}
          </Box>
        )}

        {/* Step 2: Review Mappings */}
        {activeStep === 1 && result && (
          <Box>
            {/* Status and confidence */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                mb: 2,
              }}
            >
              <Chip
                label={`Confidence: ${getConfidenceLabel(result.confidence)}`}
                color={getConfidenceColor(result.confidence)}
                size="small"
                variant="outlined"
              />
              <Typography variant="body2" color="text.secondary">
                ({Math.round(result.confidence * 100)}%)
              </Typography>
              {result.status === 'partial' && (
                <Chip label="Partial" color="warning" size="small" />
              )}
            </Box>

            {/* Warnings */}
            {result.warnings && result.warnings.length > 0 && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                <Typography variant="body2" fontWeight="bold" sx={{ mb: 0.5 }}>
                  Warnings:
                </Typography>
                {result.warnings.map(warning => (
                  <Typography key={warning} variant="body2">
                    &bull; {warning}
                  </Typography>
                ))}
              </Alert>
            )}

            {/* Probe error */}
            {result.probe_error && !result.probe_success && (
              <Alert severity="info" sx={{ mb: 2 }}>
                <Typography variant="body2">
                  Probe error: {result.probe_error}
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  The mapping may need manual adjustments. Use &quot;Test
                  Connection&quot; to debug.
                </Typography>
              </Alert>
            )}

            {/* Reasoning (collapsible) */}
            {result.reasoning && (
              <Box sx={{ mb: 2 }}>
                <Button
                  size="small"
                  onClick={() => setShowReasoning(!showReasoning)}
                  sx={{ textTransform: 'none', p: 0 }}
                >
                  {showReasoning ? 'Hide reasoning' : 'Show reasoning'}
                </Button>
                <Collapse in={showReasoning}>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 1 }}
                  >
                    {result.reasoning}
                  </Typography>
                </Collapse>
              </Box>
            )}

            {/* Generated request mapping */}
            {result.request_mapping && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Request Mapping
                </Typography>
                <Box sx={editorWrapperStyle}>
                  <Editor
                    height="120px"
                    defaultLanguage="json"
                    theme={editorTheme}
                    value={JSON.stringify(result.request_mapping, null, 2)}
                    options={readOnlyEditorOptions}
                  />
                </Box>
              </Box>
            )}

            {/* Generated response mapping */}
            {result.response_mapping && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Response Mapping
                </Typography>
                <Box sx={editorWrapperStyle}>
                  <Editor
                    height="80px"
                    defaultLanguage="json"
                    theme={editorTheme}
                    value={JSON.stringify(result.response_mapping, null, 2)}
                    options={readOnlyEditorOptions}
                  />
                </Box>
              </Box>
            )}

            {/* Generated headers */}
            {result.request_headers && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Request Headers
                </Typography>
                <Box sx={editorWrapperStyle}>
                  <Editor
                    height="80px"
                    defaultLanguage="json"
                    theme={editorTheme}
                    value={JSON.stringify(result.request_headers, null, 2)}
                    options={readOnlyEditorOptions}
                  />
                </Box>
              </Box>
            )}

            {/* Probe response (collapsible) */}
            {result.probe_response && (
              <Box>
                <Button
                  size="small"
                  onClick={() => setShowProbeResponse(!showProbeResponse)}
                  sx={{ textTransform: 'none', p: 0 }}
                >
                  {showProbeResponse
                    ? 'Hide probe response'
                    : 'Show probe response'}
                </Button>
                <Collapse in={showProbeResponse}>
                  <Box sx={{ ...editorWrapperStyle, mt: 1 }}>
                    <Editor
                      height="120px"
                      defaultLanguage="json"
                      theme={editorTheme}
                      value={JSON.stringify(result.probe_response, null, 2)}
                      options={readOnlyEditorOptions}
                    />
                  </Box>
                </Collapse>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleClose}>Cancel</Button>
        <Box sx={{ flexGrow: 1 }} />
        {activeStep === 0 && (
          <>
            {loading ? (
              <LoadingButton
                variant="contained"
                loading
                loadingPosition="start"
                startIcon={<AutoFixHighIcon />}
              >
                Analyzing…
              </LoadingButton>
            ) : error ? (
              <Button
                variant="contained"
                onClick={handleAutoConfigure}
                disabled={!inputText.trim() || hasApiKey}
                startIcon={<RefreshIcon />}
              >
                Retry
              </Button>
            ) : (
              <Button
                variant="contained"
                onClick={handleAutoConfigure}
                disabled={!inputText.trim() || hasApiKey}
                startIcon={<AutoFixHighIcon />}
              >
                Auto-configure
              </Button>
            )}
          </>
        )}
        {activeStep === 1 && result && (
          <>
            <Button variant="outlined" onClick={handleBack}>
              Back
            </Button>
            <Button
              variant="outlined"
              onClick={() => {
                handleBack();
                // Small delay so user sees step 1 before re-running
                setTimeout(handleAutoConfigure, 100);
              }}
              disabled={!inputText.trim()}
              startIcon={<RefreshIcon />}
            >
              Retry
            </Button>
            <Button
              variant="contained"
              onClick={handleApply}
              disabled={!result.request_mapping && !result.response_mapping}
            >
              {result.status === 'partial'
                ? 'Apply Anyway'
                : 'Apply to Endpoint'}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}
