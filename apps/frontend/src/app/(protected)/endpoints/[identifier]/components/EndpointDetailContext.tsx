'use client';

import React, { createContext, useContext } from 'react';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import {
  useEndpointDetail,
  type EndpointDetailContextValue,
} from './useEndpointDetail';

const EndpointDetailContext = createContext<EndpointDetailContextValue | null>(
  null
);

export function EndpointDetailProvider({
  endpoint,
  children,
}: {
  endpoint: Endpoint;
  children: React.ReactNode;
}) {
  const value = useEndpointDetail(endpoint);
  return (
    <EndpointDetailContext.Provider value={value}>
      {children}
    </EndpointDetailContext.Provider>
  );
}

export function useEndpointDetailContext(): EndpointDetailContextValue {
  const ctx = useContext(EndpointDetailContext);
  if (!ctx) {
    throw new Error(
      'useEndpointDetailContext must be used within EndpointDetailProvider'
    );
  }
  return ctx;
}
