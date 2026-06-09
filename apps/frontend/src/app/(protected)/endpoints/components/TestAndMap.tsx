'use client';

import {
  useState,
  useMemo,
  useEffect,
  useCallback,
  Fragment,
  useRef,
} from 'react';
import {
  Box,
  Typography,
  Chip,
  TextField,
  Button,
  Popover,
  List,
  ListItemButton,
  ListItemText,
  Divider,
} from '@mui/material';
import { LoadingButton } from '@mui/lab';
import {
  PlayArrowIcon,
  KeyboardArrowDownIcon,
  KeyboardArrowUpIcon,
} from '@/components/icons';
import RequestBodyEditor from './RequestBodyEditor';
import { BORDER_RADIUS } from '@/styles/theme-constants';

// ── Constants ─────────────────────────────────────────────────────────────────

const REQUEST_VARIABLES = [
  {
    name: '{{ input }}',
    description: 'The test prompt sent to your endpoint.',
  },
  { name: '{{ messages }}', description: 'Full conversation history.' },
  {
    name: '{{ system_prompt }}',
    description: 'System prompt prepended to the conversation.',
  },
  {
    name: '{{ conversation_id }}',
    description: 'Conversation ID — pass it back to continue a session.',
  },
  {
    name: '{{ files }}',
    description: 'Files (images, documents) attached to the request.',
  },
];

const OUTPUT_VARIABLES = [
  {
    name: 'output',
    label: '{{ output }}',
    description: 'Main response text — evaluated against your metrics.',
  },
  {
    name: 'conversation_id',
    label: '{{ conversation_id }}',
    description: 'Conversation ID — Rhesis passes it back on the next turn.',
  },
  {
    name: 'metadata',
    label: '{{ metadata }}',
    description: 'Structured data (model, token counts…).',
  },
  {
    name: 'context',
    label: '{{ context }}',
    description: 'Retrieved documents or additional sources.',
  },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

// Handles both plain {{ var }} and Jinja filter expressions {{ var | filter }}
function extractTemplateVars(template: string): string[] {
  const vars = new Set<string>();
  for (const m of template.matchAll(/\{\{\s*([\w.]+)(?:\s*\|[^}]*)?\s*\}\}/g)) {
    vars.add(m[1]);
  }
  return [...vars];
}

// Handles both dot-notation (a.b.c) and bracket-notation (a[0].b)
function getAtPath(obj: unknown, path: string): unknown {
  if (!path) return obj;
  const parts: string[] = [];
  const re = /([^.[]+)|\[(\d+)\]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(path)) !== null) {
    parts.push(m[1] ?? m[2]);
  }
  let cur: unknown = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object') return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return cur;
}

// ── Response JSON tree ────────────────────────────────────────────────────────

interface JsonTreeProps {
  value: unknown;
  path: string;
  depth: number;
  comma: boolean;
  pathToVar: Record<string, string>;
  onKeyClick: (path: string, el: HTMLElement) => void;
}

const T = {
  key: 'primary.main',
  str: '#ce9178',
  num: '#b5cea8',
  kw: '#569cd6',
  bracket: 'text.secondary',
  comma: 'text.disabled',
};

