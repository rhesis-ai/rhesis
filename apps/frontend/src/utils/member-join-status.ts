import { User } from '@/utils/api-client/interfaces/user';

export type MemberJoinStatus = 'active' | 'invited';

/** True once the user has accepted organization membership. */
export function hasJoinedOrganization(user: User): boolean {
  return user.joined_at != null;
}

export function getMemberJoinStatus(user: User): MemberJoinStatus {
  return hasJoinedOrganization(user) ? 'active' : 'invited';
}

export function memberJoinStatusActiveODataFilter(): string {
  return 'joined_at ne null';
}

export function memberJoinStatusInvitedODataFilter(): string {
  return 'joined_at eq null';
}
