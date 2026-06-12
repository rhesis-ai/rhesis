'use client';

import React, { useRef, useState } from 'react';
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
import {
  variableChipSx,
  testPreviewSx,
  fieldSurfaceBoxSx,
} from './endpoint-styles';
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

  const varRow = (
    key: string,
    chip: React.ReactNode,
    content: React.ReactNode
  ) => (
    <Box key={key} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
      <Box sx={{ flexShrink: 0, pt: '7px' }}>{chip}</Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>{content}</Box>
    </Box>
  );

  return (
    <Grid container spacing={4}>
      {/* Row 1: Input variables | Mapped output */}
      <Grid size={{ xs: 12, md: 6 }}>
        <FormSectionDivider
          headline="Mapped Input"
          descriptiveText="Values Rhesis substitutes into the request before sending."
        />
        <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {inputVars.length === 0 ? (
            <Typography variant="body2" sx={{ color: 'text.disabled' }}>
              No template variables in request body.
            </Typography>
          ) : (
            inputVars.map(v =>
              varRow(
                v,
                <Chip label={`{{ ${v} }}`} size="small" sx={variableChipSx} />,
                FILE_VAR_RE.test(v) ? (
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
                    key={v}
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
                )
              )
            )
          )}
        </Box>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <FormSectionDivider
          headline="Mapped Output"
          descriptiveText="Values Rhesis extracts using your response mapping."
        />
        <Box
          sx={{
            mt: 2,
            display: 'grid',
            gridTemplateColumns: 'max-content 1fr',
            gap: '12px 12px',
            alignItems: 'start',
          }}
        >
          {Object.keys(responseMapping).length === 0 ? (
            <Typography
              variant="body2"
              sx={{ color: 'text.disabled', gridColumn: '1 / -1' }}
            >
              No response mapping configured yet.
            </Typography>
          ) : (
            Object.entries(responseMapping).map(([varName, path]) => {
              const display = formatMappedValue(mappedValues[varName]);
              return (
                <React.Fragment key={varName}>
                  <Box sx={{ pt: '5px' }}>
                    <Chip
                      label={`{{ ${varName} }}`}
                      size="small"
                      sx={variableChipSx}
                    />
                  </Box>
                  <Box>
                    <Box sx={fieldSurfaceBoxSx}>
                      <Typography
                        sx={{
                          fontSize: 12,
                          lineHeight: '20px',
                          color: theme => theme.palette.greyscale.body,
                          fontFamily: 'monospace',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {display || '—'}
                      </Typography>
                    </Box>
                    {!rawResponse && path && (
                      <Typography
                        sx={{
                          fontSize: 11,
                          color: theme => theme.palette.greyscale.subtitle,
                          fontFamily: 'monospace',
                          pt: '3px',
                        }}
                      >
                        {path}
                      </Typography>
                    )}
                  </Box>
                </React.Fragment>
              );
            })
          )}
        </Box>
      </Grid>

      {/* Row 2a: section headings */}
      <Grid size={{ xs: 12, md: 6 }}>
        <FormSectionDivider headline="Request" />
      </Grid>
      <Grid size={{ xs: 12, md: 6 }}>
        <FormSectionDivider
          headline="Response"
          descriptiveText={
            isTestingEndpoint ? 'Waiting for response…' : undefined
          }
        />
      </Grid>

      {/* Row 2b: URL | empty — same CSS grid row keeps them equal height */}
      <Grid size={{ xs: 12, md: 6 }}>
        <Typography
          variant="body2"
          sx={{
            fontFamily: 'monospace',
            fontSize: 12,
            color: 'text.secondary',
          }}
        >
          {method || 'POST'} {url || '—'}
        </Typography>
      </Grid>
      <Grid size={{ xs: 12, md: 6 }}>
        {statusCode && (
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
          </Box>
        )}
      </Grid>

      {/* Row 2c: JSON blocks — aligned */}
      <Grid size={{ xs: 12, md: 6 }}>
        <Box component="pre" sx={{ ...testPreviewSx, minHeight: 'unset' }}>
          <TemplatePreview template={requestTemplate || '{}'} />
        </Box>
      </Grid>
      <Grid size={{ xs: 12, md: 6 }}>
        {rawResponse != null ? (
          <Box component="pre" sx={{ ...testPreviewSx, minHeight: 'unset' }}>
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
      </Grid>

      {/* Row 2d: secondary controls */}
      <Grid size={{ xs: 12, md: 6 }}>
        {(rawResponse != null || !!statusCode) && (
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
        )}
      </Grid>
      <Grid size={{ xs: 12, md: 6 }}>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-start',
            gap: 2,
          }}
        >
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
              sx={{ color: 'text.secondary', textTransform: 'none' }}
            >
              Raw response
            </Button>
          )}
          {rawResponse != null && (
            <Collapse in={rawExpanded}>
              <Box component="pre" sx={testPreviewSx}>
                {rawResponseText}
              </Box>
            </Collapse>
          )}
          {error && <Alert severity="error">{error}</Alert>}
        </Box>
      </Grid>
    </Grid>
  );
}
