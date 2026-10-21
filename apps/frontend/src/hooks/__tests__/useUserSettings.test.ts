import { QueryClient } from '@tanstack/react-query';

import { userSettingsKeys } from '@/constants/query-keys';
import type { UserSettings } from '@/utils/api-client/interfaces/user';

import { writeUserSettingsCache } from '../useUserSettings';

describe('writeUserSettingsCache', () => {
  it('keeps GET-only fields the PATCH response leaves out', () => {
    const queryClient = new QueryClient();
    const key = userSettingsKeys.all('user-1');
    queryClient.setQueryData<UserSettings>(key, {
      has_password: true,
      provider_type: 'email',
      email: 'user@example.com',
      default_project: {
        project_id: '00000000-0000-0000-0000-000000000001',
        name: 'Old',
      },
    });

    writeUserSettingsCache(queryClient, 'user-1', {
      default_project: {
        project_id: '00000000-0000-0000-0000-000000000002',
        name: 'New',
      },
    });

    expect(queryClient.getQueryData(key)).toEqual({
      has_password: true,
      provider_type: 'email',
      email: 'user@example.com',
      default_project: {
        project_id: '00000000-0000-0000-0000-000000000002',
        name: 'New',
      },
    });
  });

  it('leaves an empty cache for the next GET to fill', () => {
    const queryClient = new QueryClient();

    writeUserSettingsCache(queryClient, 'user-1', {
      default_project: {
        project_id: '00000000-0000-0000-0000-000000000002',
        name: 'New',
      },
    });

    expect(
      queryClient.getQueryData(userSettingsKeys.all('user-1'))
    ).toBeUndefined();
    // A query left in "success" with no data would block the next GET.
    expect(
      queryClient.getQueryCache().find({
        queryKey: userSettingsKeys.all('user-1'),
      })
    ).toBeUndefined();
  });
});
