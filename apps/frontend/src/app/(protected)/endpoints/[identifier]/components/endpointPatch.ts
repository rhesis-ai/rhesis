'use client';

import { updateEndpoint } from '@/actions/endpoints';
import {
  Endpoint,
  EndpointEditData,
} from '@/utils/api-client/interfaces/endpoint';

export async function patchEndpointFields(
  endpointId: string,
  payload: EndpointEditData
): Promise<Endpoint> {
  const cleaned = { ...payload };
  if (cleaned.auth_token === '') {
    delete cleaned.auth_token;
  }

  const result = await updateEndpoint(endpointId, cleaned);
  if (!result.success) {
    throw new Error(result.error || 'Failed to update endpoint');
  }

  return cleaned as Endpoint;
}
