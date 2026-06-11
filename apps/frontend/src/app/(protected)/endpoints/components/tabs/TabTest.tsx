'use client';

import { useState, useMemo } from 'react';
import { LoadingButton } from '@mui/lab';
import { PlayArrowIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import EndpointTestWorkbench from '../EndpointTestWorkbench';
import { responseMappingToPathToVar } from '../JsonPreview';

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

function substituteVars(
  template: string,
  values: Record<string, string>
): string {
  let result = template.replace(
    /"(\{\{\s*[\w.]+(?:\s*\|[^}]*)?\s*\}\})"/g,
    match => {
      const nameMatch = match.match(/\{\{\s*([\w.]+)/);
      if (!nameMatch) return match;
      const base = nameMatch[1].split('.')[0];
      return values[base] !== undefined ? JSON.stringify(values[base]) : match;
    }
  );
  result = result.replace(
    /\{\{\s*([\w.]+)(?:\s*\|[^}]*)?\s*\}\}/g,
    (_match, name) => {
      const base = name.split('.')[0];
      return values[base] !== undefined ? String(values[base]) : _match;
    }
  );
  return result;
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
