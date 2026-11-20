import { FeatureName } from '@/constants/features';
import { hasServerCapability } from '../server-permissions';

const mockGetFeatures = jest.fn();
const mockGetMyPermissions = jest.fn();

// `React.cache` only dedupes inside a server render; pass the function through.
jest.mock('react', () => ({
  ...jest.requireActual('react'),
  cache: (fn: unknown) => fn,
}));

jest.mock('@/utils/api-client/server-factory', () => ({
  createServerApiFactory: async () => ({
    getFeaturesClient: () => ({ getFeatures: mockGetFeatures }),
    getPermissionsClient: () => ({ getMyPermissions: mockGetMyPermissions }),
  }),
}));

jest.mock('@/utils/server-active-project', () => ({
  getServerActiveProjectId: async () => 'project-1',
}));

const rbac = (on: boolean) => ({ enabled: on ? [FeatureName.RBAC] : [] });

describe('hasServerCapability', () => {
  beforeEach(() => {
    mockGetFeatures.mockReset();
    mockGetMyPermissions.mockReset();
  });

  it('asks for permissions without waiting for features', async () => {
    let resolveFeatures: (value: unknown) => void = () => undefined;
    mockGetFeatures.mockReturnValue(
      new Promise(r => {
        resolveFeatures = r;
      })
    );
    mockGetMyPermissions.mockResolvedValue(['thing:read']);

    const result = hasServerCapability('thing:read');
    await new Promise(r => setTimeout(r, 0));
    expect(mockGetMyPermissions).toHaveBeenCalledTimes(1);

    resolveFeatures(rbac(true));
    await expect(result).resolves.toBe(true);
  });

  it('allows everything when RBAC is off, even if permissions fail', async () => {
    mockGetFeatures.mockResolvedValue(rbac(false));
    mockGetMyPermissions.mockRejectedValue(new Error('boom'));

    await expect(hasServerCapability('thing:read')).resolves.toBe(true);
  });

  it('checks the permission list when RBAC is on', async () => {
    mockGetFeatures.mockResolvedValue(rbac(true));
    mockGetMyPermissions.mockResolvedValue(['thing:read']);

    await expect(hasServerCapability('thing:read')).resolves.toBe(true);
    await expect(hasServerCapability('thing:delete')).resolves.toBe(false);
  });

  it('fails closed when RBAC is on and permissions fail', async () => {
    mockGetFeatures.mockResolvedValue(rbac(true));
    mockGetMyPermissions.mockRejectedValue(new Error('boom'));

    await expect(hasServerCapability('thing:read')).resolves.toBe(false);
  });

  it('fails closed when features fail', async () => {
    mockGetFeatures.mockRejectedValue(new Error('boom'));
    mockGetMyPermissions.mockResolvedValue(['thing:read']);

    await expect(hasServerCapability('thing:read')).resolves.toBe(false);
  });
});