function JsonTree({
  value,
  path,
  depth,
  comma,
  pathToVar,
  onKeyClick,
}: JsonTreeProps) {
  const indent = (n: number) => ' '.repeat(n * 2);
  const tail = comma ? (
    <Box component="span" sx={{ color: T.comma }}>
      ,
    </Box>
  ) : null;
  const mappedVar = pathToVar[path];

  if (mappedVar !== undefined) {
    const outVar = OUTPUT_VARIABLES.find(v => v.name === mappedVar);
    return (
      <>
        <Box
          component="span"
          sx={{
            bgcolor: theme =>
              theme.palette.mode === 'light'
                ? 'rgba(0,128,175,0.10)'
                : 'rgba(0,128,175,0.20)',
            color: 'primary.main',
            px: '4px',
            py: '1px',
            borderRadius: '3px',
            fontWeight: 500,
          }}
        >
          {outVar?.label ?? `{{ ${mappedVar} }}`}
        </Box>
        {tail}
      </>
    );
  }

  if (value === null)
    return (
      <>
        <Box component="span" sx={{ color: T.kw }}>
          null
        </Box>
        {tail}
      </>
    );
  if (typeof value === 'boolean')
    return (
      <>
        <Box component="span" sx={{ color: T.kw }}>
          {String(value)}
        </Box>
        {tail}
      </>
    );
  if (typeof value === 'number')
    return (
      <>
        <Box component="span" sx={{ color: T.num }}>
          {value}
        </Box>
        {tail}
      </>
    );
  if (typeof value === 'string')
    return (
      <>
        <Box component="span" sx={{ color: T.str }}>
          &quot;{value}&quot;
        </Box>
        {tail}
      </>
    );

  if (Array.isArray(value)) {
    if (!value.length)
      return (
        <>
          <Box component="span" sx={{ color: T.bracket }}>
            []
          </Box>
          {tail}
        </>
      );
    return (
      <>
        <Box component="span" sx={{ color: T.bracket }}>
          {'['}
        </Box>
        {'\n'}
        {value.map((item, i) => (
          // eslint-disable-next-line react/no-array-index-key
          <Fragment key={i}>
            {indent(depth + 1)}
            <JsonTree
              value={item}
              path={`${path}[${i}]`}
              depth={depth + 1}
              comma={i < value.length - 1}
              pathToVar={pathToVar}
              onKeyClick={onKeyClick}
            />
            {'\n'}
          </Fragment>
        ))}
        {indent(depth)}
        <Box component="span" sx={{ color: T.bracket }}>
          {']'}
        </Box>
        {tail}
      </>
    );
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (!entries.length)
      return (
        <>
          <Box component="span" sx={{ color: T.bracket }}>
            {'{}'}
          </Box>
          {tail}
        </>
      );
    return (
      <>
        <Box component="span" sx={{ color: T.bracket }}>
          {'{'}
        </Box>
        {'\n'}
        {entries.map(([k, v], i) => {
          const childPath = path ? `${path}.${k}` : k;
          const isAlreadyMapped = pathToVar[childPath] !== undefined;
          return (
            <Fragment key={k}>
              {indent(depth + 1)}
              <Box
                component="span"
                onClick={e => {
                  e.stopPropagation();
                  onKeyClick(childPath, e.currentTarget as HTMLElement);
                }}
                title={
                  isAlreadyMapped
                    ? 'Click to remap'
                    : 'Click to map to output variable'
                }
                sx={{
                  color: isAlreadyMapped ? 'primary.main' : T.key,
                  cursor: 'pointer',
                  borderRadius: '2px',
                  px: '2px',
                  ml: '-2px',
                  fontWeight: isAlreadyMapped ? 600 : 400,
                  '&:hover': {
                    bgcolor: 'rgba(0,128,175,0.10)',
                    outline: '1px dashed',
                    outlineColor: 'primary.main',
                  },
                }}
              >
                &quot;{k}&quot;
              </Box>
              <Box component="span" sx={{ color: T.comma }}>
                :{' '}
              </Box>
              <JsonTree
                value={v}
                path={childPath}
                depth={depth + 1}
                comma={i < entries.length - 1}
                pathToVar={pathToVar}
                onKeyClick={onKeyClick}
              />
              {'\n'}
            </Fragment>
          );
        })}
        {indent(depth)}
        <Box component="span" sx={{ color: T.bracket }}>
          {'}'}
        </Box>
        {tail}
      </>
    );
  }
  return null;
}

// ── Request Preview Headers sub-component ────────────────────────────────────

