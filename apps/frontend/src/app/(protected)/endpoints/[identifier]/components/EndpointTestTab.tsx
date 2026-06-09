'use client';

import { useState } from 'react';
import SectionCard from '@/components/common/SectionCard';
import { useEndpointDetailContext } from './EndpointDetailContext';
import TestAndMap from '../../components/TestAndMap';
import { bodyToRequestMapping } from '../../components/mappingUtils';
import { invokeEndpoint } from '@/actions/endpoints';

export default function EndpointTestTab() {
  const { endpoint, saveFields } = useEndpointDetailContext();

  const [testResponse, setTestResponse] = useState('');
  const [isTestingEndpoint, setIsTestingEndpoint] = useState(false);

  const requestTemplate = JSON.stringify(
    endpoint.request_mapping ?? {},
    null,
    2
  );

  const responseMapping = (endpoint.response_mapping ?? {}) as Record<
    string,
    string
  >;

  const handleRequestTemplateChange = (t: string) => {
    saveFields({ request_mapping: bodyToRequestMapping(t) });
  };

  const handleResponseMappingChange = (m: Record<string, string>) => {
    saveFields({ response_mapping: m });
  };

  const handleTest = async (inputData: Record<string, unknown>) => {
    setIsTestingEndpoint(true);
    setTestResponse('');
    try {
      const result = await invokeEndpoint(endpoint.id, inputData);
      if (result.success) {
        setTestResponse(JSON.stringify(result.data ?? {}, null, 2));
      } else {
        setTestResponse(
          JSON.stringify({ error: result.error ?? 'Request failed' }, null, 2)
        );
      }
    } catch (err) {
      setTestResponse(
        JSON.stringify({ error: (err as Error).message }, null, 2)
      );
    } finally {
      setIsTestingEndpoint(false);
    }
  };

  return (
    <SectionCard title="Test connection">
      <TestAndMap
        key={endpoint.id}
        requestTemplate={requestTemplate}
        responseMapping={responseMapping}
        onRequestTemplateChange={handleRequestTemplateChange}
        onResponseMappingChange={handleResponseMappingChange}
        onTest={handleTest}
        testResponse={testResponse}
        isTestingEndpoint={isTestingEndpoint}
      />
    </SectionCard>
  );
}
