'use client';

import { useRef, useState } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Chip,
  Collapse,
  Alert,
  Grid,
} from '@mui/material';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import ViewField from '@/components/common/ViewField';
import { variableChipSx, testPreviewSx } from './endpoint-styles';
import { JsonPreview, TemplatePreview } from './JsonPreview';
import {
  FileUploadIcon,
  KeyboardArrowDownIcon,
  KeyboardArrowUpIcon,
} from '@/components/icons';

const FILE_VAR_RE = /^(files?|images?)$/i;

export interface EndpointTestWorkbenchProps {
  method: string;
  url: string;
  requestTemplate: string;
  responseMapping: Record<string, string>;
  pathToVar: Record<string, string>;
  inputVars: string[];
  varValues: Record<string, string>;
  onVarValuesChange: (values: Record<string, string>) => void;
  fileValues: Record<string, File[]>;
  onFileValuesChange: (values: Record<string, File[]>) => void;
  curlText: string;
  rawResponse: unknown | null;
  statusCode: string;
  mappedValues: Record<string, unknown>;
  isTestingEndpoint: boolean;
  error?: string | null;
}

function formatMappedValue(val: unknown): string {
  if (val === undefined) return '';
  if (typeof val === 'string') return val;
  return JSON.stringify(val, null, 2);
}

