'use server';

import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

export interface InvokeEndpointResult {
  success: boolean;
  data?: any;
  error?: string;
}

export async function invokeEndpoint(
  endpointId: string,
  inputData: any
): Promise<InvokeEndpointResult> {
  try {
    const session = await auth();
    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const apiFactory = new ApiClientFactory(session.session_token);
    const endpointsClient = apiFactory.getEndpointsClient();
    const response = await endpointsClient.invokeEndpoint(
      endpointId,
      inputData
    );

    return {
      success: true,
      data: response,
    };
  } catch (error) {
    // Failed to invoke endpoint
    return {
      success: false,
      error:
        error instanceof Error ? error.message : 'An unknown error occurred',
    };
  }
}
