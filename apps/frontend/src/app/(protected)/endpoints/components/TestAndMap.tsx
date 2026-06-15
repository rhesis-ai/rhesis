'use client';

import React, {
  useState,
  useMemo,
  useEffect,
  useCallback,
  Fragment,
} from 'react';
import {
  Box,
  Typography,
  Popover,
  List,
  ListItemButton,
  ListItemText,
  Link,
} from '@mui/material';
import { LoadingButton } from '@mui/lab';
import { PlayArrowIcon } from '@/components/icons';
import RequestBodyEditor from './RequestBodyEditor';
import FormSectionDivider from '@/components/common/FormSectionDivider';
import { sectionContainedButtonSx } from '@/components/common/SectionCardActions';
import { alpha, type Theme } from '@mui/material/styles';
import { testPreviewSx } from './endpoint-styles';
import VariableChip from './VariableChip';

// ── Constants ─────────────────────────────────────────────────────────────────

const REQUEST_VARIABLES = [
  {
    groupLabel: 'Input',
    name: '{{ input }}',
    description: 'Required. The test prompt sent to your endpoint.',
  },
  {
    groupLabel: 'Multi-turn',
    chips: ['{{ messages }}', '{{ conversation_id }}'],
    description: (
      <>
        <strong>messages</strong>: full conversation history for stateless
        endpoints. <strong>conversation_id</strong>: tracking ID for both
        stateful and stateless endpoints.
      </>
    ),
    docsUrl: 'https://docs.rhesis.ai/docs/endpoints/multi-turn-conversations',
  },
  {
    groupLabel: 'System prompt',
    name: '{{ system_prompt }}',
    description:
      'Injected as the system message. Rhesis removes it from the body before sending.',
  },
  {
    groupLabel: 'Files',
    name: '{{ files }}',
    description:
      'File attachments (images, PDFs). Use provider filters: to_openai, to_anthropic, to_gemini.',
    docsUrl:
      'https://docs.rhesis.ai/docs/endpoints/single-turn#file-format-filters',
  },
  {
    groupLabel: 'Experiments',
    name: '{{ params }}',
    description:
      'Required if you run experiments. Access individual values with dot notation: {{ params.model }}, {{ params.temperature }}.',
    docsUrl:
      'https://docs.rhesis.ai/docs/endpoints#using-experiment-parameters',
  },
  {
    groupLabel: 'Execution context',
    chips: [
      '{{ test_id }}',
      '{{ test_run_id }}',
      '{{ test_configuration_id }}',
    ],
    description:
      'Auto-filled on every test run — useful if your API logs or traces which test triggered the request.',
    docsUrl:
      'https://docs.rhesis.ai/docs/endpoints/mapping-examples#test-execution-context',
  },
];

const OUTPUT_VARIABLES = [
  {
    name: 'output',
    label: '{{ output }}',
    groupLabel: 'Output',
    description:
      'Required. The text your model returned — this is what Rhesis scores.',
  },
  {
    name: 'conversation_id',
    label: '{{ conversation_id }}',
    groupLabel: 'Conversation ID',
    description: 'Conversation ID for multi-turn tracking.',
    docsUrl: 'https://docs.rhesis.ai/docs/endpoints/multi-turn-conversations',
  },
  {
    name: 'context',
    label: '{{ context }}',
    groupLabel: 'Context',
    description:
      'Retrieved documents or sources — used by context-dependent metrics.',
  },
  {
    name: 'metadata',
    label: '{{ metadata }}',
    groupLabel: 'Metadata',
    description:
      'Structured data (model version, token counts…). Stored with the result and available to custom metrics.',
  },
  {
    name: 'tool_calls',
    label: '{{ tool_calls }}',
    groupLabel: 'Tool calls',
    description:
      'Tool or function calls made during response generation. Available to metrics that evaluate tool use.',
  },
];

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
  str: (t: Theme) => (t.palette.mode === 'dark' ? '#ce9178' : '#a31515'), // Intentional: syntax-highlighting token, no theme equivalent
  num: (t: Theme) => (t.palette.mode === 'dark' ? '#b5cea8' : '#098658'), // Intentional: syntax-highlighting token, no theme equivalent
  kw: (t: Theme) => (t.palette.mode === 'dark' ? '#569cd6' : '#0070c1'), // Intentional: syntax-highlighting token, no theme equivalent
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
            bgcolor: (t: {
              palette: { mode: string; primary: { main: string } };
            }) =>
              t.palette.mode === 'light'
                ? alpha(t.palette.primary.main, 0.1)
                : alpha(t.palette.primary.main, 0.2),
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
                  textDecoration: 'underline',
                  textDecorationStyle: 'dashed',
                  textDecorationColor: (t: Theme) =>
                    isAlreadyMapped
                      ? alpha(t.palette.primary.main, 0.5)
                      : alpha(t.palette.greyscale.subtitle, 0.5),
                  textUnderlineOffset: '3px',
                  '&:hover': {
                    bgcolor: (t: { palette: { primary: { main: string } } }) =>
                      alpha(t.palette.primary.main, 0.1),
                    outline: '1px dashed',
                    outlineColor: 'primary.main',
                    textDecorationColor: 'primary.main',
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

function responseMappingToPathToVar(
  mapping: Record<string, string>
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [varName, jsonPath] of Object.entries(mapping)) {
    out[jsonPath.replace(/^\$\./, '')] = varName;
  }
  return out;
}

