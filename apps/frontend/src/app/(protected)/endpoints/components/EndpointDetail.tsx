'use client';

import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { EndpointDetailProvider } from '../[identifier]/components/EndpointDetailContext';
import EndpointDetailView from '../[identifier]/components/EndpointDetailView';

interface EndpointDetailProps {
  endpoint: Endpoint;
}

export default function EndpointDetail({ endpoint }: EndpointDetailProps) {
  return (
    <EndpointDetailProvider endpoint={endpoint}>
      <EndpointDetailView />
    </EndpointDetailProvider>
  );
}