export default function EndpointTestWorkbench({
  method,
  url,
  requestTemplate,
  responseMapping,
  pathToVar,
  inputVars,
  varValues,
  onVarValuesChange,
  fileValues,
  onFileValuesChange,
  curlText,
  rawResponse,
  statusCode,
  mappedValues,
  isTestingEndpoint,
  error,
}: EndpointTestWorkbenchProps) {
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const [curlExpanded, setCurlExpanded] = useState(false);
  const [rawExpanded, setRawExpanded] = useState(false);

  const rawResponseText = (() => {
    if (!rawResponse) return '';
    try {
      return JSON.stringify(rawResponse, null, 2);
    } catch {
      return String(rawResponse);
    }
  })();

  const isSuccess = statusCode.startsWith('2');

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <Box>
        <FormSectionDivider
          headline="Request preview"
          descriptiveText={`${method || 'POST'} ${url || '—'}`}
        />
        <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <Button
              size="small"
              variant="text"
              onClick={() => setCurlExpanded(v => !v)}
              endIcon={
                curlExpanded ? (
                  <KeyboardArrowUpIcon />
                ) : (
                  <KeyboardArrowDownIcon />
                )
              }
              sx={{ mb: 1, color: 'text.secondary', textTransform: 'none' }}
            >
              cURL command
            </Button>
            <Collapse in={curlExpanded}>
              <Box component="pre" sx={testPreviewSx}>
                {curlText}
              </Box>
            </Collapse>
          </Box>
          <ViewField label="Request body template">
            <Box
              component="pre"
              sx={{ ...testPreviewSx, p: 0, minHeight: 'unset' }}
            >
              <TemplatePreview template={requestTemplate || '{}'} />
            </Box>
          </ViewField>
        </Box>
      </Box>

      <Box>
        <FormSectionDivider
          headline="Input variables"
          descriptiveText="Values Rhesis substitutes into the request before sending."
        />
        <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {inputVars.length === 0 ? (
            <Typography variant="body2" sx={{ color: 'text.disabled' }}>
              No template variables in request body.
            </Typography>
          ) : (
            inputVars.map(v => (
              <Box
                key={v}
                sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}
              >
                <Chip
                  label={`{{ ${v} }}`}
                  size="small"
                  sx={{ ...variableChipSx, flexShrink: 0, mt: 0.5 }}
                />
                {FILE_VAR_RE.test(v) ? (
                  <>
                    <input
                      type="file"
                      multiple
                      ref={el => {
                        fileInputRefs.current[v] = el;
                      }}
                      style={{ display: 'none' }}
                      onChange={e =>
                        onFileValuesChange({
                          ...fileValues,
                          [v]: Array.from(e.target.files ?? []),
                        })
                      }
                    />
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<FileUploadIcon />}
                      onClick={() => fileInputRefs.current[v]?.click()}
                    >
                      {(fileValues[v]?.length ?? 0) > 0
                        ? fileValues[v].map(f => f.name).join(', ')
                        : 'Upload'}
                    </Button>
                  </>
                ) : (
                  <TextField
                    size="small"
                    fullWidth
                    multiline={v === 'input' || v === 'system_prompt'}
                    maxRows={4}
                    placeholder={
                      v === 'conversation_id'
                        ? 'Auto-filled from last response'
                        : ''
                    }
                    value={varValues[v] ?? ''}
                    onChange={e =>
                      onVarValuesChange({ ...varValues, [v]: e.target.value })
                    }
                  />
                )}
              </Box>
            ))
          )}
        </Box>
      </Box>

      <Box>
        <FormSectionDivider
          headline="Response"
          descriptiveText={
            isTestingEndpoint
              ? 'Waiting for response…'
              : statusCode
                ? `Status: ${statusCode}`
                : 'Run a test to see the response.'
          }
        />
        <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {statusCode ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  bgcolor: isSuccess ? 'success.main' : 'error.main',
                }}
              />
              <Typography
                variant="body2"
                sx={{
                  fontFamily: 'monospace',
                  fontWeight: 700,
                  color: isSuccess ? 'success.main' : 'error.main',
                }}
              >
                {statusCode}
              </Typography>
              {rawResponse != null && (
                <Button
                  size="small"
                  variant="text"
                  onClick={() => setRawExpanded(v => !v)}
                  endIcon={
                    rawExpanded ? (
                      <KeyboardArrowUpIcon />
                    ) : (
                      <KeyboardArrowDownIcon />
                    )
                  }
                  sx={{
                    ml: 'auto',
                    color: 'text.secondary',
                    textTransform: 'none',
                  }}
                >
                  Raw response
                </Button>
              )}
            </Box>
          ) : null}
          {rawResponse != null && (
            <Collapse in={rawExpanded}>
              <Box component="pre" sx={testPreviewSx}>
                {rawResponseText}
              </Box>
            </Collapse>
          )}
          <ViewField label="Mapped response preview">
            {rawResponse != null ? (
              <Box
                component="pre"
                sx={{ ...testPreviewSx, p: 0, minHeight: 'unset' }}
              >
                <JsonPreview value={rawResponse} pathToVar={pathToVar} />
              </Box>
            ) : (
              <Typography
                sx={{
                  fontSize: 12,
                  lineHeight: '24px',
                  color: theme => theme.palette.greyscale.subtitle,
                  fontFamily: 'monospace',
                }}
              >
                Run a test to see the response
              </Typography>
            )}
          </ViewField>
        </Box>
      </Box>

      <Box>
        <FormSectionDivider
          headline="Mapped output"
          descriptiveText="Values Rhesis extracts using your response mapping."
        />
        <Box sx={{ mt: 2 }}>
          {Object.keys(responseMapping).length === 0 ? (
            <Typography variant="body2" sx={{ color: 'text.disabled' }}>
              No response mapping configured yet.
            </Typography>
          ) : (
            <Grid container spacing={2}>
              {Object.entries(responseMapping).map(([varName, path]) => {
                const val = mappedValues[varName];
                const display = formatMappedValue(val);
                return (
                  <Grid
                    key={varName}
                    size={{
                      xs: 12,
                      md: Object.keys(responseMapping).length > 1 ? 6 : 12,
                    }}
                  >
                    <ViewField
                      label={`{{ ${varName} }}`}
                      value={display || undefined}
                      helperText={rawResponse ? undefined : path}
                      multiline
                      inputSx={{ fontFamily: 'monospace', fontSize: 12 }}
                    />
                  </Grid>
                );
              })}
            </Grid>
          )}
        </Box>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}
    </Box>
  );
}
