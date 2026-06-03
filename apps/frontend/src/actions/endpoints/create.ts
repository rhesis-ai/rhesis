'use server';

import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';

export interface CreateEndpointResult {
  success: boolean;
  data?: Endpoint;
  error?: string;
}

export async function createEndpoint(
  data: Omit<Endpoint, 'id'>
): Promise<CreateEndpointResult> {
  try {
    const session = await auth();
    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const apiFactory = await createServerApiFactory(session.session_token);
    const endpointsClient = apiFactory.getEndpointsClient();
    const endpoint = await endpointsClient.createEndpoint(data);

    return {
      success: true,
      data: endpoint,
    };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : 'An unknown error occurred',
    };
  }
}
