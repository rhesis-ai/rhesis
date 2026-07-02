'use client';

import React, { useState, useMemo, useEffect, useCallback } from 'react';
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
import {
  JsonPreview,
  OUTPUT_VARIABLES,
  responseMappingToPathToVar,
} from './JsonPreview';

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

// ── Props ─────────────────────────────────────────────────────────────────────

export interface MappingEditorProps {
  requestTemplate: string;
  responseMapping: Record<string, string>;
  onRequestTemplateChange: (t: string) => void;
  onResponseMappingChange: (m: Record<string, string>) => void;
  onTest: (inputData: Record<string, unknown>) => void;
  testResponse: string;
  isTestingEndpoint: boolean;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function MappingEditor({
  requestTemplate: requestTemplateProp,
  responseMapping,
  onRequestTemplateChange,
  onResponseMappingChange,
  onTest,
  testResponse,
  isTestingEndpoint,
}: MappingEditorProps) {
  const [requestTemplate, setRequestTemplate] = useState(requestTemplateProp);

  useEffect(() => {
    setRequestTemplate(requestTemplateProp);
  }, [requestTemplateProp]);

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
                  sx={{ ...testPreviewSx, maxHeight: 400, lineHeight: 1.8 }}
                >
                  <JsonPreview
                    value={mappingTarget}
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
