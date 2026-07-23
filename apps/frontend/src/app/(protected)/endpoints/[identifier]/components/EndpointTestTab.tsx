'use client';

import { useState, useMemo } from 'react';
import { Button } from '@mui/material';
import { PlayArrowIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import { useEndpointDetailContext } from './EndpointDetailContext';
import { invokeEndpoint } from '@/actions/endpoints';
import EndpointTestWorkbench from '../../components/EndpointTestWorkbench';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { responseMappingToPathToVar } from '../../components/JsonPreview';
import {
  extractVars,
  applyJsonPath,
  substituteVars,
  buildCurl,
} from '../../components/endpoint-template-utils';

export default function EndpointTestTab() {
  const { endpoint } = useEndpointDetailContext();
  const canInvoke = useCan(Capability.Endpoint.UPDATE);

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
      if (!result.success) {
        throw new Error(result.error ?? 'Test failed');
      }
      const data = result.data as Record<string, unknown>;
      const raw = data?.raw_response ?? data;
      setRawResponse(raw);

      // The backend returns HTTP 200 even when the endpoint invocation
      // itself failed (e.g. a connection error to the target URL) — the
      // failure is encoded in the body as `error: true` instead of the
      // HTTP status, so it must be checked explicitly rather than assumed
      // to be a 200 success just because the request reached the server.
      if (data?.error === true) {
        const message =
          (typeof data.message === 'string' && data.message) ||
          (typeof data.output === 'string' && data.output) ||
          'Endpoint invocation failed';
        setStatusCode(
          typeof data.status_code === 'number' ? String(data.status_code) : ''
        );
        setError(message);
        return;
      }

      setStatusCode(String(data?.status_code ?? '200'));
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
      title="Test"
      subtitle="Fire a live request and see exactly what your API returns and how Rhesis maps it."
      actions={
        canInvoke ? (
          <Button
            variant="contained"
            onClick={handleTest}
            loading={isTestingEndpoint}
            loadingPosition="start"
            startIcon={<PlayArrowIcon />}
          >
            Check connection
          </Button>
        ) : undefined
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
