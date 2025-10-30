'use server';

import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';

export interface UpdateEndpointResult {
  success: boolean;
  data?: Endpoint;
  error?: string;
}

export async function updateEndpoint(
  endpointId: string,
  data: Partial<Endpoint>
): Promise<UpdateEndpointResult> {
  try {
    const session = await auth();
    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const apiFactory = new ApiClientFactory(session.session_token);
    const endpointsClient = apiFactory.getEndpointsClient();
    const updatedEndpoint = await endpointsClient.updateEndpoint(
      endpointId,
      data
    );

    return {
      success: true,
      data: updatedEndpoint,
    };
  } catch (error) {
    // Failed to update endpoint
    return {
      success: false,
      error:
        error instanceof Error ? error.message : 'An unknown error occurred',
    };
  }
}
