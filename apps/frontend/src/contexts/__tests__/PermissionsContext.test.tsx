import React from 'react';
import { render, screen, waitFor } from '@/test-utils';
import '@testing-library/jest-dom';

import {
  PermissionsProvider,
  useAmbientPermissions,
} from '../PermissionsContext';

const mockGetMyPermissions = jest.fn();

const AUTHENTICATED_SESSION = {
  data: { session_token: 'test-token', user: { id: 'user-1' } },
  status: 'authenticated',
};

jest.mock('next-auth/react', () => ({
  useSession: () => AUTHENTICATED_SESSION,
}));

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({ activeProject: { id: 'project-1' } }),
}));

// RBAC "on" and features already resolved — isolates PermissionsProvider's
// own initialData-seeding behavior from FeaturesProvider's.
jest.mock('@/contexts/FeaturesContext', () => ({
  useFeature: () => true,
  useFeaturesState: () => ({ loading: false }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getPermissionsClient: () => ({
      getMyPermissions: mockGetMyPermissions,
    }),
  })),
}));

beforeEach(() => {
  mockGetMyPermissions.mockReset();
});

function Probe() {
  const { permitted_actions, loading } = useAmbientPermissions();
  return (
    <div>
      <div data-testid="loading">{String(loading)}</div>
      <div data-testid="actions">{permitted_actions.join(',')}</div>
    </div>
  );
}

describe('PermissionsProvider server-seeded initialPermissions', () => {
  it('reports loading=false and the seeded capabilities synchronously, with no fetch', () => {
    // Never-resolving promise: if the provider fell back to fetching instead
    // of trusting the seed, `loading` would stay true and this assertion
    // would fail rather than pass synchronously.
    mockGetMyPermissions.mockReturnValue(new Promise(() => {}));

    render(
      <PermissionsProvider initialPermissions={['metric:read', 'tool:read']}>
        <Probe />
      </PermissionsProvider>
    );

    expect(screen.getByTestId('loading')).toHaveTextContent('false');
    expect(screen.getByTestId('actions')).toHaveTextContent(
      'metric:read,tool:read'
    );
  });

  it('falls back to the normal client fetch when initialPermissions is null', async () => {
    mockGetMyPermissions.mockResolvedValue(['metric:read']);

    render(
      <PermissionsProvider initialPermissions={null}>
        <Probe />
      </PermissionsProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('actions')).toHaveTextContent('metric:read')
    );
    expect(mockGetMyPermissions).toHaveBeenCalledTimes(1);
  });
});
