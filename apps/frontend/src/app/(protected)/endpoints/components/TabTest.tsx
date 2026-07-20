'use client';

import { useState, useMemo } from 'react';
import { Button } from '@mui/material';
import { PlayArrowIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import EndpointTestWorkbench from './EndpointTestWorkbench';
import { responseMappingToPathToVar } from './JsonPreview';
import {
  extractVars,
  applyJsonPath,
  substituteVars,
  buildCurl,
} from './endpoint-template-utils';

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

  return (
    <SectionCard
      title="Test"
      subtitle="Fire a live request and see exactly what your API returns and how Rhesis maps it."
      actions={
        <Button
          variant="contained"
          onClick={handleTest}
          loading={isTestingEndpoint}
          loadingPosition="start"
          startIcon={<PlayArrowIcon />}
        >
          Check connection
        </Button>
      }
    >
      <EndpointTestWorkbench
        method={method}
        url={url}
        requestTemplate={reqBody}
        responseMapping={responseMapping}
        pathToVar={pathToVar}
        inputVars={inputVars}
        varValues={varValues}
        onVarValuesChange={setVarValues}
        fileValues={fileValues}
        onFileValuesChange={setFileValues}
        curlText={curlText}
        rawResponse={rawResponse}
        statusCode={statusCode}
        mappedValues={mappedValues}
        isTestingEndpoint={isTestingEndpoint}
        error={testResult?.error}
      />
    </SectionCard>
  );
}
