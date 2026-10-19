import { patchEndpointFields } from '../endpointPatch';
import { updateEndpoint } from '@/actions/endpoints';

jest.mock('@/actions/endpoints', () => ({
  updateEndpoint: jest.fn(),
}));

const mockUpdate = updateEndpoint as jest.MockedFunction<typeof updateEndpoint>;

describe('patchEndpointFields', () => {
  beforeEach(() => {
    mockUpdate.mockReset();
    mockUpdate.mockResolvedValue({ success: true } as Awaited<
      ReturnType<typeof updateEndpoint>
    >);
  });

  it('drops empty secrets so the stored ones are kept', async () => {
    await patchEndpointFields('ep-1', {
      name: 'n',
      auth_token: '',
      client_secret: '',
    });
    expect(mockUpdate).toHaveBeenCalledWith('ep-1', { name: 'n' });
  });

  it('passes null and new secrets through', async () => {
    await patchEndpointFields('ep-1', {
      auth_token: null,
      client_secret: 'new-secret',
    });
    expect(mockUpdate).toHaveBeenCalledWith('ep-1', {
      auth_token: null,
      client_secret: 'new-secret',
    });
  });

  it('throws when the update fails', async () => {
    mockUpdate.mockResolvedValue({ success: false, error: 'nope' } as Awaited<
      ReturnType<typeof updateEndpoint>
    >);
    await expect(patchEndpointFields('ep-1', { name: 'n' })).rejects.toThrow(
      'nope'
    );
  });
});
