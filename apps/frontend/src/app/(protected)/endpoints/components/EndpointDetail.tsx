'use client';

import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { EndpointDetailProvider } from '../[identifier]/components/EndpointDetailContext';
import EndpointDetailView from '../[identifier]/components/EndpointDetailView';

interface EndpointDetailProps {
  endpoint: Endpoint;
}

/**
 * @deprecated Prefer EndpointDetailProvider + EndpointDetailView on the detail page.
 * Kept for tests and legacy imports.
 */
export default function EndpointDetail({ endpoint }: EndpointDetailProps) {
  return (
    <EndpointDetailProvider endpoint={endpoint}>
      <EndpointDetailView />
    </EndpointDetailProvider>
  );
}
