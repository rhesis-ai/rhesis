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
  // For secrets, an empty string means "untouched / keep existing" and must not
  // be sent. An explicit null means "remove the saved value" and is sent through.
  if (cleaned.auth_token === '') {
    delete cleaned.auth_token;
  }
  if (cleaned.client_secret === '') {
    delete cleaned.client_secret;
  }

  const result = await updateEndpoint(endpointId, cleaned);
  if (!result.success) {
    throw new Error(result.error || 'Failed to update endpoint');
  }

  return cleaned as Endpoint;
}
