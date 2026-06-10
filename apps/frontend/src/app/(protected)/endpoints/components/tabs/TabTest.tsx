'use client';

import { useState, useMemo, useRef } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  Alert,
} from '@mui/material';
import { LoadingButton } from '@mui/lab';
import {
  PlayArrowIcon,
  ArrowRightAltIcon,
  FileUploadIcon,
  KeyboardArrowDownIcon,
  KeyboardArrowUpIcon,
} from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import {
  variableChipSx,
  testPanelSx,
  testPanelHeaderSx,
  testPreviewSx,
} from '../endpoint-styles';
import {
  JsonPreview,
  TemplatePreview,
  responseMappingToPathToVar,
} from '../JsonPreview';

const FILE_VAR_RE = /^(files?|images?)$/i;

function substituteVars(
  template: string,
  values: Record<string, string>
): string {
  // Replace "{{ varName }}" (string-quoted in JSON) → JSON-encoded value
  let result = template.replace(
    /"(\{\{\s*[\w.]+(?:\s*\|[^}]*)?\s*\}\})"/g,
    (match, _tpl, offset, str) => {
      const nameMatch = match.match(/\{\{\s*([\w.]+)/);
      if (!nameMatch) return match;
      const base = nameMatch[1].split('.')[0];
      return values[base] !== undefined ? JSON.stringify(values[base]) : match;
    }
  );
  // Replace remaining {{ varName }} unquoted
  result = result.replace(
    /\{\{\s*([\w.]+)(?:\s*\|[^}]*)?\s*\}\}/g,
    (_match, name) => {
      const base = name.split('.')[0];
      return values[base] !== undefined ? String(values[base]) : _match;
    }
  );
  return result;
}

const SENSITIVE_HEADERS = new Set(['authorization', 'x-api-key', 'api-key']);

function maskHeaders(headers: Record<string, string>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(headers).map(([k, v]) => {
      if (!SENSITIVE_HEADERS.has(k.toLowerCase())) return [k, v];
      const prefix = v.match(/^(Bearer\s+)/i)?.[1] ?? '';
      return [k, `${prefix}[hidden]`];
    })
  );
}

function buildCurl(
  method: string,
  url: string,
  headers: Record<string, string>,
  body: string
): string {
  const lines: string[] = [`curl -X ${method} '${url}'`];
  for (const [k, v] of Object.entries(maskHeaders(headers))) {
    lines.push(`  -H '${k}: ${v}'`);
  }
  const trimmed = body.trim();
  if (trimmed && trimmed !== '{}') {
    const pretty = (() => {
      try {
        return JSON.stringify(JSON.parse(trimmed), null, 2);
      } catch {
        return trimmed;
      }
    })();
    lines.push(`  -d '${pretty.replace(/'/g, "\\'")}'`);
  }
  return lines.join(' \\\n');
}

function extractVars(template: string): string[] {
  const vars = new Set<string>();
  for (const m of template.matchAll(/\{\{\s*([\w.]+)(?:\s*\|[^}]*)?\s*\}\}/g)) {
    vars.add(m[1].split('.')[0]);
  }
  return [...vars];
}

function applyJsonPath(obj: unknown, path: string): unknown {
  const cleaned = path.replace(/^\$\.?/, '');
  if (!cleaned) return obj;
  const parts: string[] = [];
  const re = /([^.[]+)|\[(\d+)\]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(cleaned)) !== null) parts.push(m[1] ?? m[2]);
  let cur: unknown = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object') return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return cur;
}

interface TestResult {
  success: boolean;
  response?: Record<string, unknown>;
  error?: string;
}

interface TabTestProps {
  url: string;
  method: string;
  reqBody: string;
  resBody: string;
  requestHeaders?: string;
  authToken?: string;
  testResult: TestResult | null;
  isTestingEndpoint: boolean;
  onRunTest: (inputData: Record<string, unknown>) => void;
}

