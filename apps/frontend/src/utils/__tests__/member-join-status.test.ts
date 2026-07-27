import {
  getMemberJoinStatus,
  hasJoinedOrganization,
  memberJoinStatusActiveODataFilter,
  memberJoinStatusInvitedODataFilter,
} from '../member-join-status';
import { User } from '@/utils/api-client/interfaces/user';

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: '00000000-0000-0000-0000-000000000001',
    email: 'viewer@example.com',
    ...overrides,
  };
}

describe('member join status', () => {
  it('treats users with joined_at as active', () => {
    const user = makeUser({ joined_at: '2026-07-13T10:00:00Z' });
    expect(hasJoinedOrganization(user)).toBe(true);
    expect(getMemberJoinStatus(user)).toBe('active');
  });

  it('treats invited users without joined_at as invited', () => {
    const user = makeUser({
      name: 'Invited Viewer',
      given_name: 'Invited',
      family_name: 'Viewer',
      last_login_at: null,
      external_provider_id: undefined,
    });
    expect(hasJoinedOrganization(user)).toBe(false);
    expect(getMemberJoinStatus(user)).toBe('invited');
  });

  it('builds OData filters for active and invited members', () => {
    expect(memberJoinStatusActiveODataFilter()).toBe('joined_at ne null');
    expect(memberJoinStatusInvitedODataFilter()).toBe('joined_at eq null');
  });
});