export default function TestAndMap({
  requestTemplate: requestTemplateProp,
  responseMapping,
  onRequestTemplateChange,
  onResponseMappingChange,
  onTest,
  testResponse,
  isTestingEndpoint,
}: TestAndMapProps) {
  const [requestTemplate, setRequestTemplate] = useState(requestTemplateProp);

  useEffect(() => {
    setRequestTemplate(requestTemplateProp);
  }, [requestTemplateProp]);

  // ── Response mapping state ─────────────────────────────────────────────────

  const [pathToVar, setPathToVar] = useState<Record<string, string>>(() =>
    responseMappingToPathToVar(responseMapping)
  );

  const responseMappingKey = useMemo(
    () => JSON.stringify(responseMapping),
    [responseMapping]
  );
  useEffect(() => {
    setPathToVar(responseMappingToPathToVar(JSON.parse(responseMappingKey)));
  }, [responseMappingKey]);

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

  const parsedResponse = useMemo(() => {
    if (!testResponse) return null;
    try {
      return JSON.parse(testResponse);
    } catch {
      return null;
    }
  }, [testResponse]);

  const mappingTarget = useMemo(() => {
    if (!parsedResponse || typeof parsedResponse !== 'object')
      return parsedResponse;
    const r = parsedResponse as Record<string, unknown>;
    return r.raw_response != null ? r.raw_response : parsedResponse;
  }, [parsedResponse]);

  const mappedVarNames = new Set(Object.values(pathToVar));

  const mappedPaths = useMemo(() => {
    const out: Record<string, string> = {};
    for (const [path, varName] of Object.entries(pathToVar)) {
      out[varName] = `$.${path}`;
    }
    return out;
  }, [pathToVar]);

  const outputVarCard = (v: (typeof OUTPUT_VARIABLES)[number]) => {
    const isMapped = mappedVarNames.has(v.name);
    const jsonPath = mappedPaths[v.name];
    return (
      <Box
        key={v.name}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 0.5,
          p: 1.5,
          border: 1,
          borderColor: isMapped ? 'success.light' : 'divider',
          borderRadius: 1,
          bgcolor: isMapped
            ? (t: Theme) =>
                t.palette.mode === 'light'
                  ? alpha(t.palette.success.main, 0.04)
                  : alpha(t.palette.success.main, 0.08)
            : 'background.default',
        }}
      >
        {v.groupLabel && (
          <Typography
            variant="caption"
            sx={{ color: 'text.secondary', fontSize: 11, fontWeight: 600 }}
          >
            {v.groupLabel}
          </Typography>
        )}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.75,
            flexWrap: 'wrap',
          }}
        >
          <VariableChip label={v.label} isActive={isMapped} />
          {isMapped && jsonPath && (
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'monospace',
                fontSize: 10,
                color: 'success.main',
              }}
            >
              → {jsonPath}
            </Typography>
          )}
        </Box>
        <Typography
          variant="caption"
          sx={{ color: 'text.disabled', fontSize: 10, lineHeight: 1.4 }}
        >
          {v.description}
          {v.docsUrl && (
            <>
              {' '}
              <Box
                component="a"
                href={v.docsUrl}
                target="_blank"
                rel="noopener noreferrer"
                sx={{
                  color: 'primary.main',
                  textDecoration: 'none',
                  '&:hover': { textDecoration: 'underline' },
                }}
              >
                Docs ↗
              </Box>
            </>
          )}
        </Typography>
      </Box>
    );
  };

  const outputVarGrid = (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 1,
        mt: 1.5,
      }}
    >
      {OUTPUT_VARIABLES.map(outputVarCard)}
    </Box>
  );

  const handleEditorChange = (t: string) => {
    setRequestTemplate(t);
    onRequestTemplateChange(t);
  };

  const handleQuickTest = () => {
    onTest({ input: 'Hello, how are you?' });
  };

  const inlineCode = {
    fontFamily: 'monospace',
    fontSize: 12,
    bgcolor: (t: { palette: { mode: string } }) =>
      t.palette.mode === 'light'
        ? 'rgba(0,0,0,0.06)'
        : 'rgba(255,255,255,0.08)',
    borderRadius: '3px',
    px: '4px',
    py: '1px',
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <Box>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 2,
            mb: 2,
          }}
        >
          <FormSectionDivider
            headline="Request body"
            descriptiveText="Define the JSON body Rhesis sends with each test. Place {{ input }} where your API expects the prompt."
          />
          <LoadingButton
            variant="contained"
            onClick={handleQuickTest}
            loading={isTestingEndpoint}
            loadingPosition="start"
            startIcon={<PlayArrowIcon />}
            sx={{ ...sectionContainedButtonSx, flexShrink: 0, mt: 0.5 }}
          >
            Run test
          </LoadingButton>
        </Box>
        <RequestBodyEditor
          value={requestTemplate}
          onChange={handleEditorChange}
          variables={REQUEST_VARIABLES}
          layout="bottom"
        />
      </Box>

      <Box>
        <FormSectionDivider
          headline="Response"
          descriptiveText="Run a test, then click any key in the response to map it to a Rhesis variable."
        />
        <Box sx={{ mt: 2 }}>
          {testResponse ? (
            <>
              <Typography
                variant="body2"
                sx={{ color: 'text.secondary', mb: 2.5 }}
              >
                Your API returned the JSON below. <strong>Click any key</strong>{' '}
                to assign it to a Rhesis variable. At minimum, map{' '}
                <Box component="code" sx={inlineCode}>
                  {'{{ output }}'}
                </Box>{' '}
                to the field that holds your model&apos;s reply — that&apos;s
                the text Rhesis will score against your metrics.{' '}
                <Link
                  href="https://docs.rhesis.ai/docs/endpoints/mapping-examples"
                  target="_blank"
                  rel="noopener"
                  variant="body2"
                >
                  See all variables ↗
                </Link>
              </Typography>

              {mappingTarget !== null ? (
                <Box
                  component="pre"
                  sx={{
                    ...testPreviewSx,
                    maxHeight: 400,
                    lineHeight: 1.8,
                  }}
                >
                  <JsonTree
                    value={mappingTarget}
                    path=""
                    depth={0}
                    comma={false}
                    pathToVar={pathToVar}
                    onKeyClick={handleKeyClick}
                  />
                </Box>
              ) : (
                <Box component="pre" sx={testPreviewSx}>
                  {testResponse}
                </Box>
              )}

              {outputVarGrid}
            </>
          ) : (
            <Box>
              <Typography
                variant="body2"
                sx={{ color: 'text.secondary', mb: 2.5 }}
              >
                Run a test to see your API&apos;s response here, then click any
                key to map it.
              </Typography>
              {outputVarGrid}
            </Box>
          )}
        </Box>
      </Box>

      {/* Key mapping popover */}
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
          {OUTPUT_VARIABLES.map(({ name, label }) => (
            <ListItemButton
              key={name}
              onClick={() => handlePickOutputVar(name)}
              selected={pathToVar[pendingPath] === name}
              sx={{ px: 2, py: 0.75 }}
            >
              <ListItemText
                primary={label}
                slotProps={{
                  primary: { sx: { fontFamily: 'monospace', fontSize: 12 } },
                }}
              />
            </ListItemButton>
          ))}
          {pathToVar[pendingPath] !== undefined && (
            <>
              <Box
                sx={{ mx: 2, my: 0.5, borderTop: 1, borderColor: 'divider' }}
              />
              <ListItemButton
                onClick={() => {
                  const next = { ...pathToVar };
                  delete next[pendingPath];
                  setPathToVar(next);
                  const newMapping: Record<string, string> = {};
                  for (const [p, v] of Object.entries(next))
                    newMapping[v] = `$.${p}`;
                  onResponseMappingChange(newMapping);
                  setPopoverAnchor(null);
                  setPendingPath('');
                }}
                sx={{ px: 2, py: 0.75 }}
              >
                <ListItemText
                  primary="Remove mapping"
                  slotProps={{
                    primary: { sx: { fontSize: 12, color: 'error.main' } },
                  }}
                />
              </ListItemButton>
            </>
          )}
        </List>
      </Popover>
    </Box>
  );
}
