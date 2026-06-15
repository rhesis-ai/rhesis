'use client';

import { useState, useMemo } from 'react';
import { LoadingButton } from '@mui/lab';
import { PlayArrowIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import { useEndpointDetailContext } from './EndpointDetailContext';
import { invokeEndpoint } from '@/actions/endpoints';
import EndpointTestWorkbench from '../../components/EndpointTestWorkbench';
import { responseMappingToPathToVar } from '../../components/JsonPreview';

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

export default function EndpointTestTab() {
  const { endpoint } = useEndpointDetailContext();

  const requestTemplate = useMemo(
    () => JSON.stringify(endpoint.request_mapping ?? {}, null, 2),
    [endpoint.request_mapping]
  );
  const responseMapping = useMemo(
    () => (endpoint.response_mapping ?? {}) as Record<string, string>,
    [endpoint.response_mapping]
  );
  const pathToVar = useMemo(
    () => responseMappingToPathToVar(responseMapping),
    [responseMapping]
  );

  const inputVars = useMemo(
    () => extractVars(requestTemplate),
    [requestTemplate]
  );

  const [varValues, setVarValues] = useState<Record<string, string>>({});
  const [fileValues, setFileValues] = useState<Record<string, File[]>>({});
  const [rawResponse, setRawResponse] = useState<unknown>(null);
  const [statusCode, setStatusCode] = useState<string>('');
  const [isTestingEndpoint, setIsTestingEndpoint] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resolvedHeaders = useMemo<Record<string, string>>(() => {
    const h = (endpoint.request_headers ?? {}) as Record<string, string>;
    return Object.fromEntries(
      Object.entries(h).map(([k, v]) => [
        k,
        v.replace(/\{\{\s*auth_token\s*\}\}/g, '[hidden]'),
      ])
    );
  }, [endpoint]);

  const curlText = useMemo(() => {
    const substituted = substituteVars(requestTemplate || '{}', varValues);
    return buildCurl(
      endpoint.method || 'POST',
      endpoint.url || '—',
      resolvedHeaders,
      substituted
    );
  }, [
    endpoint.method,
    endpoint.url,
    resolvedHeaders,
    requestTemplate,
    varValues,
  ]);

  const mappedValues = useMemo(() => {
    if (!rawResponse) return {} as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [path, varName] of Object.entries(pathToVar)) {
      out[varName] = applyJsonPath(rawResponse, path);
    }
    return out;
  }, [rawResponse, pathToVar]);

  const handleTest = async () => {
    setIsTestingEndpoint(true);
    setRawResponse(null);
    setError(null);
    setStatusCode('');
    try {
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
      const result = await invokeEndpoint(endpoint.id, inputData);
      const data = result.data as Record<string, unknown>;
      const raw = data?.raw_response ?? data;
      setRawResponse(raw);
      setStatusCode(
        String(data?.status_code ?? (result.success ? '200' : 'error'))
      );
      if (responseMapping.conversation_id) {
        const convId = applyJsonPath(raw, responseMapping.conversation_id);
        if (typeof convId === 'string') {
          setVarValues(prev => ({ ...prev, conversation_id: convId }));
        }
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsTestingEndpoint(false);
    }
  };

  return (
    <SectionCard
      title="Connection Test"
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
        method={endpoint.method || 'POST'}
        url={endpoint.url || ''}
        requestTemplate={requestTemplate}
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
        error={error}
      />
    </SectionCard>
  );
}