function RequestPreviewHeaders({ headers }: { headers: unknown }) {
  if (!headers || typeof headers !== 'object') return null;
  const entries = Object.entries(headers as Record<string, string>);
  if (!entries.length) return null;
  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
      {entries.map(([k, v], i) => (
        <Box
          key={k}
          sx={{
            display: 'flex',
            px: 1.5,
            py: 0.5,
            gap: 2,
            bgcolor: i % 2 === 0 ? 'action.hover' : 'transparent',
          }}
        >
          <Typography
            variant="caption"
            sx={{
              fontFamily: 'monospace',
              color: 'primary.main',
              minWidth: 180,
              flexShrink: 0,
            }}
          >
            {k}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              fontFamily: 'monospace',
              color: 'text.secondary',
              wordBreak: 'break-all',
            }}
          >
            {String(v)}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

// ── Props ─────────────────────────────────────────────────────────────────────

export interface TestAndMapProps {
  requestTemplate: string;
  responseMapping: Record<string, string>;
  onRequestTemplateChange: (t: string) => void;
  onResponseMappingChange: (m: Record<string, string>) => void;
  onTest: (inputData: Record<string, unknown>) => void;
  testResponse: string;
  isTestingEndpoint: boolean;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function TestAndMap({
  requestTemplate: requestTemplateProp,
  responseMapping: _responseMapping,
  onRequestTemplateChange,
  onResponseMappingChange,
  onTest,
  testResponse,
  isTestingEndpoint,
}: TestAndMapProps) {
  // Local editable state seeded from prop
  const [requestTemplate, setRequestTemplate] = useState(requestTemplateProp);

  // Re-seed when prop changes (e.g. endpoint switches)
  useEffect(() => {
    setRequestTemplate(requestTemplateProp);
  }, [requestTemplateProp]);

  // Extract {{ var }} names from whatever is in the editor right now
  const inputVars = useMemo(
    () => extractTemplateVars(requestTemplate),
    [requestTemplate]
  );

  const FILE_VAR_RE = /^(files?|images?)$/i;
  const isFileVar = (v: string) => FILE_VAR_RE.test(v);

  // Text values for non-file vars
  const [varValues, setVarValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(inputVars.filter(v => !isFileVar(v)).map(v => [v, '']))
  );
  // File objects for file vars
  const [fileValues, setFileValues] = useState<Record<string, File[]>>({});
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const inputVarsKey = inputVars.join(',');
  useEffect(() => {
    setVarValues(
      Object.fromEntries(inputVars.filter(v => !isFileVar(v)).map(v => [v, '']))
    );
    setFileValues({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputVarsKey]);

  // ── Response mapping state ─────────────────────────────────────────────────

  // pathToVar: response JSON path (without $.) → output var name
  // Starts empty — user maps manually by clicking keys in the response tree
  const [pathToVar, setPathToVar] = useState<Record<string, string>>({});

  // Popover for key mapping
  const [popoverAnchor, setPopoverAnchor] = useState<HTMLElement | null>(null);
  const [pendingPath, setPendingPath] = useState('');

  const handleKeyClick = (path: string, el: HTMLElement) => {
    setPendingPath(path);
    setPopoverAnchor(el);
  };

  const handlePickOutputVar = useCallback(
    (varName: string) => {
      setPopoverAnchor(null);
      const newPathToVar = { ...pathToVar };
      for (const p of Object.keys(newPathToVar)) {
        if (newPathToVar[p] === varName) delete newPathToVar[p];
      }
      newPathToVar[pendingPath] = varName;
      setPathToVar(newPathToVar);

      const newResponseMapping: Record<string, string> = {};
      for (const [p, v] of Object.entries(newPathToVar)) {
        newResponseMapping[v] = `$.${p}`;
      }
      onResponseMappingChange(newResponseMapping);
    },
    [pathToVar, pendingPath, onResponseMappingChange]
  );

  const handleRemoveMapping = useCallback(
    (varName: string) => {
      const newPathToVar = { ...pathToVar };
      for (const p of Object.keys(newPathToVar)) {
        if (newPathToVar[p] === varName) delete newPathToVar[p];
      }
      setPathToVar(newPathToVar);

      const newResponseMapping: Record<string, string> = {};
      for (const [p, v] of Object.entries(newPathToVar)) {
        newResponseMapping[v] = `$.${p}`;
      }
      onResponseMappingChange(newResponseMapping);
    },
    [pathToVar, onResponseMappingChange]
  );

  // Parse response JSON
  const parsedResponse = useMemo(() => {
    if (!testResponse) return null;
    try {
      return JSON.parse(testResponse);
    } catch {
      return null;
    }
  }, [testResponse]);

  // Extract raw_request from response (present on both success and error)
  const rawRequest = useMemo(() => {
    if (!parsedResponse || typeof parsedResponse !== 'object') return null;
    const r = parsedResponse as Record<string, unknown>;
    return (r.raw_request ?? r.request ?? null) as Record<
      string,
      unknown
    > | null;
  }, [parsedResponse]);

  const [requestPreviewOpen, setRequestPreviewOpen] = useState(false);

  // Extract mapped values from parsed response
  const mappedValues = useMemo(() => {
    if (!parsedResponse) return {};
    const out: Record<string, unknown> = {};
    for (const [path, varName] of Object.entries(pathToVar)) {
      out[varName] = getAtPath(parsedResponse, path);
    }
    return out;
  }, [parsedResponse, pathToVar]);

  const chipSx = {
    fontFamily: 'monospace',
    fontSize: 11,
    height: 22,
    cursor: 'pointer',
    bgcolor: (t: { palette: { mode: string } }) =>
      t.palette.mode === 'light'
        ? 'rgba(0,128,175,0.08)'
        : 'rgba(0,128,175,0.18)',
    color: 'primary.main',
    border: 1,
    borderColor: 'transparent',
    '& .MuiChip-label': { px: 1 },
    '&:hover': {
      bgcolor: (t: { palette: { mode: string } }) =>
        t.palette.mode === 'light'
          ? 'rgba(0,128,175,0.16)'
          : 'rgba(0,128,175,0.28)',
      borderColor: 'primary.main',
    },
  };

  const mappedVarNames = new Set(Object.values(pathToVar));

  const handleEditorChange = (t: string) => {
    setRequestTemplate(t);
    onRequestTemplateChange(t);
  };

  const handleTest = async () => {
    const inputData: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(varValues)) {
      try {
        inputData[k] = JSON.parse(v);
      } catch {
        inputData[k] = v;
      }
    }
    // Encode files as base64 data URIs
    for (const [k, files] of Object.entries(fileValues)) {
      if (!files.length) continue;
      const encoded = await Promise.all(
        files.map(
          f =>
            new Promise<{ name: string; content_type: string; data: string }>(
              (resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => {
                  const dataUri = reader.result as string;
                  // Strip "data:<mime>;base64," prefix — backend filters expect raw base64
                  const raw = dataUri.includes(',')
                    ? dataUri.split(',')[1]
                    : dataUri;
                  resolve({ name: f.name, content_type: f.type, data: raw });
                };
                reader.onerror = reject;
                reader.readAsDataURL(f);
              }
            )
        )
      );
      inputData[k] = encoded;
    }
    onTest(inputData);
  };

  return (
    <Box>
      {/* ── Request ── */}
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Request
      </Typography>

      <RequestBodyEditor
        value={requestTemplate}
        onChange={handleEditorChange}
        variables={REQUEST_VARIABLES}
        layout="side"
      />

      {/* ── Placeholder input rows ── */}
      {inputVars.length > 0 && (
        <Box sx={{ mt: 2 }}>
          {inputVars.map(v => (
            <Box
              key={v}
              sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}
            >
              <Chip
                label={`{{ ${v} }}`}
                size="small"
                sx={{ ...chipSx, cursor: 'default', flexShrink: 0 }}
              />
              {isFileVar(v) ? (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    flex: 1,
                  }}
                >
                  <input
                    type="file"
                    multiple
                    ref={el => {
                      fileInputRefs.current[v] = el;
                    }}
                    style={{ display: 'none' }}
                    onChange={e => {
                      const files = Array.from(e.target.files ?? []);
                      setFileValues(prev => ({ ...prev, [v]: files }));
                    }}
                  />
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => fileInputRefs.current[v]?.click()}
                  >
                    Upload
                  </Button>
                  {(fileValues[v]?.length ?? 0) > 0 ? (
                    <Typography
                      variant="caption"
                      sx={{ color: 'text.secondary' }}
                    >
                      {fileValues[v].map(f => f.name).join(', ')}
                    </Typography>
                  ) : (
                    <Typography
                      variant="caption"
                      sx={{ color: 'text.disabled' }}
                    >
                      No files selected
                    </Typography>
                  )}
                </Box>
              ) : (
                <TextField
                  size="small"
                  fullWidth
                  multiline
                  maxRows={4}
                  placeholder={`Value for ${v}…`}
                  value={varValues[v] ?? ''}
                  onChange={e =>
                    setVarValues(prev => ({ ...prev, [v]: e.target.value }))
                  }
                />
              )}
            </Box>
          ))}
        </Box>
      )}

      {/* ── Test button ── */}
      <Box sx={{ mt: 2, mb: testResponse ? 3 : 0 }}>
        <LoadingButton
          variant="contained"
          color="primary"
          onClick={handleTest}
          loading={isTestingEndpoint}
          loadingPosition="start"
          startIcon={<PlayArrowIcon />}
        >
          Test
        </LoadingButton>
      </Box>

      {/* ── Request Preview ── */}
      {rawRequest && (
        <Box sx={{ mt: 2 }}>
          <Box
            onClick={() => setRequestPreviewOpen(o => !o)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              cursor: 'pointer',
              userSelect: 'none',
              width: 'fit-content',
            }}
          >
            {requestPreviewOpen ? (
              <KeyboardArrowUpIcon
                sx={{ fontSize: 16, color: 'text.disabled' }}
              />
            ) : (
              <KeyboardArrowDownIcon
                sx={{ fontSize: 16, color: 'text.disabled' }}
              />
            )}
            <Typography
              variant="caption"
              sx={{ color: 'text.disabled', fontFamily: 'monospace' }}
            >
              {String(rawRequest.method ?? 'POST')}{' '}
              {String(rawRequest.url ?? '')}
            </Typography>
          </Box>

          {requestPreviewOpen && (
            <Box
              sx={{
                mt: 1,
                border: 1,
                borderColor: 'divider',
                borderRadius: BORDER_RADIUS.sm,
                overflow: 'hidden',
              }}
            >
              {/* Headers */}
              <RequestPreviewHeaders headers={rawRequest.headers} />
              {/* Body */}
              {rawRequest.body !== undefined && (
                <Box
                  component="pre"
                  sx={{
                    m: 0,
                    p: 1.5,
                    fontSize: 12,
                    fontFamily: 'monospace',
                    color: 'text.secondary',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    maxHeight: 300,
                    overflowY: 'auto',
                    bgcolor: 'background.paper',
                  }}
                >
                  {typeof rawRequest.body === 'string'
                    ? rawRequest.body
                    : JSON.stringify(rawRequest.body, null, 2)}
                </Box>
              )}
            </Box>
          )}
        </Box>
      )}

      {/* ── Response ── */}
      {testResponse && (
        <>
          <Divider sx={{ mb: 3, mt: rawRequest ? 2 : 0 }} />

          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Response
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
            {/* JSON tree */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              {parsedResponse !== null ? (
                <Box
                  component="pre"
                  sx={{
                    m: 0,
                    p: 1.5,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: BORDER_RADIUS.sm,
                    bgcolor: 'background.paper',
                    fontFamily: 'monospace',
                    fontSize: 12,
                    lineHeight: 1.8,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    overflowX: 'auto',
                    color: 'text.secondary',
                    maxHeight: 400,
                    overflowY: 'auto',
                  }}
                >
                  <JsonTree
                    value={parsedResponse}
                    path=""
                    depth={0}
                    comma={false}
                    pathToVar={pathToVar}
                    onKeyClick={handleKeyClick}
                  />
                </Box>
              ) : (
                <Box
                  component="pre"
                  sx={{
                    m: 0,
                    p: 1.5,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: BORDER_RADIUS.sm,
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: 'text.secondary',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {testResponse}
                </Box>
              )}
            </Box>

            {/* Output variable chips on the right */}
            <Box
              sx={{
                width: 200,
                flexShrink: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 0.75,
                pt: 0.5,
              }}
            >
              {OUTPUT_VARIABLES.map(({ name, label, description }) => {
                const isMapped = mappedVarNames.has(name);
                return (
                  <Box
                    key={name}
                    sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}
                  >
                    <Chip
                      label={isMapped ? `✓ ${label}` : label}
                      size="small"
                      onDelete={
                        isMapped ? () => handleRemoveMapping(name) : undefined
                      }
                      sx={{
                        ...chipSx,
                        alignSelf: 'flex-start',
                        cursor: 'default',
                        ...(isMapped && {
                          bgcolor: (t: { palette: { mode: string } }) =>
                            t.palette.mode === 'light'
                              ? 'rgba(56,142,60,0.08)'
                              : 'rgba(56,142,60,0.18)',
                          color: 'success.main',
                          borderColor: 'rgba(56,142,60,0.3)',
                        }),
                      }}
                    />
                    <Typography
                      variant="caption"
                      sx={{
                        color: 'text.disabled',
                        fontSize: 10,
                        lineHeight: 1.4,
                        pl: 0.25,
                      }}
                    >
                      {description}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          </Box>

          {/* ── Mapped output rows ── */}
          {Object.keys(pathToVar).length > 0 && (
            <Box
              sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 1 }}
            >
              {OUTPUT_VARIABLES.filter(v => mappedVarNames.has(v.name)).map(
                ({ name, label }) => {
                  const val = mappedValues[name];
                  return (
                    <Box
                      key={name}
                      sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}
                    >
                      <Chip
                        label={label}
                        size="small"
                        sx={{ ...chipSx, cursor: 'default', flexShrink: 0 }}
                      />
                      {val !== undefined ? (
                        <Typography
                          variant="body2"
                          sx={{
                            color: 'text.secondary',
                            fontFamily: 'monospace',
                            fontSize: 12,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: 500,
                          }}
                        >
                          {typeof val === 'string' ? val : JSON.stringify(val)}
                        </Typography>
                      ) : (
                        <Typography
                          variant="caption"
                          sx={{ color: 'text.disabled', fontStyle: 'italic' }}
                        >
                          not found in response
                        </Typography>
                      )}
                    </Box>
                  );
                }
              )}
            </Box>
          )}
        </>
      )}

      {/* ── Key mapping popover ── */}
      <Popover
        open={Boolean(popoverAnchor)}
        anchorEl={popoverAnchor}
        onClose={() => {
          setPopoverAnchor(null);
          setPendingPath('');
        }}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{ paper: { sx: { mt: 0.5, minWidth: 220 } } }}
      >
        <Typography
          variant="caption"
          sx={{
            px: 2,
            pt: 1.5,
            pb: 0.5,
            display: 'block',
            color: 'text.disabled',
            fontFamily: 'monospace',
            fontSize: 10,
          }}
        >
          {pendingPath}
        </Typography>
        <List dense disablePadding sx={{ pb: 0.5 }}>
          {OUTPUT_VARIABLES.map(({ name, label, description }) => (
            <ListItemButton
              key={name}
              onClick={() => handlePickOutputVar(name)}
              selected={pathToVar[pendingPath] === name}
              sx={{ px: 2, py: 0.75 }}
            >
              <ListItemText
                primary={label}
                secondary={description}
                slotProps={{
                  primary: { sx: { fontFamily: 'monospace', fontSize: 12 } },
                  secondary: { sx: { fontSize: 10 } },
                }}
              />
            </ListItemButton>
          ))}
        </List>
      </Popover>
    </Box>
  );
}
