'use client';

import React, { useMemo, useRef, useState } from 'react';
import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { FileUploadIcon } from '@/components/icons';
import { BORDER_RADIUS } from '@/styles/theme';
import {
  JsonPreview,
  OUTPUT_VARIABLES,
  responseMappingToPathToVar,
} from './JsonPreview';
import { testPreviewSx } from './endpoint-styles';
import TestValuesEditor from './TestValuesEditor';
import {
  CardSubtitle,
  MappingCard,
  disabledContainedSx,
  MappingColumnHeaders,
  MappingRow,
  MappingRowList,
  TwoCardRow,
} from './MappingRows';
import { mappingTarget } from './responsePaths';
import {
  RawResponseCollapse,
  RunTestButton,
  TestResponseCard,
  type EndpointTestResult,
} from './TestResponseCard';
import {
  applyJsonPath,
  buildCurl,
  substituteVars,
} from './endpoint-template-utils';
import {
  formatTestValue as formatValue,
  testInputData,
  testValueVars,
  type TestValues,
} from './testValues';

interface TabTestProps {
  url: string;
  method: string;
  reqBody: string;
  resBody: string;
  requestHeaders?: string;
  /** Shared with the Mapping step, so values typed there carry over. */
  values: TestValues;
  onValuesChange: (values: TestValues) => void;
  testResult: EndpointTestResult | null;
  isTestingEndpoint: boolean;
  onRunTest: (inputData: Record<string, unknown>) => void;
}

function readFile(f: File) {
  return new Promise<{ name: string; content_type: string; data: string }>(
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
  );
}

/** An object or array, or a string holding one, to show as JSON; otherwise undefined. */
function asJsonValue(value: unknown): unknown {
  let parsed = value;
  if (typeof value === 'string') {
    try {
      parsed = JSON.parse(value);
    } catch {
      return undefined;
    }
  }
  return parsed !== null && typeof parsed === 'object' ? parsed : undefined;
}

