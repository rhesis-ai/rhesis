'use client';

import React, { useMemo, useState } from 'react';
import { Box, MenuItem, Select, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import JsonMonacoField from '../[identifier]/components/JsonMonacoField';
import { OUTPUT_VARIABLES } from './JsonPreview';
import {
  MappingColumnHeaders,
  MappingRow,
  MappingRowList,
  ModeLink,
} from './MappingRows';
import { mappingTarget, responsePaths } from './responsePaths';
import {
  RawResponseCollapse,
  TestResponseCard,
  type EndpointTestResult,
} from './TestResponseCard';

interface ResponseMappingCardProps {
  responseMapping: string;
  onResponseMappingChange: (value: string) => void;
  testResult: EndpointTestResult | null;
  isTesting: boolean;
  inputMapped: boolean;
  complete: boolean;
}

/** Variable → JSONPath, or null when the JSON can't be shown as rows. */
function parseMapping(json: string): Record<string, string> | null {
  try {
    const parsed: unknown = JSON.parse(json || '{}');
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed))
      return null;
    const entries = Object.entries(parsed as Record<string, unknown>);
    if (entries.some(([, v]) => typeof v !== 'string')) return null;
    return parsed as Record<string, string>;
  } catch {
    return null;
  }
}

const toPath = (jsonPath: string) => jsonPath.replace(/^\$\.?/, '');

export default function ResponseMappingCard({
  responseMapping,
  onResponseMappingChange,
  testResult,
  isTesting,
  inputMapped,
  complete,
}: ResponseMappingCardProps) {
  const theme = useTheme();
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';
  const [mode, setMode] = useState<'rows' | 'json'>('rows');

  const mapping = useMemo(
    () => parseMapping(responseMapping),
    [responseMapping]
  );
  const target = mappingTarget(testResult?.response);

  // Mapped paths the response didn't contain (e.g. from auto-configure) stay selectable.
  const paths = useMemo(() => {
    const found = responsePaths(target);
    const mapped = Object.values(mapping ?? {}).map(toPath);
    return [...found, ...mapped.filter(p => p && !found.includes(p))];
  }, [target, mapping]);

  const assign = (varName: string, path: string) => {
    const next = { ...(mapping ?? {}) };
    if (path) next[varName] = `$.${path}`;
    else delete next[varName];
    onResponseMappingChange(JSON.stringify(next, null, 2));
  };

  return (
    <TestResponseCard
      result={testResult}
      isTesting={isTesting}
      subtitle="Pick which part of your API's response holds each Rhesis variable."
      emptyText={
        inputMapped
          ? 'Rhesis sends a test request once the request is mapped.'
          : 'Map the input variable on the left. Rhesis then sends a test request and shows the response here.'
      }
      successTitle="Test request successful"
      complete={complete}
    >
      {mode === 'rows' ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Box>
            <MappingColumnHeaders
              left="Rhesis' variables"
              right="Value from your API's response"
            />
            <MappingRowList>
              {OUTPUT_VARIABLES.map(v => {
                const selected = mapping?.[v.name]
                  ? toPath(mapping[v.name])
                  : '';
                return (
                  <MappingRow
                    key={v.name}
                    label={v.name === 'output' ? `${v.name}*` : v.name}
                    info={v.description}
                  >
                    <Select
                      fullWidth
                      size="small"
                      displayEmpty
                      value={selected}
                      onChange={e => assign(v.name, e.target.value)}
                      inputProps={{
                        'aria-label': `Response value for ${v.name}`,
                      }}
                      renderValue={p =>
                        p ? (
                          `$.${p}`
                        ) : (
                          <Typography
                            variant="body2"
                            color="text.disabled"
                            component="span"
                          >
                            {v.name === 'output'
                              ? 'Select the reply text'
                              : 'Not mapped'}
                          </Typography>
                        )
                      }
                    >
                      <MenuItem value="">
                        <em>Not mapped</em>
                      </MenuItem>
                      {paths.map(p => (
                        <MenuItem key={p} value={p}>
                          {`$.${p}`}
                        </MenuItem>
                      ))}
                    </Select>
                  </MappingRow>
                );
              })}
            </MappingRowList>
          </Box>
          <ModeLink onClick={() => setMode('json')}>Edit as JSON</ModeLink>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <JsonMonacoField
              editorKey="create-response-mapping"
              height="180px"
              theme={editorTheme}
              value={responseMapping}
              onChange={onResponseMappingChange}
            />
            <Typography
              variant="caption"
              color="text.secondary"
              component="p"
              sx={{ mt: 0.5, mx: 1.75 }}
            >
              Map each Rhesis variable to a JSONPath in the response, e.g.{' '}
              {'"output": "$.choices[0].message.content"'}.
            </Typography>
          </Box>
          <ModeLink
            disabled={!mapping}
            disabledReason="Easy input needs valid JSON whose values are all paths."
            onClick={() => setMode('rows')}
          >
            Switch to easy input
          </ModeLink>
        </Box>
      )}
      <RawResponseCollapse
        label="Complete response returned by your API"
        value={target}
      />
    </TestResponseCard>
  );
}
