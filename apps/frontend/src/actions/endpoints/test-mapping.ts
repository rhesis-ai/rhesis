'use server';

import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';

export interface TestEndpointMappingResult {
  success: boolean;
  data?: Record<string, unknown>;
  error?: string;
}

export async function testEndpointMapping(
  endpointId: string,
  inputData: Record<string, unknown>,
  requestMapping: Record<string, unknown>,
  responseMapping: Record<string, string>
): Promise<TestEndpointMappingResult> {
  try {
    const session = await auth();
    if (!session || session.error) {
      throw new Error('No session token available');
    }

    const apiFactory = await createServerApiFactory();
    const endpointsClient = apiFactory.getEndpointsClient();
    const response = await endpointsClient.testEndpointMapping(endpointId, {
      request_mapping: requestMapping,
      response_mapping: responseMapping,
      input_data: inputData,
    });

    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : 'An unknown error occurred',
    };
  }
}
