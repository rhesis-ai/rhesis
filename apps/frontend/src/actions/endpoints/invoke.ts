'use server';

import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';

export interface InvokeEndpointResult {
  success: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

export async function invokeEndpoint(
  endpointId: string,
  inputData: Record<string, unknown>
): Promise<InvokeEndpointResult> {
  try {
    const session = await auth();
    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const apiFactory = await createServerApiFactory(session.session_token);
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
    return {
      success: false,
      error:
        error instanceof Error ? error.message : 'An unknown error occurred',
    };
  }
}
