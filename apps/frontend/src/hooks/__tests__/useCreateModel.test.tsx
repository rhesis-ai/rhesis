import React from 'react';
import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { useCreateModel } from '../useCreateModel';
import { modelKeys } from '@/constants/query-keys';
import type { ModelCreate } from '@/utils/api-client/interfaces/model';

const mockCreateModel = jest.fn();
let mockStatus = 'authenticated';

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { id: 'user-1' } }, status: mockStatus }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getModelsClient: () => ({ createModel: mockCreateModel }),
  })),
}));

const MODEL_DATA = { name: 'My model' } as unknown as ModelCreate;

function setup() {
  const queryClient = new QueryClient();
  const invalidate = jest.spyOn(queryClient, 'invalidateQueries');
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useCreateModel(), { wrapper });
  return { createModel: result.current, invalidate };
}

beforeEach(() => {
  jest.clearAllMocks();
  mockStatus = 'authenticated';
  mockCreateModel.mockResolvedValue({ id: 'model-1' });
});

describe('useCreateModel', () => {
  it('creates the model and invalidates the cached model lists', async () => {
    const { createModel, invalidate } = setup();

    await expect(createModel(MODEL_DATA)).resolves.toEqual({ id: 'model-1' });

    expect(mockCreateModel).toHaveBeenCalledWith(MODEL_DATA);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: modelKeys.all() });
  });

  it('refuses without a session and makes no request', async () => {
    mockStatus = 'unauthenticated';
    const { createModel } = setup();

    await expect(createModel(MODEL_DATA)).rejects.toThrow('No session token');
    expect(mockCreateModel).not.toHaveBeenCalled();
  });
});
