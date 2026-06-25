'use server';

import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import {
  AutoConfigureRequest,
  AutoConfigureResult,
} from '@/utils/api-client/interfaces/endpoint';

export interface AutoConfigureResponse {
  success: boolean;
  data?: AutoConfigureResult;
  error?: string;
}

export async function autoConfigureEndpoint(
  payload: AutoConfigureRequest
): Promise<AutoConfigureResponse> {
  try {
    const session = await auth();
    if (!session?.session_token) {
      throw new Error('No session token available');
    }

    const apiFactory = await createServerApiFactory(session.session_token);
    const endpointsClient = apiFactory.getEndpointsClient();
    const result = await endpointsClient.autoConfigure(payload);

    return {
      success: true,
      data: result,
    };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : 'An unknown error occurred',
    };
  }
}
