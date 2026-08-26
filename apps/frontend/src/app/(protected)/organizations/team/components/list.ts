import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';
import { escapeODataValue } from '@/utils/odata-filter';
import {
  memberJoinStatusActiveODataFilter,
  memberJoinStatusInvitedODataFilter,
} from '@/utils/member-join-status';

export interface TeamFilters {
  /** Joined vs pending invite — mapped to joined_at OData checks. */
  memberStatus: '' | 'active' | 'invited';
  /** Account enabled flag — null means no filter. */
  accountStatus: boolean | null;
  email: string;
  name: string;
}

export const EMPTY_TEAM_FILTERS: TeamFilters = {
  memberStatus: '',
  accountStatus: null,
  email: '',
  name: '',
};

export function hasActiveTeamFilters(f: TeamFilters): boolean {
  return (
    f.memberStatus !== '' ||
    f.accountStatus !== null ||
    f.email.trim() !== '' ||
    f.name.trim() !== ''
  );
}

export function countActiveTeamFilters(f: TeamFilters): number {
  return (
    (f.memberStatus !== '' ? 1 : 0) +
    (f.accountStatus !== null ? 1 : 0) +
    (f.email.trim() !== '' ? 1 : 0) +
    (f.name.trim() !== '' ? 1 : 0)
  );
}

/** Team's `contains` clauses are case-sensitive, unlike the engine's default `search` kind — hence `raw`. */
function contains(column: string, value: string): string {
  return `contains(${column},'${escapeODataValue(value)}')`;
}

function anyOf(columns: string[], value: string): string {
  const q = value.trim();
  return `(${columns.map(c => contains(c, q)).join(' or ')})`;
}

const TEAM_FILTERS = {
  search: {
    kind: 'raw' as const,
    toOData: (value: string) =>
      value.trim()
        ? anyOf(['email', 'name', 'given_name', 'family_name'], value)
        : undefined,
  },
  email: {
    kind: 'raw' as const,
    toOData: (value: string) =>
      value.trim() ? contains('email', value.trim()) : undefined,
  },
  name: {
    kind: 'raw' as const,
    toOData: (value: string) =>
      value.trim()
        ? anyOf(['name', 'given_name', 'family_name'], value)
        : undefined,
  },
  memberStatus: {
    kind: 'raw' as const,
    toOData: (value: string) => {
      if (value === 'active') return memberJoinStatusActiveODataFilter();
      if (value === 'invited') return memberJoinStatusInvitedODataFilter();
      return undefined;
    },
  },
  accountStatus: {
    kind: 'raw' as const,
    toOData: (value: string) => {
      if (value === 'true') return 'is_active eq true';
      if (value === 'false') return 'is_active eq false';
      return undefined;
    },
  },
};

/**
 * Not wired through `useList`/`useListAuthGate`: today's team grid has no
 * independent read gate of its own (only Organization.READ, checked one level up by
 * `organizations/settings/page.tsx`), and adding one here would be a new restriction, not a
 * port. `capability` is still declared for documentation/typing; only `list`/`listParams`
 * are actually used, via `usePaginatedList` directly in `TeamMembersGrid`.
 */
export const teamList = defineList({
  title: 'Team',
  resource: 'team members',
  capability: Capability.Member.READ,
  defaultPageSize: 25,
  filters: TEAM_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getUsersClient().getUsers({
      skip: params.skip,
      limit: Math.min(params.limit, 100),
      $filter: params.$filter,
    }),
});
