'use client';

import React, { useMemo, useState } from 'react';
import { Box, ListItemText, MenuItem, Select, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import JsonMonacoField from '../[identifier]/components/JsonMonacoField';
import {
  OUTPUT_VARIABLES,
  pathToVarToResponseMapping,
  responseMappingToPathToVar,
} from './JsonPreview';
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
  onRunTest: () => void;
  blockedReason?: string;
}

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

export default function ResponseMappingCard({
  responseMapping,
  onResponseMappingChange,
  testResult,
  isTesting,
  onRunTest,
  blockedReason,
}: ResponseMappingCardProps) {
  const theme = useTheme();
  const editorTheme = theme.palette.mode === 'dark' ? 'vs-dark' : 'light';
  const [mode, setMode] = useState<'rows' | 'json'>('rows');

  const parsedMapping = parseMapping(responseMapping);
  const pathToVar = useMemo(
    () => responseMappingToPathToVar(parseMapping(responseMapping) ?? {}),
    [responseMapping]
  );
  const target = mappingTarget(testResult?.response);

  // Mapped paths the response didn't contain (e.g. from auto-configure) still get a row.
  const paths = useMemo(() => {
    const found = responsePaths(target);
    return [
      ...found,
      ...Object.keys(pathToVar).filter(p => !found.includes(p)),
    ];
  }, [target, pathToVar]);

  const assign = (path: string, varName: string) => {
    const next = { ...pathToVar };
    for (const p of Object.keys(next)) {
      if (next[p] === varName) delete next[p];
    }
    if (varName) next[path] = varName;
    else delete next[path];
    onResponseMappingChange(
      JSON.stringify(pathToVarToResponseMapping(next), null, 2)
    );
  };

  return (
    <TestResponseCard
      result={testResult}
      isTesting={isTesting}
      onRun={onRunTest}
      blockedReason={blockedReason}
      emptyText="Run a test request to receive your API's response."
      successTitle="Test request successful"
    >
      {mode === 'rows' ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {paths.length > 0 ? (
            <Box>
              <MappingColumnHeaders
                left="Your API's keys"
                right="Mapped variables"
              />
              <Box sx={{ maxHeight: 440, overflowY: 'auto' }}>
                <MappingRowList>
                  {paths.map(path => (
                    <MappingRow key={path} label={`$.${path}`}>
                      <Select
                        fullWidth
                        size="small"
                        displayEmpty
                        value={pathToVar[path] ?? ''}
                        onChange={e => assign(path, e.target.value)}
                        inputProps={{ 'aria-label': `Variable for $.${path}` }}
                        renderValue={v =>
                          v ? (
                            v
                          ) : (
                            <Typography
                              variant="body2"
                              color="text.disabled"
                              component="span"
                            >
                              Assign variable
                            </Typography>
                          )
                        }
                      >
                        <MenuItem value="">
                          <em>None</em>
                        </MenuItem>
                        {OUTPUT_VARIABLES.map(v => {
                          const usedElsewhere = Object.entries(pathToVar).some(
                            ([p, name]) => name === v.name && p !== path
                          );
                          return (
                            <MenuItem
                              key={v.name}
                              value={v.name}
                              sx={{ whiteSpace: 'normal', maxWidth: 360 }}
                            >
                              <ListItemText
                                primary={v.label}
                                secondary={
                                  usedElsewhere
                                    ? `${v.description} Selecting it moves it here.`
                                    : v.description
                                }
                              />
                            </MenuItem>
                          );
                        })}
                      </Select>
                    </MappingRow>
                  ))}
                </MappingRowList>
              </Box>
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">
              The response has no keys to map. Edit the mapping as JSON instead.
            </Typography>
          )}
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
            disabled={!parsedMapping}
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