export default function TabTest({
  url,
  method,
  reqBody,
  resBody,
  requestHeaders,
  authToken,
  testResult,
  isTestingEndpoint,
  onRunTest,
}: TabTestProps) {
  const responseMapping = useMemo<Record<string, string>>(() => {
    try {
      return JSON.parse(resBody);
    } catch {
      return {};
    }
  }, [resBody]);

  const inputVars = useMemo(() => extractVars(reqBody), [reqBody]);
  const pathToVar = useMemo(
    () => responseMappingToPathToVar(responseMapping),
    [responseMapping]
  );

  const [varValues, setVarValues] = useState<Record<string, string>>({});
  const [fileValues, setFileValues] = useState<Record<string, File[]>>({});
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const [reqExpanded, setReqExpanded] = useState(false);
  const [resExpanded, setResExpanded] = useState(false);

  const resolvedHeaders = useMemo<Record<string, string>>(() => {
    let h: Record<string, string> = {};
    try {
      h = JSON.parse(requestHeaders || '{}');
    } catch {
      /* */
    }
    return Object.fromEntries(
      Object.entries(h).map(([k, v]) => [
        k,
        v.replace(/\{\{\s*auth_token\s*\}\}/g, '[hidden]'),
      ])
    );
  }, [requestHeaders]);

  const curlText = useMemo(() => {
    const substituted = substituteVars(reqBody || '{}', varValues);
    return buildCurl(
      method || 'POST',
      url || '—',
      resolvedHeaders,
      substituted
    );
  }, [method, url, resolvedHeaders, reqBody, varValues]);

  const rawResponse = useMemo(() => {
    if (!testResult?.response) return null;
    const r = testResult.response;
    return r.raw_response ?? r;
  }, [testResult]);

  const rawResponseText = useMemo(() => {
    if (!rawResponse) return '';
    try {
      return JSON.stringify(rawResponse, null, 2);
    } catch {
      return String(rawResponse);
    }
  }, [rawResponse]);

  const statusCode = useMemo(() => {
    if (!testResult) return '';
    const r = testResult.response;
    if (r?.status_code) return String(r.status_code);
    return testResult.success ? '200' : 'error';
  }, [testResult]);

  const mappedValues = useMemo(() => {
    if (!rawResponse) return {} as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [path, varName] of Object.entries(pathToVar)) {
      out[varName] = applyJsonPath(rawResponse, path);
    }
    return out;
  }, [rawResponse, pathToVar]);

  const handleTest = async () => {
    const inputData: Record<string, unknown> = { ...varValues };
    for (const [k, files] of Object.entries(fileValues)) {
      if (!files.length) continue;
      inputData[k] = await Promise.all(
        files.map(
          f =>
            new Promise<{ name: string; content_type: string; data: string }>(
              (resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => {
                  const uri = reader.result as string;
                  resolve({
                    name: f.name,
                    content_type: f.type,
                    data: uri.split(',')[1] ?? uri,
                  });
                };
                reader.onerror = reject;
                reader.readAsDataURL(f);
              }
            )
        )
      );
    }
    onRunTest(inputData);
  };

  const isSuccess = statusCode.startsWith('2');

  const sectionDivider = (label: string) => (
    <Divider sx={{ my: 2 }}>
      <Typography
        variant="caption"
        sx={{
          color: 'text.disabled',
          fontWeight: 600,
          fontSize: 11,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        {label}
      </Typography>
    </Divider>
  );

  return (
    <SectionCard
      title="Test"
      subtitle="Fire a live request and see exactly what your API returns and how Rhesis maps it."
      actions={
        <LoadingButton
          variant="contained"
          onClick={handleTest}
          loading={isTestingEndpoint}
          loadingPosition="start"
          startIcon={<PlayArrowIcon />}
        >
          Run test
        </LoadingButton>
      }
    >
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0 }}>
        {/* Left — request */}
        <Box sx={testPanelSx}>
          <Box
            sx={{ ...testPanelHeaderSx, cursor: 'pointer', userSelect: 'none' }}
            onClick={() => setReqExpanded(v => !v)}
          >
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'monospace',
                fontWeight: 700,
                color: 'text.secondary',
                fontSize: 11,
                flexShrink: 0,
              }}
            >
              {method || 'POST'}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'monospace',
                color: 'text.disabled',
                fontSize: 11,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                flex: 1,
              }}
            >
              {url || '—'}
            </Typography>
            {reqExpanded ? (
              <KeyboardArrowUpIcon
                sx={{ fontSize: 14, color: 'text.disabled', flexShrink: 0 }}
              />
            ) : (
              <KeyboardArrowDownIcon
                sx={{ fontSize: 14, color: 'text.disabled', flexShrink: 0 }}
              />
            )}
          </Box>
          <Collapse in={reqExpanded}>
            <Box
              component="pre"
              sx={{
                ...testPreviewSx,
                minHeight: 'unset',
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              {curlText}
            </Box>
          </Collapse>
          <Box component="pre" sx={testPreviewSx}>
            <TemplatePreview template={reqBody || '{}'} />
          </Box>
          {sectionDivider('What Rhesis sends')}
          <Box
            sx={{
              px: 2,
              pb: 2,
              display: 'flex',
              flexDirection: 'column',
              gap: 1.5,
            }}
          >
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
                  <Typography
                    variant="body2"
                    sx={{ color: 'text.disabled', flexShrink: 0, mt: 0.5 }}
                  >
                    :
                  </Typography>
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
                          setFileValues(prev => ({
                            ...prev,
                            [v]: Array.from(e.target.files ?? []),
                          }))
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
                        setVarValues(prev => ({ ...prev, [v]: e.target.value }))
                      }
                    />
                  )}
                </Box>
              ))
            )}
          </Box>
        </Box>

        {/* Center arrow */}
        <Box
          sx={{
            width: 48,
            flexShrink: 0,
            display: 'flex',
            justifyContent: 'center',
            pt: '140px',
          }}
        >
          {isTestingEndpoint ? (
            <CircularProgress size={20} />
          ) : (
            <ArrowRightAltIcon sx={{ fontSize: 32, color: 'text.secondary' }} />
          )}
        </Box>

        {/* Right — response */}
        <Box sx={testPanelSx}>
          <Box
            sx={{
              ...testPanelHeaderSx,
              minHeight: 36,
              cursor: rawResponse ? 'pointer' : 'default',
              userSelect: 'none',
            }}
            onClick={() => {
              if (rawResponse) setResExpanded(v => !v);
            }}
          >
            {statusCode ? (
              <>
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor: isSuccess ? 'success.main' : 'error.main',
                    flexShrink: 0,
                  }}
                />
                <Typography
                  variant="caption"
                  sx={{
                    fontFamily: 'monospace',
                    fontWeight: 700,
                    fontSize: 11,
                    color: isSuccess ? 'success.main' : 'error.main',
                    flex: 1,
                  }}
                >
                  {statusCode}
                </Typography>
                {resExpanded ? (
                  <KeyboardArrowUpIcon
                    sx={{ fontSize: 14, color: 'text.disabled', flexShrink: 0 }}
                  />
                ) : (
                  <KeyboardArrowDownIcon
                    sx={{ fontSize: 14, color: 'text.disabled', flexShrink: 0 }}
                  />
                )}
              </>
            ) : (
              <Typography
                variant="caption"
                sx={{ color: 'text.disabled', fontSize: 11 }}
              >
                No response yet
              </Typography>
            )}
          </Box>
          <Collapse in={resExpanded}>
            <Box
              component="pre"
              sx={{
                ...testPreviewSx,
                minHeight: 'unset',
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              {rawResponseText}
            </Box>
          </Collapse>
          <Box component="pre" sx={testPreviewSx}>
            {rawResponse ? (
              <JsonPreview value={rawResponse} pathToVar={pathToVar} />
            ) : (
              <Box
                component="span"
                sx={{
                  color: 'text.disabled',
                  fontFamily: 'monospace',
                  fontSize: 12,
                }}
              >
                Run a test to see the response
              </Box>
            )}
          </Box>
          {sectionDivider('What Rhesis reads')}
          <Box
            sx={{
              px: 2,
              pb: 2,
              display: 'flex',
              flexDirection: 'column',
              gap: 1.5,
            }}
          >
            {Object.keys(responseMapping).length === 0 ? (
              <Typography variant="body2" sx={{ color: 'text.disabled' }}>
                No response mapping configured yet.
              </Typography>
            ) : (
              Object.entries(responseMapping).map(([varName, path]) => {
                const val = mappedValues[varName];
                return (
                  <Box
                    key={varName}
                    sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}
                  >
                    <Chip
                      label={`{{ ${varName} }}`}
                      size="small"
                      sx={{ ...variableChipSx, flexShrink: 0, mt: 0.5 }}
                    />
                    <Typography
                      variant="body2"
                      sx={{ color: 'text.disabled', flexShrink: 0, mt: 0.5 }}
                    >
                      :
                    </Typography>
                    <TextField
                      size="small"
                      fullWidth
                      multiline
                      maxRows={4}
                      value={
                        val !== undefined
                          ? typeof val === 'string'
                            ? val
                            : JSON.stringify(val, null, 2)
                          : ''
                      }
                      placeholder={rawResponse ? 'not found' : path}
                      slotProps={{ input: { readOnly: true } }}
                    />
                  </Box>
                );
              })
            )}
          </Box>
        </Box>
      </Box>
      {testResult?.error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {testResult.error}
        </Alert>
      )}
    </SectionCard>
  );
}
