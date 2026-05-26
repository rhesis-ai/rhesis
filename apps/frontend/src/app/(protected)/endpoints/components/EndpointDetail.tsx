'use client';

import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { EndpointDetailProvider } from '../[identifier]/components/EndpointDetailContext';
import EndpointDetailView from '../[identifier]/components/EndpointDetailView';

interface EndpointDetailProps {
  endpoint: Endpoint;
  sessionToken: string;
  onUpdate?: (endpoint: Endpoint) => void;
  onDelete?: () => void;
}

export default function EndpointDetail({
  endpoint,
  sessionToken,
  onUpdate,
  onDelete,
}: EndpointDetailProps) {
  return (
    <EndpointDetailProvider
      endpoint={endpoint}
      sessionToken={sessionToken}
      onUpdate={onUpdate}
      onDelete={onDelete}
    >
      <EndpointDetailView />
    </EndpointDetailProvider>
  );
}