export default function TabTest({
  url,
  method,
  reqBody,
  resBody,
  requestHeaders,
  values,
  onValuesChange: setValues,
  testResult,
  isTestingEndpoint,
  onRunTest,
}: TabTestProps) {
  const theme = useTheme();

  const inputVars = useMemo(() => testValueVars(reqBody), [reqBody]);

  const [fileValues, setFileValues] = useState<Record<string, File[]>>({});
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const resolvedHeaders = useMemo<Record<string, string>>(() => {
    try {
      const h = JSON.parse(requestHeaders || '{}') as Record<string, string>;
      return Object.fromEntries(
        Object.entries(h).map(([k, v]) => [
          k,
          String(v).replace(/\{\{\s*auth_token\s*\}\}/g, '[hidden]'),
        ])
      );
    } catch {
      return {};
    }
  }, [requestHeaders]);

  const curlText = useMemo(() => {
    const previewValues = Object.fromEntries(
      Object.entries(values).map(([k, v]) => [k, formatValue(v)])
    );
    for (const [k, files] of Object.entries(fileValues)) {
      if (files.length) previewValues[k] = files.map(f => f.name).join(', ');
    }
    return buildCurl(
      method || 'POST',
      url || '—',
      resolvedHeaders,
      substituteVars(reqBody || '{}', previewValues)
    );
  }, [method, url, resolvedHeaders, reqBody, values, fileValues]);

  const inputValue = values.input;
  const blockedReason =
    inputVars.includes('input') &&
    !(typeof inputValue === 'string' ? inputValue.trim() : inputValue)
      ? 'Enter a value for input first.'
      : undefined;

  const handleRun = async () => {
    const inputData = testInputData(values);
    for (const [k, files] of Object.entries(fileValues)) {
      if (files.length) inputData[k] = await Promise.all(files.map(readFile));
    }
    onRunTest(inputData);
  };

  const pathToVar = useMemo(() => {
    try {
      return responseMappingToPathToVar(JSON.parse(resBody));
    } catch {
      return {};
    }
  }, [resBody]);
  const rawResponse = mappingTarget(testResult?.response);
  const mappedValues = useMemo(() => {
    const out: Record<string, unknown> = {};
    for (const [path, varName] of Object.entries(pathToVar)) {
      out[varName] = applyJsonPath(rawResponse, path);
    }
    return out;
  }, [rawResponse, pathToVar]);
  const mappedVars = OUTPUT_VARIABLES.filter(v => v.name in mappedValues);

  const fileRow = (v: string) => (
    <>
      <input
        type="file"
        multiple
        hidden
        ref={el => {
          fileInputRefs.current[v] = el;
        }}
        onChange={e =>
          setFileValues({
            ...fileValues,
            [v]: Array.from(e.target.files ?? []),
          })
        }
      />
      {(fileValues[v]?.length ?? 0) > 0 ? (
        <Button
          startIcon={<FileUploadIcon />}
          onClick={() => fileInputRefs.current[v]?.click()}
          sx={{ textTransform: 'none' }}
        >
          {fileValues[v].map(f => f.name).join(', ')}
        </Button>
      ) : (
        <Button
          variant="contained"
          sx={disabledContainedSx}
          startIcon={<FileUploadIcon />}
          onClick={() => fileInputRefs.current[v]?.click()}
        >
          Upload
        </Button>
      )}
    </>
  );

  const requestCard = (
    <MappingCard
      complete={Boolean(testResult?.success)}
      title="Request"
      subtitle={
        <CardSubtitle>
          Type the values to send in this test request.
        </CardSubtitle>
      }
      action={
        <RunTestButton
          label="Send test request"
          onRun={() => void handleRun()}
          isTesting={isTestingEndpoint}
          blockedReason={blockedReason}
        />
      }
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <TestValuesEditor
          vars={inputVars}
          values={values}
          onValuesChange={setValues}
          editorKey="create-test-values"
          fieldLabel={v => `Value for ${v}`}
          renderFileField={fileRow}
        />
        <RawResponseCollapse label="cURL command" value={curlText} />
      </Box>
    </MappingCard>
  );

  return (
    <Stack spacing={5}>
      <TwoCardRow
        left={requestCard}
        right={
          <TestResponseCard
            result={testResult}
            isTesting={isTestingEndpoint}
            subtitle="What your API returned, and the value Rhesis reads for each variable."
            emptyText="Fill in the test values and click Send test request."
            successTitle="Endpoint is ready"
            complete={Boolean(testResult?.success)}
          >
            {mappedVars.length > 0 && (
              <Box>
                <MappingColumnHeaders
                  left="Rhesis' variables"
                  right="Returned values"
                />
                <MappingRowList>
                  {mappedVars.map(v => {
                    const json = asJsonValue(mappedValues[v.name]);
                    return (
                      <MappingRow key={v.name} label={v.name}>
                        {json !== undefined ? (
                          <Box
                            component="pre"
                            sx={{
                              ...testPreviewSx,
                              m: 0,
                              maxHeight: theme.spacing(30),
                            }}
                          >
                            <JsonPreview value={json} />
                          </Box>
                        ) : (
                          <Box
                            sx={{
                              px: 1.5,
                              py: 1,
                              borderRadius: BORDER_RADIUS.xs,
                              bgcolor: t => t.palette.greyscale.fieldSurface,
                              maxHeight: theme.spacing(15),
                              overflowY: 'auto',
                            }}
                          >
                            <Typography
                              variant="body2"
                              sx={{
                                wordBreak: 'break-word',
                                whiteSpace: 'pre-wrap',
                              }}
                            >
                              {formatValue(mappedValues[v.name])}
                            </Typography>
                          </Box>
                        )}
                      </MappingRow>
                    );
                  })}
                </MappingRowList>
              </Box>
            )}
            <RawResponseCollapse
              label="Complete response returned by your API"
              value={rawResponse}
            />
          </TestResponseCard>
        }
      />
      {!testResult?.success && !isTestingEndpoint && (
        <Alert severity="info">
          No successful test yet. You can still create the endpoint and test it
          later from its page.
        </Alert>
      )}
    </Stack>
  );
}
